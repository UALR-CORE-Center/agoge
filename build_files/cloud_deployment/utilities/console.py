"""Terminal presentation for setup.py.

Setup output goes through this module so the deploy tooling has one look:
a banner, section rules, colour-coded status lines, menus, and a live task
board. The board runs long gcloud commands (concurrently when they are
independent), writes each task's full output to ``.deploy_logs/``, and shows
only the tail of a task that fails.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable, Iterator

from rich import box
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

THEME = Theme({
    'info': 'cyan',
    'success': 'bold green',
    'warning': 'bold yellow',
    'error': 'bold red',
    'muted': 'grey50',
    'accent': 'bold bright_magenta',
    'heading': 'bold bright_white',
    'key': 'bold cyan',
})
console = Console(theme=THEME, highlight=False)

LOG_ROOT = Path('.deploy_logs')
KEEP_LOG_RUNS = 10
TAIL_LINES = 30
_ANSI = re.compile(r'\x1b\[[0-9;?]*[ -/]*[@-~]')
_SLUG = re.compile(r'[^a-z0-9]+')


# ---------------------------------------------------------------------------
# Status lines, banners, menus
# ---------------------------------------------------------------------------
def _line(icon: str, style: str, message: object) -> None:
    console.print(Text.assemble((f'{icon} ', style), str(message)))


def info(message: object) -> None:
    _line('•', 'info', message)


def success(message: object) -> None:
    _line('✔', 'success', message)


def warning(message: object) -> None:
    _line('▲', 'warning', message)


def error(message: object) -> None:
    _line('✖', 'error', message)


def muted(message: object) -> None:
    console.print(Text(str(message), style='muted'))


def section(title: str) -> None:
    console.print()
    console.rule(Text(f' {title} ', style='heading'), style='accent', align='left')


def banner(title: str, subtitle: str | None = None, details: dict | None = None) -> None:
    parts = []
    if subtitle:
        parts.append(Text(subtitle, style='muted'))
    if details:
        grid = Table.grid(padding=(0, 2))
        grid.add_column(style='muted', justify='right', no_wrap=True)
        grid.add_column(style='heading')
        for key, value in details.items():
            grid.add_row(key, str(value) if value else '—')
        if parts:
            parts.append(Text())
        parts.append(grid)
    console.print(Panel(
        Group(*parts), title=Text(f' {title} ', style='accent'), title_align='left',
        border_style='accent', box=box.ROUNDED, padding=(1, 2), expand=False,
    ))


def menu(title: str, items: Iterable[tuple[object, str]]) -> None:
    table = Table(box=None, show_header=False, padding=(0, 1), pad_edge=False)
    table.add_column(justify='right', style='key', no_wrap=True)
    table.add_column()
    for key, label in items:
        quiet = label.startswith(('Back', 'Exit'))
        table.add_row(Text(f'{key}', style='muted' if quiet else 'key'), Text(label, style='muted' if quiet else ''))
    console.print()
    console.print(Panel(
        table, title=Text(f' {title} ', style='heading'), title_align='left',
        border_style='info', box=box.ROUNDED, padding=(0, 2), expand=False,
    ))


def panel(title: str, body: str, *, style: str = 'info') -> None:
    """Show plain text (e.g. raw command output) in a titled box."""
    console.print(Panel(
        Text(body), title=Text(f' {title} ', style='heading'), title_align='left',
        border_style=style, box=box.ROUNDED, expand=False,
    ))


def _ansi(text: Text) -> str:
    with console.capture() as captured:
        console.print(text, end='')
    return captured.get()


def prompt(message: str) -> str:
    """input() with a styled prompt. Kept on builtins.input so tests can patch it."""
    return input(_ansi(Text.assemble(('› ', 'key'), message)))


def duration(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    return f'{minutes}:{secs:02d}'


# ---------------------------------------------------------------------------
# Live task board
# ---------------------------------------------------------------------------
_STATES = {
    'queued': ('○', 'muted', 'Queued'),
    'running': ('', 'info', 'Running'),
    'done': ('✔', 'success', 'Done'),
    'failed': ('✖', 'error', 'Failed'),
    'skipped': ('–', 'warning', 'Skipped'),
}


@dataclass(eq=False)
class Task:
    label: str
    log_path: Path
    state: str = 'queued'
    phase: str = 'Waiting'
    activity: str = ''
    started: float | None = None
    finished: float | None = None
    tail: deque = field(default_factory=lambda: deque(maxlen=TAIL_LINES))
    spinner: Spinner = field(default_factory=lambda: Spinner('dots', style='info'))
    _log: object = None

    @property
    def elapsed(self) -> float:
        if self.started is None:
            return 0.0
        return (self.finished or time.monotonic()) - self.started

    def begin(self) -> None:
        self.state, self.phase, self.started = 'running', 'Starting', time.monotonic()
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self._log = open(self.log_path, 'a', encoding='utf-8')
        except OSError:
            self._log = None

    def end(self, state: str) -> None:
        if self.state == 'running':
            self.state = state
        self.finished = time.monotonic()
        if self.state == 'done':
            self.phase = 'Complete'
        if self._log:
            self._log.close()
            self._log = None

    def log(self, line: str) -> None:
        self.tail.append(line)
        if self._log:
            self._log.write(line + '\n')
            self._log.flush()


class _Board:
    def __init__(self, title: str) -> None:
        self.title = title
        self.tasks: list[Task] = []
        self.lock = threading.Lock()
        self.started = time.monotonic()
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        self.run_dir = LOG_ROOT / f'{stamp}-{_slug(title)}'

    def add(self, label: str) -> Task:
        with self.lock:
            task = Task(label=label, log_path=self.run_dir / f'{len(self.tasks) + 1:02d}-{_slug(label)}.log')
            self.tasks.append(task)
        return task

    def __rich__(self) -> Panel:
        table = Table(box=box.SIMPLE_HEAD, expand=True, header_style='muted', pad_edge=False, show_edge=False)
        table.add_column('', width=1, no_wrap=True)
        table.add_column('Task', style='heading', no_wrap=True)
        table.add_column('Status', no_wrap=True)
        table.add_column('Phase', no_wrap=True)
        table.add_column('Activity', style='muted', no_wrap=True, overflow='ellipsis', ratio=1)
        table.add_column('Time', justify='right', no_wrap=True)
        for task in list(self.tasks):
            icon, style, label = _STATES[task.state]
            table.add_row(
                task.spinner if task.state == 'running' else Text(icon, style=style),
                task.label,
                Text(label, style=style),
                task.phase,
                task.activity,
                duration(task.elapsed) if task.started else '',
            )

        total = len(self.tasks)
        finished = sum(task.state in ('done', 'failed', 'skipped') for task in self.tasks)
        failed = any(task.state == 'failed' for task in self.tasks)
        colour = 'red' if failed else ('green' if finished == total else 'cyan')
        footer = Table.grid(expand=True, padding=(0, 1))
        footer.add_column(ratio=1)
        footer.add_column(no_wrap=True, justify='right')
        footer.add_row(
            ProgressBar(total=max(total, 1), completed=finished, complete_style=colour, finished_style=colour),
            Text(f'{finished}/{total} complete · {duration(time.monotonic() - self.started)}', style='muted'),
        )
        return Panel(
            Group(table, footer), title=Text(f' {self.title} ', style='heading'), title_align='left',
            border_style=colour, box=box.ROUNDED, padding=(0, 1),
        )


_active: _Board | None = None
_local = threading.local()


def _slug(value: str) -> str:
    return _SLUG.sub('-', value.lower()).strip('-')[:40] or 'task'


def _prune_logs() -> None:
    try:
        runs = sorted(path for path in LOG_ROOT.iterdir() if path.is_dir())
    except OSError:
        return
    for stale in runs[:-KEEP_LOG_RUNS]:
        shutil.rmtree(stale, ignore_errors=True)


def current_task() -> Task | None:
    return getattr(_local, 'task', None)


def run_tasks(title: str, tasks: list[tuple[str, Callable[[], bool | None]]]) -> dict[str, bool]:
    """Run independent tasks concurrently on one live board.

    A task fails when it returns False or raises. Every task runs to
    completion; the first exception is then re-raised. Called while a board is
    already on screen, the tasks are added to it as extra rows.
    """
    global _active
    if _active is not None:
        results, exc = _execute(_active, tasks)
        if exc:
            raise exc
        return results

    board = _Board(title)
    _active = board
    try:
        with Live(board, console=console, refresh_per_second=10, redirect_stdout=True, redirect_stderr=True):
            results, exc = _execute(board, tasks)
    finally:
        _active = None
    _report(board)
    if exc:
        raise exc
    return results


def _execute(board: _Board, tasks) -> tuple[dict[str, bool], BaseException | None]:
    entries = [(board.add(label), function) for label, function in tasks]

    def work(task: Task, function) -> bool:
        parent = current_task()
        _local.task = task
        task.begin()
        try:
            ok = function() is not False
        except BaseException as exc:
            task.log(f'{type(exc).__name__}: {exc}')
            task.activity = f'{type(exc).__name__}: {exc}'
            task.end('failed')
            raise
        finally:
            _local.task = parent
        task.end('done' if ok else 'failed')
        return ok

    results, first_error = {}, None
    if len(entries) == 1:
        task, function = entries[0]
        try:
            results[task.label] = work(task, function)
        except Exception as exc:
            results[task.label], first_error = False, exc
        return results, first_error

    with ThreadPoolExecutor(max_workers=len(entries), thread_name_prefix='setup-task') as pool:
        futures = [(task, pool.submit(work, task, function)) for task, function in entries]
        for task, future in futures:
            try:
                results[task.label] = future.result()
            except Exception as exc:
                results[task.label] = False
                first_error = first_error or exc
    return results, first_error


def _report(board: _Board) -> None:
    for task in board.tasks:
        if task.state != 'failed':
            continue
        console.print(Panel(
            Text('\n'.join(task.tail) or 'No output was captured.'),
            title=Text(f' ✖ {task.label} failed ', style='error'), title_align='left',
            subtitle=Text(f' Full log: {task.log_path} ', style='muted'), subtitle_align='left',
            border_style='red', box=box.ROUNDED,
        ))
    if board.run_dir.exists():
        console.print(Text.assemble(('Logs: ', 'muted'), (str(board.run_dir), 'muted')))
        _prune_logs()


def set_phase(name: str) -> None:
    """Name what the current task is doing; outside a board, print it."""
    task = current_task()
    if task is None:
        info(name)
        return
    task.phase = name
    task.activity = ''
    task.log(f'==> {name}')


def note(message: str) -> None:
    """Record a detail line on the current task, or print it outside a board."""
    task = current_task()
    if task is None:
        info(message)
        return
    task.activity = message
    task.log(message)


def skip(reason: str) -> None:
    """Mark the current task as skipped; the caller should then return False."""
    task = current_task()
    if task is None:
        warning(reason)
        return
    task.state, task.phase = 'skipped', reason
    task.log(f'skipped: {reason}')


def _clean(raw: str) -> str:
    segments = [part for part in _ANSI.sub('', raw).split('\r') if part.strip()]
    return segments[-1].rstrip() if segments else ''


def run_command(
    command: str, *, phase: str | None = None,
    retry_on: str | None = None, attempts: int = 1, retry_delay: float = 30.0,
) -> bool:
    """Run a shell command, streaming stdout and stderr into the current task.

    A failed run whose output matches the regex ``retry_on`` is retried, up to
    ``attempts`` runs in all, waiting ``retry_delay`` seconds and doubling it
    each time. Outside a board, the command gets a one-row board of its own.
    """
    task = current_task()
    if task is None:
        label = phase or (command if len(command) <= 60 else command[:57] + '...')
        return run_tasks(label, [(label, lambda: run_command(
            command, phase=phase, retry_on=retry_on, attempts=attempts, retry_delay=retry_delay,
        ))])[label]

    if phase:
        set_phase(phase)
    pattern = re.compile(retry_on) if retry_on else None
    for attempt in range(1, attempts + 1):
        returncode, output = _run_once(task, command)
        if not returncode:
            return True
        if pattern is None or attempt == attempts or not any(pattern.search(line) for line in output):
            return False
        task.activity = f'Transient error; retrying in {retry_delay:.0f}s (attempt {attempt + 1}/{attempts})'
        task.log(task.activity)
        time.sleep(retry_delay)
        retry_delay *= 2
    return False


def _run_once(task: Task, command: str) -> tuple[int, list[str]]:
    task.log(f'$ {command}')
    output = []
    # One merged pipe: reading stdout to EOF before stderr deadlocks once
    # gcloud fills the stderr buffer, and hides its progress until the end.
    # No stdin: a gcloud prompt fails fast instead of hanging behind the board.
    process = subprocess.Popen(
        command, shell=True, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, errors='replace', bufsize=1,
    )
    try:
        for raw in process.stdout:
            line = _clean(raw)
            if line:
                task.activity = line
                task.log(line)
                output.append(line)
    except BaseException:
        # e.g. Ctrl-C: don't leave gcloud running detached from the board.
        process.terminate()
        process.wait()
        raise
    returncode = process.wait()
    if returncode:
        task.log(f'exit status {returncode}')
    return returncode, output


def run_step(command: str, label: str) -> subprocess.CompletedProcess:
    """Run a quick, failure-tolerant command behind a spinner and print one result line."""
    with status(label):
        result = subprocess.run(
            command, capture_output=True, shell=True, text=True, stdin=subprocess.DEVNULL,
        )
    if result.returncode == 0:
        success(label)
    else:
        detail = next((line for line in (result.stderr or '').splitlines() if line.strip()), '')
        warning(f'{label} — {detail}' if detail else label)
    return result


@contextmanager
def status(message: str) -> Iterator[None]:
    """A transient spinner. Inside a board, it updates the task's phase instead."""
    if _active is not None or current_task() is not None:
        set_phase(message)
        yield
        return
    with console.status(Text(message, style='info'), spinner='dots'):
        yield

"""Exercise deployment output streaming with real local child processes."""
import os
import shlex
import subprocess
import sys

from cloud_deployment.operations.app_install_updates.agoge_app import AgogeApp
from cloud_deployment.utilities import console as ui


def python_command(script):
    arguments = [sys.executable, str(script)]
    return subprocess.list2cmdline(arguments) if os.name == 'nt' else shlex.join(arguments)


def run_on_board(command):
    """Run through the task board, as a deployment does; return (result, task log)."""
    tasks = []

    def work():
        tasks.append(ui.current_task())
        return AgogeApp._stream_command_output(command)

    result = ui.run_tasks('Deploy', [('Deploy', work)])['Deploy']
    return result, tasks[0].log_path.read_text()


def test_stderr_larger_than_pipe_capacity_streams_while_stdout_is_open(tmp_path):
    script = tmp_path / 'large deployment output.py'
    script.write_text('''import os
import threading

# Bound a regression without leaving a producer blocked in its stderr pipe.
# Reading stdout to EOF before stderr deadlocks while this stderr write blocks.
watchdog = threading.Timer(10, lambda: os._exit(97))
watchdog.daemon = True
watchdog.start()
for _ in range(256):
    os.write(2, b'deployment-progress:' + b'x' * 1024 + b'\\n')
os.write(1, b'deployment-complete\\n')
watchdog.cancel()
''')

    result, log = run_on_board(python_command(script))
    assert result is True
    assert log.count('deployment-progress:') == 256
    assert 'deployment-complete' in log


def test_failed_command_preserves_both_progress_and_error_and_returns_false(tmp_path):
    script = tmp_path / 'failed deployment.py'
    script.write_text('''import os
import sys
os.write(1, b'creating revision\\n')
os.write(2, b'container startup failed\\n')
sys.exit(2)
''')

    result, log = run_on_board(python_command(script))
    assert result is False
    assert 'creating revision' in log
    assert 'container startup failed' in log

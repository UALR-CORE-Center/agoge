"""Reserve a private local file before issuing a one-time enrollment token."""
from contextlib import contextmanager
import csv
import os
from pathlib import Path
import re
import subprocess
import sys


def _protect_windows(path):
    """Replace inherited access on an empty file with the current user's SID."""
    system_root = os.environ.get('SystemRoot')
    if not system_root:
        raise ValueError('Cannot locate Windows tools to protect the enrollment token file')
    tools = Path(system_root) / 'System32'
    options = {'check': True, 'capture_output': True, 'text': True,
               'errors': 'replace', 'timeout': 15}
    try:
        result = subprocess.run(
            [str(tools / 'whoami.exe'), '/user', '/fo', 'csv', '/nh'], **options)
        rows = list(csv.reader(result.stdout.splitlines()))
        if len(rows) != 1 or len(rows[0]) != 2 or not re.fullmatch(r'S-\d+(?:-\d+)+', rows[0][1]):
            raise ValueError('Cannot identify the current Windows user for token file permissions')
        sid = rows[0][1]
        # /reset removes explicit ACEs. Then remove inherited ACEs and grant
        # only this SID. Both commands run before the file contains a secret.
        subprocess.run([str(tools / 'icacls.exe'), str(path), '/reset', '/q'], **options)
        subprocess.run([str(tools / 'icacls.exe'), str(path), '/inheritance:r',
                        '/grant:r', f'*{sid}:F', '/q'], **options)
    except (OSError, subprocess.SubprocessError, UnicodeError, csv.Error):
        raise ValueError('Could not protect the enrollment token file with a current-user-only Windows ACL') from None


def _protect_file(path, descriptor):
    if sys.platform == 'win32':
        _protect_windows(path)
    else:
        os.fchmod(descriptor, 0o600)


@contextmanager
def enrollment_token_output(path):
    """Yield a one-use token writer, reserving a new protected file first.

    A failure before ``save`` removes the empty reservation. Once saving begins,
    retain the file even if a later operation fails: enrollment may already be
    committed, and the one-time token cannot be fetched again.
    """
    raw = Path(path).expanduser()
    # Resolve only the parent: resolving the final name would follow a dangling
    # symlink before O_EXCL can reject that existing directory entry.
    output = raw.parent.resolve() / raw.name
    try:
        output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                             | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_BINARY', 0), 0o600)
    except FileExistsError:
        raise ValueError(f'Token output already exists; choose a new file: {output}') from None
    except OSError:
        raise ValueError(f'Cannot create enrollment token output: {output}') from None

    active, attempted, saved = True, False, False
    try:
        try:
            _protect_file(output, descriptor)
        except OSError:
            raise ValueError(f'Could not set private permissions for enrollment token output: {output}') from None

        def save(token):
            nonlocal attempted, saved
            if not active:
                raise ValueError('Enrollment token output is already closed')
            if attempted:
                raise ValueError('An enrollment token can be saved only once')
            if not isinstance(token, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', token):
                raise ValueError('Enrollment token must be a nonempty URL-safe string')
            attempted = True
            payload = (token + '\n').encode('ascii')
            try:
                remaining = memoryview(payload)
                while remaining:
                    written = os.write(descriptor, remaining)
                    if written <= 0:
                        raise OSError('Incomplete token write')
                    remaining = remaining[written:]
                os.fsync(descriptor)
            except OSError:
                raise ValueError('Enrollment may have succeeded, but saving its token failed. '
                                 f'The protected output was retained for inspection: {output}') from None
            saved = True

        yield save
        if not saved:
            raise ValueError('No enrollment token was saved')
    finally:
        active = False
        os.close(descriptor)
        if not attempted:
            output.unlink(missing_ok=True)

"""Exercise deployment output streaming with real local child processes."""
import os
import shlex
import subprocess
import sys

from cloud_deployment.operations.app_install_updates.agoge_app import AgogeApp


def python_command(script):
    arguments = [sys.executable, str(script)]
    return subprocess.list2cmdline(arguments) if os.name == 'nt' else shlex.join(arguments)


def test_stderr_larger_than_pipe_capacity_streams_while_stdout_is_open(tmp_path, capsys):
    script = tmp_path / 'large deployment output.py'
    script.write_text('''import os
import threading

# Bound a regression without leaving a producer blocked in its stderr pipe.
# The old implementation waits for stdout EOF while this stderr write blocks.
watchdog = threading.Timer(10, lambda: os._exit(97))
watchdog.daemon = True
watchdog.start()
for _ in range(256):
    os.write(2, b'deployment-progress:' + b'x' * 1024 + b'\\n')
os.write(1, b'deployment-complete\\n')
watchdog.cancel()
''')

    assert AgogeApp._stream_command_output(python_command(script)) is True
    output = capsys.readouterr().out
    assert output.count('deployment-progress:') == 256
    assert output.endswith('deployment-complete\n')


def test_failed_command_preserves_both_progress_and_error_and_returns_false(tmp_path, capsys):
    script = tmp_path / 'failed deployment.py'
    script.write_text('''import os
import sys
os.write(1, b'creating revision\\n')
os.write(2, b'container startup failed\\n')
sys.exit(2)
''')

    assert AgogeApp._stream_command_output(python_command(script)) is False
    output = capsys.readouterr().out
    assert 'creating revision\n' in output
    assert 'container startup failed\n' in output

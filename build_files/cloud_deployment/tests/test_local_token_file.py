"""Private one-time enrollment output, without device or cloud access."""
import os
from pathlib import Path
import stat
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from common.utilities import local_token_file as module


def test_output_is_protected_before_enrollment_and_token_is_flushed(tmp_path, monkeypatch, capsys):
    output = tmp_path / 'nested' / 'peer.token'
    sync = Mock(wraps=os.fsync)
    monkeypatch.setattr(module.os, 'fsync', sync)
    with module.enrollment_token_output(output) as save:
        assert output.exists() and output.read_bytes() == b''
        if os.name != 'nt':
            assert stat.S_IMODE(output.stat().st_mode) == 0o600
        save('one-time-secret')
    assert output.read_bytes() == b'one-time-secret\n'
    sync.assert_called_once()
    assert capsys.readouterr() == ('', '')


def test_existing_output_is_never_overwritten(tmp_path):
    output = tmp_path / 'peer.token'
    output.write_text('existing-secret')
    with pytest.raises(ValueError, match='already exists'):
        with module.enrollment_token_output(output):
            pytest.fail('Enrollment must not run when the output already exists')
    assert output.read_text() == 'existing-secret'


@pytest.mark.skipif(os.name == 'nt', reason='Symlink creation may need Windows developer mode')
@pytest.mark.parametrize('target_exists', [False, True])
def test_output_does_not_follow_a_final_component_symlink(tmp_path, target_exists):
    target = tmp_path / 'target'
    if target_exists:
        target.write_text('existing-secret')
    output = tmp_path / 'peer.token'
    output.symlink_to(target)
    with pytest.raises(ValueError, match='already exists'):
        with module.enrollment_token_output(output):
            pytest.fail('Enrollment must not run for a symlink output')
    assert output.is_symlink()
    if target_exists:
        assert target.read_text() == 'existing-secret'
    else:
        assert not target.exists()


def test_enrollment_failure_removes_empty_reservation_and_allows_retry(tmp_path):
    output = tmp_path / 'peer.token'
    with pytest.raises(RuntimeError, match='Enrollment failed'):
        with module.enrollment_token_output(output):
            raise RuntimeError('Enrollment failed')
    assert not output.exists()
    with module.enrollment_token_output(output) as save:
        save('retry-token')
    assert output.read_text() == 'retry-token\n'


def test_failure_after_save_keeps_the_one_time_token(tmp_path):
    output = tmp_path / 'peer.token'
    with pytest.raises(RuntimeError, match='Later operation failed'):
        with module.enrollment_token_output(output) as save:
            save('retained-token')
            raise RuntimeError('Later operation failed')
    assert output.read_text() == 'retained-token\n'


def test_writer_handles_short_writes_until_the_complete_token_is_stored(tmp_path, monkeypatch):
    output = tmp_path / 'peer.token'
    write = os.write
    monkeypatch.setattr(module.os, 'write', lambda descriptor, payload: write(descriptor, payload[:3]))
    with module.enrollment_token_output(output) as save:
        save('complete-token')
    assert output.read_text() == 'complete-token\n'


def test_failed_save_keeps_protected_output_and_never_exposes_token_in_error(tmp_path, monkeypatch):
    output = tmp_path / 'peer.token'
    monkeypatch.setattr(module.os, 'fsync', Mock(side_effect=OSError('private-token-in-device-error')))
    with pytest.raises(ValueError, match='retained for inspection') as error:
        with module.enrollment_token_output(output) as save:
            save('retained-token')
    assert output.read_text() == 'retained-token\n'
    assert 'retained-token' not in str(error.value)
    assert 'private-token-in-device-error' not in str(error.value)


def test_output_without_save_is_an_error_and_removes_reservation(tmp_path):
    output = tmp_path / 'peer.token'
    with pytest.raises(ValueError, match='No enrollment token'):
        with module.enrollment_token_output(output):
            pass
    assert not output.exists()


def test_writer_is_one_use_and_cannot_be_used_after_context_exits(tmp_path):
    output = tmp_path / 'peer.token'
    with pytest.raises(ValueError, match='only once'):
        with module.enrollment_token_output(output) as save:
            save('first-token')
            save('second-token')
    assert output.read_text() == 'first-token\n'
    with pytest.raises(ValueError, match='already closed'):
        save('late-token')
    assert output.read_text() == 'first-token\n'


def test_permission_failure_removes_file_before_enrollment_can_run(tmp_path, monkeypatch):
    output = tmp_path / 'peer.token'
    monkeypatch.setattr(module, '_protect_file', Mock(side_effect=ValueError('Permissions failed')))
    with pytest.raises(ValueError, match='Permissions failed'):
        with module.enrollment_token_output(output):
            pytest.fail('Enrollment must not run before permissions are protected')
    assert not output.exists()


def test_permission_os_error_is_actionable_and_removes_the_empty_file(tmp_path, monkeypatch):
    output = tmp_path / 'peer.token'
    monkeypatch.setattr(module, '_protect_file', Mock(side_effect=OSError('private-device-error')))
    with pytest.raises(ValueError, match='private permissions') as error:
        with module.enrollment_token_output(output):
            pytest.fail('Enrollment must not run before permissions are protected')
    assert not output.exists()
    assert 'private-device-error' not in str(error.value)


def test_windows_acl_commands_use_numeric_current_user_sid_before_secret_write(tmp_path, monkeypatch):
    output = tmp_path / 'peer token.txt'
    output.write_bytes(b'')
    monkeypatch.setenv('SystemRoot', '/windows')
    sid = 'S-1-5-21-1-2-3-1001'
    commands = []

    def run(arguments, **options):
        assert output.read_bytes() == b''
        assert options['check'] and options['capture_output']
        assert 'shell' not in options
        commands.append(arguments)
        return SimpleNamespace(stdout=f'"DOMAIN\\user","{sid}"\n')

    monkeypatch.setattr(module.subprocess, 'run', run)
    module._protect_windows(output)
    system_tools = Path('/windows') / 'System32'
    assert commands == [
        [str(system_tools / 'whoami.exe'), '/user', '/fo', 'csv', '/nh'],
        [str(system_tools / 'icacls.exe'), str(output), '/reset', '/q'],
        [str(system_tools / 'icacls.exe'), str(output), '/inheritance:r', '/grant:r', f'*{sid}:F', '/q'],
    ]


@pytest.mark.parametrize('stdout', ['', '"user","not-a-sid"', '"user","S-1-5-1"\n"other","S-1-5-2"'])
def test_windows_acl_fails_closed_when_identity_cannot_be_read(tmp_path, monkeypatch, stdout):
    monkeypatch.setenv('SystemRoot', '/windows')
    run = Mock(return_value=SimpleNamespace(stdout=stdout))
    monkeypatch.setattr(module.subprocess, 'run', run)
    with pytest.raises(ValueError, match='identify the current Windows user'):
        module._protect_windows(tmp_path / 'peer.token')
    run.assert_called_once()


def test_windows_acl_failure_does_not_echo_subprocess_output(tmp_path, monkeypatch):
    monkeypatch.setenv('SystemRoot', '/windows')
    run = Mock(side_effect=[
        SimpleNamespace(stdout='"user","S-1-5-21-1001"'),
        subprocess.CalledProcessError(1, ['icacls'], output='private-error-output'),
    ])
    monkeypatch.setattr(module.subprocess, 'run', run)
    with pytest.raises(ValueError, match='current-user-only Windows ACL') as error:
        module._protect_windows(tmp_path / 'peer.token')
    assert 'private-error-output' not in str(error.value)

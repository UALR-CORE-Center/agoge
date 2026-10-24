"""Safe failure locations retain useful app frames without SDK payloads."""
import json
from pathlib import Path

from google.api_core.exceptions import InvalidArgument
import pytest

from tools.debug_lab.errors import safe_error_trace


ROOT = Path(__file__).resolve().parents[3]


def test_nested_google_error_reports_locations_without_messages_source_or_locals(capsys):
    def grant():
        private_key = 'private-local-key'
        response = {'payload': 'private-response-value'}
        error = InvalidArgument('private-sdk-message')
        error.private_request = {'token': 'private-request-token'}
        raise error

    def prepare():
        grant()

    try:
        prepare()
    except InvalidArgument as error:
        trace = safe_error_trace(error, ROOT)

    assert [frame['function'] for frame in trace[-2:]] == ['prepare', 'grant']
    assert trace[-1]['file'] == 'build_files/cloud_deployment/tests/test_debug_error_trace.py'
    assert all(set(frame) == {'file', 'line', 'function'} for frame in trace)
    assert all(type(frame['line']) is int and frame['line'] > 0 for frame in trace)
    output = json.dumps(trace)
    assert str(ROOT) not in output
    for private in ('private-local-key', 'private-response-value', 'private-sdk-message',
                    'private-request-token', 'raise error', 'private_request'):
        assert private not in output
    captured = capsys.readouterr()
    assert captured.out == captured.err == ''


def execute_with_filename(source, filename, namespace=None):
    namespace = {} if namespace is None else namespace
    exec(compile(source, str(filename), 'exec'), namespace)
    return namespace


@pytest.mark.parametrize('outside_path', [
    'sdk/request.py', 'repo-sibling/request.py',
    'repo/venv/Lib/site-packages/sdk/request.py',
    'repo/VeNv/Lib/request.py',
    'repo/.env/Lib/request.py',
    'repo/.venv/lib/python3.12/site-packages/sdk/request.py',
    'repo/vendor/site-packages/sdk/request.py',
    'repo/vendor/dist-packages/sdk/request.py',
])
def test_external_or_virtual_environment_frames_are_omitted(tmp_path, outside_path):
    root = tmp_path / 'repo'
    sdk = execute_with_filename(
        "def request():\n    raise ValueError('private-sdk-body')\n",
        tmp_path / outside_path)
    app = execute_with_filename('def grant():\n    request()\n', root / 'common/grant.py', sdk)
    try:
        app['grant']()
    except ValueError as error:
        trace = safe_error_trace(error, root)
    assert trace == [{'file': 'common/grant.py', 'line': 2, 'function': 'grant'}]


def test_only_the_last_eight_app_frames_are_retained_in_call_order(tmp_path):
    source = ''.join(f'def step_{index}():\n    step_{index + 1}()\n' for index in range(11))
    source += "def step_11():\n    raise RuntimeError('private-sdk-body')\n"
    app = execute_with_filename(source, tmp_path / 'common/provision.py')
    try:
        app['step_0']()
    except RuntimeError as error:
        trace = safe_error_trace(error, tmp_path)
    assert [frame['function'] for frame in trace] == [f'step_{index}' for index in range(4, 12)]
    assert len(trace) == 8


def test_error_without_a_traceback_has_no_locations():
    assert safe_error_trace(InvalidArgument('private-sdk-body'), ROOT) == []


def test_virtual_code_filenames_are_not_treated_as_repository_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = execute_with_filename("def run():\n    raise RuntimeError('private-body')\n", '<string>')
    try:
        app['run']()
    except RuntimeError as error:
        assert safe_error_trace(error, tmp_path) == []

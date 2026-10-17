import shlex
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from cloud_deployment.operations.app_install_updates import agoge_app as app_module
from cloud_deployment.operations.app_install_updates import base_build as base_build_module
from cloud_deployment.operations.app_install_updates.agoge_app import AgogeApp, Commands
from cloud_deployment.operations.app_install_updates.base_build import BaseBuild
from cloud_deployment.utilities import console as ui
from cloud_deployment.utilities.globals import ShellCommands


def test_tasks_run_concurrently():
    # Each task waits for the other; run serially, the barrier times out.
    barrier = threading.Barrier(2, timeout=5)
    results = ui.run_tasks('Both', [('A', lambda: barrier.wait() >= 0), ('B', lambda: barrier.wait() >= 0)])
    assert results == {'A': True, 'B': True}


def test_task_exception_is_raised_after_every_task_finishes():
    finished = []

    def slow():
        finished.append('slow')
        return True

    with pytest.raises(RuntimeError, match='boom'):
        ui.run_tasks('Mixed', [('Bad', MagicMock(side_effect=RuntimeError('boom'))), ('Slow', slow)])
    assert finished == ['slow']


def test_task_exception_is_shown_in_its_log():
    tasks = []

    def work():
        tasks.append(ui.current_task())
        raise ValueError('quota exceeded')

    with pytest.raises(ValueError):
        ui.run_tasks('Raise', [('Raise', work)])
    assert 'ValueError: quota exceeded' in tasks[0].tail


def test_commands_cannot_block_on_a_prompt():
    assert ui.run_tasks('Prompt', [('Prompt', lambda: ui.run_command('read answer'))]) == {'Prompt': False}


def test_command_output_merges_stderr_into_the_task_log():
    tasks = []

    def work():
        tasks.append(ui.current_task())
        return ui.run_command('echo out; echo err >&2; exit 3', phase='Probe')

    assert ui.run_tasks('Probe', [('Probe', work)]) == {'Probe': False}
    log = tasks[0].log_path.read_text()
    assert 'out' in log and 'err' in log and 'exit status 3' in log
    assert tasks[0].state == 'failed'


@pytest.fixture
def app(monkeypatch, tmp_path):
    env = SimpleNamespace(project='tenant-project', project_number='123', region='us-east1')
    monkeypatch.setattr(app_module, 'CloudEnv', MagicMock(return_value=env))
    monkeypatch.setattr(app_module.discovery, 'build', MagicMock())
    monkeypatch.setattr(app_module, 'prepare_firebase_auth', MagicMock())
    monkeypatch.setattr(app_module, 'ensure_shared_api_secret_access', MagicMock())
    result = AgogeApp(project='tenant-project')
    result._write_env_files = MagicMock()
    result.fastapi_env_file = tmp_path / 'api.env'
    result.react_vite_env_file = tmp_path / '.env.production'
    return result


def test_react_is_built_but_not_deployed_when_the_api_fails(app):
    app._deploy_api = MagicMock(return_value=False)
    commands = []
    app._stream_command_output = MagicMock(side_effect=lambda command, **_: commands.append(command) or True)

    assert app.deploy_main_app(targets=(Commands.AppType.API, Commands.AppType.REACT)) is False

    assert [c.split()[:3] for c in commands] == [['gcloud', 'builds', 'submit']]


def test_react_deploys_after_the_api_succeeds(app):
    api_done = threading.Event()
    app._deploy_api = MagicMock(side_effect=lambda **_: api_done.set() or True)
    deployed_after_api = []

    def stream(command, **_):
        if command.startswith('gcloud run deploy'):
            deployed_after_api.append(api_done.is_set())
        return True

    app._stream_command_output = MagicMock(side_effect=stream)
    assert app.deploy_main_app(targets=(Commands.AppType.API, Commands.AppType.REACT)) is True
    assert deployed_after_api == [True]


@pytest.mark.parametrize('function_ok', [True, False])
def test_cloud_function_deploys_on_the_same_board(app, function_ok):
    app._deploy_api = MagicMock(return_value=True)
    app.deploy_cloud_functions = MagicMock(return_value=function_ok)

    assert app.deploy_main_app(targets=(Commands.AppType.API,), with_cloud_function=True) is function_ok
    # Secret access is granted once, before the concurrent tasks start.
    app_module.ensure_shared_api_secret_access.assert_called_once_with(app.env)
    app._deploy_api.assert_called_once_with(preflight=False)
    app.deploy_cloud_functions.assert_called_once()
    assert app.deploy_cloud_functions.call_args.kwargs['preflight'] is False


def test_staging_is_per_app_and_drops_tests_but_keeps_env(app, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for directory in ('api', 'cloud_functions', 'common'):
        (tmp_path / directory / 'tests').mkdir(parents=True)
        (tmp_path / directory / '__pycache__').mkdir()
        (tmp_path / directory / 'main.py').write_text('')
    (tmp_path / 'api' / '.env').write_text('DEVELOPMENT=false\n')

    api = app._stage_build(Commands.AppType.API)
    function = app._stage_build(Commands.AppType.CLOUD_FN)

    assert api != function and api.exists() and function.exists()
    assert (api / '.env').exists() and (api / 'main.py').exists() and (api / 'common' / 'main.py').exists()
    for staged in (api, function, api / 'common'):
        assert not (staged / 'tests').exists() and not (staged / '__pycache__').exists()
    app._remove_staging(api)
    app._remove_staging(function)
    assert not api.exists() and not function.exists()
    app._remove_empty_staging_root()
    assert not app.staging_dir.exists()


def test_function_deploys_from_its_own_staging_dir(app):
    command = shlex.split(app.commands.deploy_cloud_function())
    assert '--source=./.staging/cloud_fn/' in command


@pytest.mark.parametrize('app_type, config', [('api', 'cached_image.yaml'), ('react', 'cached_multistage_image.yaml')])
def test_cloud_build_uses_the_layer_cache_config(app, app_type, config):
    command = shlex.split(app.commands.build_cloud_run(app_type, 'frontend/'))
    config_path = next(arg.split('=', 1)[1] for arg in command if arg.startswith('--config='))
    assert config_path.endswith(config)
    assert app_module.Path(config_path).exists()
    assert f'--substitutions=_IMAGE=gcr.io/tenant-project/agoge-{app_type}' in command


def test_all_apis_are_enabled_in_one_deduplicated_call(monkeypatch):
    build = object.__new__(BaseBuild)
    build.project = 'tenant-project'
    run = MagicMock(return_value=SimpleNamespace(returncode=0, stderr=''))
    monkeypatch.setattr(base_build_module.subprocess, 'run', run)

    build._enable_apis()

    run.assert_called_once()
    services = shlex.split(run.call_args.args[0])[3:-1]
    assert len(services) == len(set(services))
    assert set(services) == {item.value.split()[-1] for item in ShellCommands.EnableAPIs}


@pytest.mark.parametrize('api_ok', [True, False])
def test_cloud_function_goes_live_only_after_the_api_succeeds(app, monkeypatch, api_ok):
    api_done = threading.Event()
    app._deploy_api = MagicMock(side_effect=lambda **_: api_done.set() or api_ok)
    app._stage_build = MagicMock(return_value=app_module.Path('.staging/cloud_fn'))
    app._set_scheduler = MagicMock(return_value=True)
    function_deploys = []

    def stream(command, **_):
        if command.startswith('gcloud functions deploy'):
            function_deploys.append(api_done.is_set())
        return True

    app._stream_command_output = MagicMock(side_effect=stream)
    result = app.deploy_main_app(targets=(Commands.AppType.API,), with_cloud_function=True)

    assert result is api_ok
    assert function_deploys == ([True] if api_ok else [])


def test_cloud_function_does_not_wait_when_the_api_is_not_deployed(app):
    app._deploy_react = MagicMock(return_value=True)
    app.deploy_cloud_functions = MagicMock(return_value=True)

    assert app.deploy_main_app(targets=(Commands.AppType.REACT,), with_cloud_function=True) is True
    assert app.deploy_cloud_functions.call_args.kwargs['wait_for'] is None

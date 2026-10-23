import shlex
from types import SimpleNamespace

from cloud_deployment.operations.app_install_updates.agoge_app import Commands

ENV = SimpleNamespace(project='test-dev-787001', region='us-central1', project_number='123')


def _probe(command):
    return [arg for arg in shlex.split(command) if arg.startswith('--startup-probe=')]


def test_api_deploy_probes_the_health_path_over_http():
    command = Commands(ENV).deploy_cloud_run('api', 'gcr.io/test-dev-787001/agoge-api', min_instance=True)

    [probe] = _probe(command)
    settings = dict(item.split('=', 1) for item in probe.removeprefix('--startup-probe=').split(','))
    assert settings['httpGet.path'] == '/health/ready'
    assert settings['httpGet.port'] == '8080'
    # Cloud Run allows at most 240 s of startup probing.
    assert int(settings['periodSeconds']) * int(settings['failureThreshold']) <= 240
    assert '--min-instances=1' in shlex.split(command)


def test_react_deploy_keeps_the_default_probe():
    assert _probe(Commands(ENV).deploy_cloud_run('react', 'gcr.io/test-dev-787001/agoge-react')) == []

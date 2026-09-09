import shlex
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from cloud_deployment.operations.app_install_updates import agoge_app as app_module
from cloud_deployment.operations.app_install_updates import install_update_manager as install_module
from cloud_deployment import setup_manager as setup_manager_module
from cloud_deployment.utilities.menu_options import SetupCategories, SetupOptions, category_menu


@pytest.fixture
def installation(monkeypatch):
    calls = []
    base = MagicMock()
    base.run.side_effect = lambda: calls.append("base")
    base.ensure_wireguard_prerequisites.side_effect = lambda: calls.append("preflight")
    app = MagicMock()
    app.deploy_main_app.side_effect = lambda: calls.append("apps") or True
    app.deploy_cloud_functions.side_effect = lambda: calls.append("function") or True
    routing = MagicMock()
    routing.run.side_effect = lambda: calls.append("routing") or True
    guacamole = MagicMock()
    guacamole.create_guac_project_image.side_effect = lambda: calls.append("guacamole")
    shared_labs = MagicMock()
    shared_labs.run.side_effect = lambda: calls.append("labs")
    constructors = {}
    for name, instance in (
        ("BaseBuild", base), ("AgogeApp", app), ("SharedLoadBalancer", routing),
        ("GuacamoleImageManager", guacamole), ("SharedLabManager", shared_labs),
    ):
        constructors[name] = MagicMock(return_value=instance)
        monkeypatch.setattr(install_module, name, constructors[name])
    manager = install_module.InstallUpdateManager("selected-tenant")
    manager._create_update_record = MagicMock(side_effect=lambda **kwargs: calls.append("record"))
    return SimpleNamespace(
        manager=manager, calls=calls, app=app, routing=routing, constructors=constructors,
    )


@pytest.mark.parametrize("method, expected, action", [
    ("run_full_install", ["base", "apps", "function", "routing", "guacamole", "labs", "record"], "initial install"),
    ("run_update", ["preflight", "apps", "function", "routing", "record"], "update"),
])
def test_installation_routes_after_deployments_before_recording_success(installation, method, expected, action):
    getattr(installation.manager, method)()

    assert installation.calls == expected
    installation.constructors["AgogeApp"].assert_called_once_with(project="selected-tenant")
    installation.constructors["SharedLoadBalancer"].assert_called_once_with(project="selected-tenant")
    installation.manager._create_update_record.assert_called_once_with(action=action)


@pytest.mark.parametrize("method", ["run_full_install", "run_update"])
@pytest.mark.parametrize("failure", ["apps", "function", "routing"])
def test_failed_or_deferred_installation_stops_later_steps(installation, method, failure, capsys):
    step = {
        "apps": installation.app.deploy_main_app,
        "function": installation.app.deploy_cloud_functions,
        "routing": installation.routing.run,
    }[failure]
    step.side_effect = lambda: installation.calls.append(failure) or False

    getattr(installation.manager, method)()

    sequence = ["apps", "function", "routing"]
    prerequisite = "base" if method == "run_full_install" else "preflight"
    assert installation.calls == [prerequisite] + sequence[:sequence.index(failure) + 1]
    installation.manager._create_update_record.assert_not_called()
    installation.constructors["GuacamoleImageManager"].assert_not_called()
    installation.constructors["SharedLabManager"].assert_not_called()
    assert "Setup complete" not in capsys.readouterr().out


def test_standalone_routing_menu_uses_selected_project_without_deploying(monkeypatch):
    routing = MagicMock()
    app = MagicMock()
    monkeypatch.setattr(setup_manager_module, "SharedLoadBalancer", routing)
    monkeypatch.setattr(setup_manager_module, "AgogeApp", app)

    setup_manager_module.SetupManager(SetupOptions.SHARED_LOAD_BALANCER, "selected-tenant").run()

    routing.assert_called_once_with(project="selected-tenant")
    routing.return_value.run.assert_called_once_with()
    app.assert_not_called()
    options = [option for option, _ in category_menu[SetupCategories.APP_INSTALL_UPDATES]["options"]]
    assert SetupOptions.SHARED_LOAD_BALANCER in options


@pytest.mark.parametrize("option, method", [
    (SetupOptions.CLOUD_FUNCTION, "deploy_cloud_functions"),
    (SetupOptions.MAIN_APP, "deploy_main_app"),
])
@pytest.mark.parametrize("success", [False, True])
def test_individual_deployments_check_routing_only_after_success(monkeypatch, option, method, success):
    order = []
    app = MagicMock()
    getattr(app.return_value, method).side_effect = lambda: order.append("deploy") or success
    routing = MagicMock()
    routing.return_value.run.side_effect = lambda: order.append("routing") or True
    monkeypatch.setattr(setup_manager_module, "AgogeApp", app)
    monkeypatch.setattr(setup_manager_module, "SharedLoadBalancer", routing)

    setup_manager_module.SetupManager(option, "selected-tenant").run()

    app.assert_called_once_with(project="selected-tenant")
    getattr(app.return_value, method).assert_called_once_with()
    assert order == (["deploy", "routing"] if success else ["deploy"])
    if success:
        routing.assert_called_once_with(project="selected-tenant")
    else:
        routing.assert_not_called()


@pytest.fixture
def scoped_app(monkeypatch):
    env = SimpleNamespace(project="selected-tenant", project_number="123456", region="us-east1")
    environment = MagicMock(return_value=env)
    monkeypatch.setattr(app_module, "CloudEnv", environment)
    monkeypatch.setattr(app_module.discovery, "build", MagicMock())
    app = app_module.AgogeApp(False, project="selected-tenant")
    environment.assert_called_once_with(project="selected-tenant")
    assert app.suppress is False
    return app


@pytest.mark.parametrize("app_type", ["api", "react"])
def test_cloud_run_build_and_deployment_target_selected_project(scoped_app, app_type):
    image = scoped_app.commands.image_path(app_type)
    build = scoped_app.commands.build_cloud_run(app_type, "frontend/")
    deploy = scoped_app.commands.deploy_cloud_run(app_type, image)

    assert image == f"gcr.io/selected-tenant/agoge-{app_type}"
    for command in (build, deploy):
        assert shlex.split(command).count("--project=selected-tenant") == 1
        assert "gcloud config" not in command
    assert "--region=us-east1" in shlex.split(deploy)
    assert "@selected-tenant.iam.gserviceaccount.com" in deploy


def test_function_deployment_targets_selected_project(scoped_app):
    command = shlex.split(scoped_app.commands.deploy_cloud_function())

    assert "--project=selected-tenant" in command
    assert "--region=us-east1" in command
    assert "--run-service-account=agoge-service@selected-tenant.iam.gserviceaccount.com" in command


@pytest.mark.parametrize("success", [False, True])
def test_scheduler_targets_selected_project_and_region_and_reports_failure(scoped_app, success):
    jobs = scoped_app.service.projects.return_value.locations.return_value.jobs.return_value
    jobs.list.return_value.execute.return_value = {"jobs": []}
    scoped_app._stream_command_output = MagicMock(return_value=success)

    assert scoped_app._set_scheduler() is success

    jobs.list.assert_called_once_with(parent="projects/selected-tenant/locations/us-east1")
    command = shlex.split(scoped_app._stream_command_output.call_args.args[0])
    assert "--project=selected-tenant" in command
    assert "--location=us-east1" in command


def test_existing_scheduler_is_reused(scoped_app):
    jobs = scoped_app.service.projects.return_value.locations.return_value.jobs.return_value
    jobs.list.return_value.execute.return_value = {"jobs": [{"name": scoped_app.job_name}]}
    scoped_app._stream_command_output = MagicMock()

    assert scoped_app._set_scheduler() is True

    scoped_app._stream_command_output.assert_not_called()


def test_scheduler_failure_prevents_successful_function_deployment(scoped_app, monkeypatch):
    monkeypatch.setattr(app_module, "ensure_shared_api_secret_access", MagicMock())
    scoped_app._stream_command_output = MagicMock(return_value=True)
    scoped_app._stage_build = MagicMock()
    scoped_app._set_scheduler = MagicMock(return_value=False)

    assert scoped_app.deploy_cloud_functions() is False

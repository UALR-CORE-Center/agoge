from threading import Barrier
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from cloud_deployment.operations.project_maintenance import (
    rebuild_guacamole_for_project as maintenance,
)
from cloud_deployment.utilities.menu_options import (
    PROJECT_MAINTENANCE_REGISTRY,
    ProjectMaintenanceOptions,
)
from common.constants.database import DATABASE_NAME, DatabaseTypes, DbCollections
from common.constants.states import ServerStates, UnitStates, WorkoutStates


PROJECT = "agoge-test-project"
PROXY = "display-guacamole-server"


@pytest.fixture
def project(monkeypatch):
    documents = {
        DbCollections.SERVER: {},
        DbCollections.UNIT: {},
        DbCollections.WORKOUT: {},
    }
    db = Mock()
    db.get.side_effect = lambda collection_name, doc_id: documents[collection_name].get(doc_id, {})
    db.query.side_effect = lambda collection_name, **kwargs: list(documents[collection_name].values())
    database_factory = Mock(return_value=db)
    monkeypatch.setattr(maintenance.DocumentDatabaseFactory, "create_db_object", database_factory)
    env = {"project": PROJECT}
    environment_factory = Mock(return_value=SimpleNamespace(project=PROJECT, get_env=lambda: env))
    monkeypatch.setattr(maintenance, "CloudEnv", environment_factory)
    monkeypatch.setattr(maintenance.time, "sleep", Mock())
    manager_factory = Mock()
    monkeypatch.setattr(maintenance.ComputeManagerFactory, "create_manager_object", manager_factory)
    return SimpleNamespace(
        db=db,
        documents=documents,
        database_factory=database_factory,
        environment_factory=environment_factory,
        env=env,
        manager_factory=manager_factory,
    )


def _unit(project, unit_id, *, unit_type="solo", state=UnitStates.READY):
    project.documents[DbCollections.UNIT][unit_id] = {
        "id": unit_id,
        "unit_type": unit_type,
        "state": state.value,
    }


def _workout(project, workout_id, unit_id, *, state=WorkoutStates.READY):
    project.documents[DbCollections.WORKOUT][workout_id] = {
        "id": workout_id,
        "parent_id": unit_id,
        "parent_build_type": "unit",
        "build_type": "workout",
        "state": state.value,
    }


def _server(project, parent_id, name=PROXY, *, state=ServerStates.RUNNING, **fields):
    server_id = f"{parent_id}-{name}"
    project.documents[DbCollections.SERVER][server_id] = {
        "parent_id": parent_id,
        "parent_build_type": "workout",
        "name": name,
        "image": "image-linux-test",
        "state": state.value,
        **fields,
    }
    return server_id


def _mock_manager_factory(project, *, on_nuke=lambda _: None, image_status="READY"):
    created = []

    def new_manager(**kwargs):
        manager = Mock()
        manager.get_boot_image.return_value = SimpleNamespace(status=image_status)

        def load(server_name, **kwargs):
            manager.server_name = server_name
            manager.state_manager.get_state.return_value = project.documents[DbCollections.SERVER][server_name]["state"]

        def nuke():
            on_nuke(manager.server_name)
            manager.state_manager.get_state.return_value = ServerStates.RUNNING.value

        def stop():
            manager.state_manager.get_state.return_value = ServerStates.STOPPED.value

        manager.load.side_effect = load
        manager.nuke.side_effect = nuke
        manager.stop.side_effect = stop
        created.append(manager)
        return manager

    project.manager_factory.side_effect = new_manager
    return created


def test_project_repairs_servers_concurrently_and_continues_after_a_failure(project, monkeypatch, capsys):
    _unit(project, "solo-unit")
    _workout(project, "running-workout", "solo-unit", state=WorkoutStates.RUNNING)
    _workout(project, "stopped-workout", "solo-unit")
    running_id = _server(project, "running-workout")
    stopped_id = _server(project, "stopped-workout", state=ServerStates.STOPPED)
    rendezvous = Barrier(2, timeout=5)

    def repair(server_id):
        rendezvous.wait()
        if server_id == running_id:
            raise RuntimeError("simulated compute failure")

    managers = _mock_manager_factory(project, on_nuke=repair)
    monkeypatch.setattr("builtins.input", lambda _: "REBUILD")

    maintenance.RebuildGuacamoleForProject(project=PROJECT).run()

    assert not rendezvous.broken
    assert len(managers) == 2
    by_server = {manager.server_name: manager for manager in managers}
    assert set(by_server) == {running_id, stopped_id}
    assert by_server[running_id] is not by_server[stopped_id]
    by_server[running_id].nuke.assert_called_once_with()
    by_server[running_id].stop.assert_not_called()
    by_server[stopped_id].nuke.assert_called_once_with()
    by_server[stopped_id].stop.assert_called_once_with()
    project.database_factory.assert_called_once_with(
        db_type=DatabaseTypes.firestore,
        database_name=DATABASE_NAME,
        project_id=PROJECT,
    )
    project.environment_factory.assert_called_once_with(project=PROJECT)
    assert all(call.kwargs["env_dict"] == project.env for call in project.manager_factory.call_args_list)
    output = capsys.readouterr().out
    assert "simulated compute failure" in output
    assert running_id in output
    assert "1 rebuilt, 0 skipped, 1 failed" in output


def test_project_discovers_legacy_and_community_proxies_only_in_eligible_labs(project, monkeypatch):
    _unit(project, "community", unit_type="community", state=UnitStates.RUNNING)
    _unit(project, "retired", state=UnitStates.DELETED)
    _workout(project, "legacy", "community", state=WorkoutStates.RUNNING)
    _workout(project, "deleted", "community", state=WorkoutStates.DELETED)
    shared_id = _server(
        project,
        "community",
        "remote-desktop",
        parent_build_type="unit",
        community_server=True,
        image=f"projects/{PROJECT}/global/images/image-guac-{PROJECT}",
    )
    legacy_id = _server(project, "legacy", "display-guacamole", parent_build_type=None)
    script_id = _server(
        project,
        "community",
        "custom-proxy",
        parent_build_type="unit",
        community_server=True,
        guacamole_startup_script="#!/bin/bash\ntrue",
    )
    _server(project, "legacy", "workstation-display-guacamole-mock")
    _server(project, "deleted")
    _server(project, "orphan")
    _server(project, "retired", parent_build_type="unit")
    _server(
        project, "community", "guac-builder",
        parent_build_type="image", image=f"image-guac-{PROJECT}",
    )
    _server(
        project,
        "community",
        "wireguard-gateway",
        parent_build_type="unit",
        community_server=True,
        image=f"image-guac-{PROJECT}",
        wireguard_gateway=True,
    )
    _server(project, "community", state=ServerStates.DELETING, parent_build_type="unit")
    records = list(project.documents[DbCollections.SERVER].values())
    project.db.query.side_effect = None
    project.db.query.return_value = [*records, project.documents[DbCollections.SERVER][shared_id]]
    managers = _mock_manager_factory(project)
    monkeypatch.setattr("builtins.input", lambda _: "REBUILD")

    maintenance.RebuildGuacamoleForProject(project=PROJECT).run()

    assert len(managers) == 3
    by_server = {manager.server_name: manager for manager in managers}
    assert set(by_server) == {shared_id, legacy_id, script_id}
    assert by_server[legacy_id].load.call_args.kwargs["network_prefix"] == "community"
    for manager in managers:
        manager.nuke.assert_called_once_with()
        manager.stop.assert_not_called()
    project.db.query.assert_called_once_with(collection_name=DbCollections.SERVER)


def test_project_requires_confirmation_before_any_rebuild(project, monkeypatch, capsys):
    _unit(project, "unit")
    _workout(project, "workout", "unit")
    _server(project, "workout")
    answer = Mock(return_value="")
    monkeypatch.setattr("builtins.input", answer)

    maintenance.RebuildGuacamoleForProject(project=PROJECT).run()

    assert answer.call_count == 1
    assert PROJECT in capsys.readouterr().out
    project.manager_factory.assert_not_called()


def test_project_rechecks_owners_after_confirmation(project, monkeypatch):
    _unit(project, "retiring-unit")
    _workout(project, "retiring-workout", "retiring-unit")
    _server(project, "retiring-workout")
    _unit(project, "active-unit")
    _workout(project, "active-workout", "active-unit")
    active_id = _server(project, "active-workout")
    managers = _mock_manager_factory(project)

    def confirm(_):
        project.documents[DbCollections.UNIT]["retiring-unit"]["state"] = UnitStates.DELETING_SERVERS.value
        return "REBUILD"

    monkeypatch.setattr("builtins.input", confirm)

    maintenance.RebuildGuacamoleForProject(project=PROJECT).run()

    assert [manager.server_name for manager in managers] == [active_id]


def test_project_leaves_the_current_vm_in_place_if_the_boot_image_is_unready(project, monkeypatch, capsys):
    _unit(project, "unit")
    _workout(project, "workout", "unit", state=WorkoutStates.RUNNING)
    server_id = _server(project, "workout", image="image-guac-renewed")
    managers = _mock_manager_factory(project, image_status="PENDING")
    monkeypatch.setattr("builtins.input", lambda _: "REBUILD")

    maintenance.RebuildGuacamoleForProject(project=PROJECT).run()

    (manager,) = managers
    assert manager.server_name == server_id
    manager.get_boot_image.assert_called_once_with()
    manager.nuke.assert_not_called()
    assert "0 rebuilt, 0 skipped, 1 failed" in capsys.readouterr().out


def test_project_maintenance_keeps_unit_repair_and_registers_project_repair():
    assert PROJECT_MAINTENANCE_REGISTRY[0]["option"] == ProjectMaintenanceOptions.REIMAGE_GUACAMOLE
    project_repair, back = PROJECT_MAINTENANCE_REGISTRY[-2:]
    assert project_repair["operation_class"] is maintenance.RebuildGuacamoleForProject
    assert project_repair["operation_class"].REQUIRES_PROJECT
    assert back["option"] == ProjectMaintenanceOptions.BACK

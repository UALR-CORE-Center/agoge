from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from common.models.agoge import CatalogEditModel, CatalogModel, UnitModel
from core.unit import Unit
from routers import unit as routes


SPEC = {
    "id": "abcdefghij",
    "version": "1.0.0",
    "build_type": "unit",
    "discriminator": "test",
    "instructor_id": ["instructor@example.com"],
    "summary": {"name": "Test lab", "description": "A lab without rubric configuration."},
}


@pytest.mark.parametrize("settings,expected", [({}, False), ({"rubric_support": False}, False), ({"rubric_support": True}, True)])
@pytest.mark.parametrize("global_flag", [False, True])
def test_full_unit_uses_lab_setting_instead_of_deployment_flag(monkeypatch, settings, expected, global_flag):
    handler = MagicMock()
    handler.get_all_data.return_value = {
        "unit": UnitModel(**SPEC, **settings), "workouts": [], "roster": 0,
    }
    monkeypatch.setattr(routes, "Unit", MagicMock(return_value=handler))
    app = FastAPI()
    app.include_router(routes.unit_router)
    app.dependency_overrides[routes.get_cloud_env] = lambda: {"rubric_support": global_flag}
    app.dependency_overrides[routes.teacher_required] = lambda: SimpleNamespace(uid="test-instructor")

    with TestClient(app) as client:
        response = client.get(f"/units/{SPEC['id']}/full/")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["rubric_support"] is expected
    assert data["unit"]["rubric_support"] is expected


@pytest.mark.parametrize("settings,expected", [({}, False), ({"rubric_support": False}, False), ({"rubric_support": True}, True)])
def test_opt_in_survives_specification_models_and_lab_build(settings, expected):
    edit = CatalogEditModel(**SPEC, **settings, edit_id="test-edit")
    catalog = CatalogModel(**edit.model_dump())
    assert catalog.rubric_support is expected

    handler = Unit.__new__(Unit)
    handler.logger = MagicMock()
    handler.db = MagicMock()
    # Cover old persisted specifications that do not have the new field at all.
    handler.db.get.return_value = {**SPEC, **settings}
    handler.commit = MagicMock()

    build_id = handler.build(
        requester=SimpleNamespace(uid="test-instructor", email="instructor@example.com"),
        data={"build_file": SPEC["id"], "expires": "2099-01-01T00:00:00Z", "rubric_support": True},
    )

    unit = handler.commit.call_args.args[0]
    assert unit.id == build_id
    # A build request cannot enable rubrics if the saved specification did not.
    assert unit.model_dump()["rubric_support"] is expected


@pytest.mark.parametrize("model", [UnitModel, CatalogModel, CatalogEditModel])
def test_specifications_require_a_boolean_opt_in(model):
    with pytest.raises(ValidationError):
        model(**SPEC, edit_id="test-edit", rubric_support="true")


def test_storing_openai_key_does_not_enable_rubrics(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "build_files"))
    from cloud_deployment.operations.env_and_quotas.environment_variables import EnvironmentVariables

    handler = EnvironmentVariables.__new__(EnvironmentVariables)
    handler.env = {"project": "test-project"}
    handler.db = MagicMock()
    handler.get_secret = MagicMock(return_value=None)
    handler.store_secret = MagicMock()
    monkeypatch.setattr("builtins.input", lambda _: "y")

    handler.set_variable("openai_api_key", "test-only-key")

    assert "rubric_support" not in handler.env
    handler.db.update.assert_not_called()
    handler.store_secret.assert_called_once_with("openai_api_key", "test-only-key")

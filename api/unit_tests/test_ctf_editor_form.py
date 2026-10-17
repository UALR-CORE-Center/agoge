import copy
from unittest.mock import MagicMock, patch

import pytest

from common.exceptions import AgogeValidationError
from core.specifications.utilities.edit_manager import SpecEditManager


CTF = {
    "name": "Spring CTF",
    "flags": [
        {
            "id": "web-root",
            "server": "web-server",
            "slot": 1,
            "location_type": "file",
            "path": "/root/flag.txt",
            "operating_system": "linux",
            "points": 100,
        },
    ],
}


@pytest.fixture
def manager():
    # LabSpecBase.__init__ builds CloudEnv, Firestore, and Pub/Sub clients; none may touch GCP here.
    with patch("core.specifications.utilities.lab_spec_base.CloudEnv") as cloud_env, \
            patch("core.specifications.utilities.lab_spec_base.DocumentDatabaseFactory") as db_factory, \
            patch("core.specifications.utilities.lab_spec_base.PubSubManager"), \
            patch("core.specifications.utilities.lab_spec_base.Logger"):
        cloud_env.return_value.get_env.return_value = {}
        db_factory.create_db_object.return_value = MagicMock()
        manager = SpecEditManager(env_dict={})
        manager.spec = {
            "discriminator": "abcde",
            "unit_type": "solo",
            "summary": {"name": "Lab"},
            "servers": [{"name": "web-server"}],
        }
        yield manager


def _summary_form(**overrides) -> dict:
    form = {"form_type": "summary", "name": "Lab", "author": "A", "description": "D", "tags": [], "unit_type": "solo"}
    form.update(overrides)
    return form


def test_ctf_form_stores_block_with_model_defaults(manager):
    manager._form_to_dict({"form_type": "ctf", "ctf": copy.deepcopy(CTF)})

    ctf = manager.spec["ctf"]
    assert ctf["flags"][0]["id"] == "web-root"
    assert ctf["scoring"]["flag_prefix"] == "agoge"


def test_ctf_form_null_removes_block(manager):
    manager.spec["ctf"] = copy.deepcopy(CTF)

    manager._form_to_dict({"form_type": "ctf", "ctf": None})

    assert "ctf" not in manager.spec


def test_ctf_form_rejects_community_unit(manager):
    manager.spec["unit_type"] = "community"

    with pytest.raises(AgogeValidationError, match="solo"):
        manager._form_to_dict({"form_type": "ctf", "ctf": copy.deepcopy(CTF)})


def test_ctf_form_reports_model_errors_as_validation_errors(manager):
    ctf = copy.deepcopy(CTF)
    ctf["flags"] = []

    with pytest.raises(AgogeValidationError, match="flags"):
        manager._form_to_dict({"form_type": "ctf", "ctf": ctf})


def test_summary_without_ctf_enabled_leaves_block(manager):
    manager.spec["ctf"] = copy.deepcopy(CTF)

    manager._form_to_dict(_summary_form())

    assert "ctf" in manager.spec


def test_summary_ctf_disabled_drops_block(manager):
    manager.spec["ctf"] = copy.deepcopy(CTF)

    manager._form_to_dict(_summary_form(ctf_enabled=False))

    assert "ctf" not in manager.spec


def test_summary_ctf_enabled_requires_solo(manager):
    with pytest.raises(AgogeValidationError, match="solo"):
        manager._form_to_dict(_summary_form(unit_type="community", ctf_enabled=True))


def _stub_component_validators():
    for name in ("SummaryValidator", "ServersValidator", "FirewallRulesValidator"):
        validator = patch(f"core.specifications.utilities.edit_manager.{name}").start()
        validator.return_value.load.return_value = {}
    patch.object(SpecEditManager, "_generate_schema", side_effect=lambda objects, model: iter(objects)).start()


def test_servers_save_allows_flag_on_renamed_server_until_ctf_or_publish(manager):
    # Renaming a server must not trap the editor on the Servers step; the CTF step fixes the flag.
    _stub_component_validators()
    manager.spec.update({"build_type": "unit", "ctf": copy.deepcopy(CTF)})
    manager.spec["servers"] = [{"name": "renamed"}]

    manager.form_type = "servers"
    assert manager.is_valid()[0] is True

    manager.validated = False
    manager.form_type = "review"
    valid, message = manager.is_valid()
    assert valid is False
    assert "web-server" in message
    patch.stopall()

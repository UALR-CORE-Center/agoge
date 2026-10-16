import copy
from unittest.mock import MagicMock, patch

import pytest

from common.exceptions import AgogeValidationError
from core.specifications.utilities.edit_manager import SpecEditManager
from core.specifications.utilities.file_manager import SpecFileManager


SPEC = {
    "build_type": "unit",
    "instructor_id": ["instructor@example.com"],
    "summary": {"name": "Test lab", "description": "A lab with a CTF block."},
    "servers": [],
    "ctf": {
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
    },
}


@pytest.fixture
def patched_base():
    # LabSpecBase.__init__ builds CloudEnv, Firestore, and Pub/Sub clients; none may touch GCP here.
    with patch("core.specifications.utilities.lab_spec_base.CloudEnv") as cloud_env, \
            patch("core.specifications.utilities.lab_spec_base.DocumentDatabaseFactory") as db_factory, \
            patch("core.specifications.utilities.lab_spec_base.PubSubManager"), \
            patch("core.specifications.utilities.lab_spec_base.Logger"):
        cloud_env.return_value.get_env.return_value = {"wireguard_port": 51820}
        db = MagicMock()
        db_factory.create_db_object.return_value = db
        yield db
        patch.stopall()


def _spec(path: str = "/root/flag.txt") -> dict:
    spec = copy.deepcopy(SPEC)
    spec["ctf"]["flags"][0]["path"] = path
    return spec


def _file_manager(spec: dict) -> SpecFileManager:
    # Server/network validation is UnitValidator's job; stub it so the CTF check is the only thing under test.
    patch("core.specifications.utilities.file_manager.UnitValidator").start()
    manager = SpecFileManager(env_dict={})
    manager.load(spec)
    return manager


def _edit_manager(spec: dict) -> SpecEditManager:
    manager = SpecEditManager(env_dict={})
    manager.spec = spec
    return manager


@pytest.fixture
def known_server():
    # Stand in for the server validators so `web-server` exists without building a full ServerModel.
    def with_server(spec):
        spec["servers"] = [{"name": "web-server"}]
        return spec
    return with_server


def test_file_manager_accepts_valid_ctf_block(patched_base, known_server):
    manager = _file_manager(known_server(_spec()))

    with patch("core.specifications.utilities.file_manager.UnitModel"):
        assert manager.is_valid() == (True, "Spec is valid")


def test_file_manager_rejects_invalid_ctf_path_and_does_not_save(patched_base, known_server):
    manager = _file_manager(known_server(_spec(path="/root/flag.txt; rm -rf /")))

    with patch("core.specifications.utilities.file_manager.UnitModel"):
        valid, message = manager.is_valid()
        assert valid is False
        assert "web-root" in message
        with pytest.raises(AgogeValidationError):
            manager.save()
    patched_base.update.assert_not_called()


def test_file_manager_rejects_ctf_flag_on_unknown_server(patched_base):
    manager = _file_manager(_spec())

    with patch("core.specifications.utilities.file_manager.UnitModel"):
        valid, message = manager.is_valid()
    assert valid is False
    assert "web-root" in message and "web-server" in message


def test_file_manager_validates_ctf_outside_unit_build_types(patched_base, known_server):
    spec = known_server(_spec(path="relative/flag.txt"))
    spec["build_type"] = "not-a-unit"
    manager = _file_manager(spec)

    valid, message = manager.is_valid()
    assert valid is False
    assert "web-root" in message


def _patch_edit_validators():
    # The non-CTF component validators are covered elsewhere; stub them so only the CTF wiring runs.
    for name in ("SummaryValidator", "ServersValidator", "FirewallRulesValidator"):
        validator = patch(f"core.specifications.utilities.edit_manager.{name}").start()
        validator.return_value.load.return_value = {}
    patch.object(SpecEditManager, "_generate_schema", side_effect=lambda objects, model: iter(objects)).start()


def test_edit_manager_accepts_valid_ctf_block(patched_base, known_server):
    _patch_edit_validators()
    manager = _edit_manager(known_server(_spec()))

    assert manager.is_valid() == (True, "Spec is valid")


def test_edit_manager_rejects_invalid_ctf_path(patched_base, known_server):
    _patch_edit_validators()
    manager = _edit_manager(known_server(_spec(path="C:\\flag.txt")))

    valid, message = manager.is_valid()
    assert valid is False
    assert "web-root" in message


def test_edit_manager_publish_rejects_invalid_ctf_block(patched_base, known_server):
    _patch_edit_validators()
    spec = known_server(_spec(path="/root/$(id).txt"))
    spec["edit_id"] = "abcdefghij"
    manager = _edit_manager(spec)

    with pytest.raises(AgogeValidationError):
        manager.save()


def test_edit_manager_rejects_malformed_ctf_block_shape(patched_base, known_server):
    _patch_edit_validators()
    spec = known_server(_spec())
    spec["ctf"]["flags"] = []
    manager = _edit_manager(spec)

    # CtfSpecModel requires at least one flag; the shape check runs before CtfValidator walks the dict.
    with pytest.raises(Exception, match="flags"):
        manager.is_valid()

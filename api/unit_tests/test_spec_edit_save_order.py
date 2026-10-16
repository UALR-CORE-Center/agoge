from unittest.mock import MagicMock, call, patch

import pytest

from common.exceptions import AgogeValidationError
from core.specifications.utilities.edit_manager import SpecEditManager


@pytest.fixture
def db():
    # LabSpecBase.__init__ builds CloudEnv, Firestore, and Pub/Sub clients; none may touch GCP here.
    with patch("core.specifications.utilities.lab_spec_base.CloudEnv") as cloud_env, \
            patch("core.specifications.utilities.lab_spec_base.DocumentDatabaseFactory") as db_factory, \
            patch("core.specifications.utilities.lab_spec_base.PubSubManager"), \
            patch("core.specifications.utilities.lab_spec_base.Logger"):
        cloud_env.return_value.get_env.return_value = {}
        database = MagicMock()
        db_factory.create_db_object.return_value = database
        yield database


def _manager(spec: dict, catalog: bool) -> SpecEditManager:
    manager = SpecEditManager(env_dict={})
    manager.spec = spec
    manager.catalog = catalog
    return manager


def _invalid_spec() -> dict:
    # A missing build_type is the cheapest real AgogeValidationError _validate_spec raises.
    return {"edit_id": "abcdefghij", "id": "lab-abcde", "summary": {"name": "Lab"}}


def _valid_spec() -> dict:
    # A build_type outside unit/escape-room skips the component validators, so the spec is valid with no stubs.
    return {"build_type": "not-a-unit", "edit_id": "abcdefghij", "id": "lab-abcde", "summary": {"name": "Lab"}}


@pytest.mark.parametrize("catalog", [False, True], ids=["edit-save", "catalog-publish"])
def test_invalid_spec_is_not_written(db, catalog):
    manager = _manager(_invalid_spec(), catalog=catalog)

    with pytest.raises(AgogeValidationError):
        manager.save()

    db.update.assert_not_called()
    db.delete.assert_not_called()


def test_valid_edit_save_writes_edit(db):
    manager = _manager(_valid_spec(), catalog=False)

    manager.save()

    db.update.assert_called_once_with(collection_name=manager.edit_collection, doc_id="abcdefghij", data=manager.spec)
    db.delete.assert_not_called()


def test_valid_catalog_publish_writes_catalog_then_deletes_edit(db):
    manager = _manager(_valid_spec(), catalog=True)

    manager.save()

    assert db.method_calls == [
        call.update(collection_name=manager.catalog_collection, doc_id="lab-abcde", data=manager.spec),
        call.delete(collection_name=manager.edit_collection, doc_id="abcdefghij"),
    ]
    # clean() strips edit-only keys before the catalog write.
    assert "edit_id" not in manager.spec

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from cloud_deployment.operations.images_and_specs import custom_image_import_manager as module
from common.constants.database import DATABASE_NAME, DbCollections, DbOperationTypes
from common.constants.states import ImageStatus
from common.models.agoge import HumanInteractionModel


PROJECT = "agoge-test-project"
IMAGE_NAME = "image-csec2324-proxychain-host"
DOCUMENT_ID = "csec2324-proxychain-host"
IMAGE_URL = f"https://www.googleapis.com/compute/v1/projects/{PROJECT}/global/images/{IMAGE_NAME}"


@pytest.fixture
def importer(monkeypatch):
    env = SimpleNamespace(
        project=PROJECT,
        zone="us-central1-a",
        get_env=lambda: {"project": PROJECT, "zone": "us-central1-a"},
    )
    monkeypatch.setattr(module, "CloudEnv", MagicMock(return_value=env))
    compute = MagicMock()
    compute.get_custom_images.return_value = [{
        "name": IMAGE_NAME,
        "selfLink": IMAGE_URL,
        "diskSizeGb": "20",
        "sourceImage": "projects/debian-cloud/global/images/original-base-image",
        "sourceDisk": f"projects/{PROJECT}/zones/us-central1-a/disks/original-server",
        "licenses": ["projects/debian-cloud/global/licenses/debian-12-bookworm"],
    }]
    monkeypatch.setattr(module, "ComputeResources", MagicMock(return_value=compute))
    db = MagicMock()
    # Reproduce an image already referenced by a lab, but missing from IMAGE.
    db.query.side_effect = lambda collection_name: (
        [{"servers": [{"image": IMAGE_NAME}]}]
        if collection_name == DbCollections.CATALOG else []
    )
    monkeypatch.setattr(
        module.DocumentDatabaseFactory, "create_db_object", MagicMock(return_value=db)
    )
    connection = HumanInteractionModel(
        username="student", password="example-password", protocol="ssh", display=False
    )
    monkeypatch.setattr(
        module, "HumanInteraction",
        MagicMock(return_value=SimpleNamespace(create=lambda: [connection])),
    )
    return module.CustomImageImportManager()


@pytest.mark.parametrize("has_lab_spec", [True, False])
def test_accepted_image_is_saved_without_a_second_catalog_confirmation(
    importer, monkeypatch, capsys, has_lab_spec
):
    if not has_lab_spec:
        importer.db.query.side_effect = lambda collection_name: []
    # The old flow consumed the final "n" and silently discarded the selected image.
    answers = MagicMock(side_effect=["y", "y", "n"])
    monkeypatch.setattr("builtins.input", answers)

    importer.run()

    importer.db.batch_write.assert_called_once()
    operation = importer.db.operation.call_args.kwargs
    assert operation["collection_name"] == DbCollections.IMAGE
    assert operation["doc_id"] == DOCUMENT_ID
    assert operation["operation_type"] == DbOperationTypes.SET
    data = operation["data"]
    assert data["image"] == IMAGE_NAME
    assert data["status"] == ImageStatus.CHECKED_IN.value
    assert data["image_exists"] is True
    assert data["human_interaction"][0]["username"] == "student"
    assert data["human_interaction"][0]["protocol"] == "ssh"
    assert data["self_link"] == IMAGE_URL
    assert data["disks"][0]["initializeParams"]["sourceImage"] == IMAGE_URL
    assert data["disks"][0]["initializeParams"]["type"].endswith("/diskTypes/pd-standard")
    assert answers.call_count == 2
    output = capsys.readouterr().out
    assert f"image/{DOCUMENT_ID}" in output
    assert PROJECT in output
    assert DATABASE_NAME in output
    assert "Imported 1 image(s); skipped 0; failed 0" in output


def test_import_uses_the_selected_project_for_environment_and_database(importer):
    module.CustomImageImportManager(project=PROJECT)

    module.CloudEnv.assert_called_with(project=PROJECT)
    assert module.DocumentDatabaseFactory.create_db_object.call_args.kwargs["project_id"] == PROJECT
    assert module.DocumentDatabaseFactory.create_db_object.call_args.kwargs["database_name"] == DATABASE_NAME
    assert module.ComputeResources.call_args.kwargs["env_dict"]["project"] == PROJECT


@pytest.mark.parametrize("answer", ["", "n"])
def test_declined_image_is_not_saved(importer, monkeypatch, capsys, answer):
    answers = MagicMock(return_value=answer)
    monkeypatch.setattr("builtins.input", answers)

    importer.run()

    assert answers.call_count == 1
    importer.db.operation.assert_not_called()
    importer.db.batch_write.assert_not_called()
    assert "Imported 0 image(s); skipped 1; failed 0" in capsys.readouterr().out


def test_reimport_skips_registered_image_without_overwriting_connection_settings(
    importer, monkeypatch, capsys
):
    importer.db.query.side_effect = None
    importer.db.query.return_value = [{
        "name": DOCUMENT_ID,
        "image": IMAGE_NAME,
        "human_interaction": [{"username": "custom-user"}],
    }]
    answers = MagicMock()
    monkeypatch.setattr("builtins.input", answers)

    importer.run()

    answers.assert_not_called()
    importer.db.batch_write.assert_not_called()
    assert "Imported 0 image(s); skipped 1; failed 0" in capsys.readouterr().out


@pytest.mark.parametrize("failure", ["list", "read"])
def test_lookup_failure_aborts_import_before_prompting(
    importer, monkeypatch, capsys, failure
):
    lookup = importer.compute.get_custom_images if failure == "list" else importer.db.query
    lookup.side_effect = RuntimeError("permission denied")
    answers = MagicMock()
    monkeypatch.setattr("builtins.input", answers)

    importer.run()

    answers.assert_not_called()
    importer.db.batch_write.assert_not_called()
    output = capsys.readouterr().out
    assert "permission denied" in output
    assert "[SUCCESS]" not in output


@pytest.mark.parametrize("failure", ["operation", "batch_write"])
def test_write_failure_is_reported_without_claiming_success(
    importer, monkeypatch, capsys, failure
):
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=["y", "n"]))
    getattr(importer.db, failure).side_effect = RuntimeError("write denied")

    importer.run()

    output = capsys.readouterr().out
    assert "write denied" in output
    assert "Imported 0 image(s); skipped 0; failed 1" in output
    assert "[SUCCESS]" not in output
    assert IMAGE_NAME not in importer.existing_images


def test_invalid_image_metadata_is_reported_without_writing(importer, monkeypatch, capsys):
    importer.compute.get_custom_images.return_value[0]["diskSizeGb"] = "invalid"
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=["y", "n"]))

    importer.run()

    importer.db.batch_write.assert_not_called()
    output = capsys.readouterr().out
    assert f"Could not import '{IMAGE_NAME}'" in output
    assert "Imported 0 image(s); skipped 0; failed 1" in output


def test_image_is_committed_before_the_next_import_prompt(importer, monkeypatch):
    importer.compute.get_custom_images.return_value.append({"name": "image-second-server"})
    first_answers = iter(["y", "n"])

    def answer(prompt):
        if "image-second-server" in prompt:
            importer.db.batch_write.assert_called_once()
            raise KeyboardInterrupt
        return next(first_answers)

    monkeypatch.setattr("builtins.input", answer)

    with pytest.raises(KeyboardInterrupt):
        importer.run()

    importer.db.batch_write.assert_called_once()


def test_missing_self_link_is_constructed_for_the_selected_custom_image(importer, monkeypatch):
    del importer.compute.get_custom_images.return_value[0]["selfLink"]
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=["yes", "n"]))

    importer.run()

    data = importer.db.operation.call_args.kwargs["data"]
    assert data["self_link"] == IMAGE_URL
    assert data["disks"][0]["initializeParams"]["sourceImage"] == IMAGE_URL

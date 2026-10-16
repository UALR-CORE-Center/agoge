from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from common.models.agoge import CatalogEditModel, CatalogModel, CtfSpecModel, UnitModel
from core.unit import Unit


SPEC = {
    "id": "abcdefghij",
    "version": "1.0.0",
    "build_type": "unit",
    "discriminator": "test",
    "instructor_id": ["instructor@example.com"],
    "summary": {"name": "Test lab", "description": "A lab with an optional CTF block."},
}

CTF = {
    "name": "Spring CTF",
    "rules_url": "https://example.com/rules",
    "flags": [
        {
            "id": "web-root",
            "server": "web-server",
            "slot": 1,
            "location_type": "file",
            "path": "/root/flag.txt",
            "operating_system": "linux",
            "points": 100,
            "file_mode": "0600",
        },
        {
            "id": "decoy-one",
            "server": "web-server",
            "slot": 2,
            "location_type": "env",
            "path": "DECOY_FLAG",
            "operating_system": "linux",
            "points": -50,
            "decoy": True,
        },
    ],
    "scoring": {"flag_prefix": "spring", "submission_rate_limit": 5},
}


def _build_unit(stored_spec):
    """Run Unit.build against a mocked catalog read and return the committed UnitModel."""
    handler = Unit.__new__(Unit)
    handler.logger = MagicMock()
    handler.db = MagicMock()
    handler.db.get.return_value = stored_spec
    handler.commit = MagicMock()

    build_id = handler.build(
        requester=SimpleNamespace(uid="test-instructor", email="instructor@example.com"),
        data={"build_file": SPEC["id"], "expires": "2099-01-01T00:00:00Z"},
    )

    unit = handler.commit.call_args.args[0]
    assert unit.id == build_id
    return unit


def test_ctf_block_survives_specification_models_and_lab_build():
    edit = CatalogEditModel(**SPEC, ctf=CTF, edit_id="test-edit")
    assert isinstance(edit.ctf, CtfSpecModel)

    catalog = CatalogModel(**edit.model_dump())
    assert catalog.ctf == edit.ctf

    # Firestore stores the catalog as plain JSON; the build copies it into the unit.
    unit = _build_unit(catalog.model_dump(mode="json"))

    assert isinstance(unit.ctf, CtfSpecModel)
    assert unit.ctf == edit.ctf
    assert unit.model_dump()["ctf"] == CtfSpecModel(**CTF).model_dump()
    assert unit.ctf.scoring.flag_prefix == "spring"
    assert unit.ctf.flags[1].decoy is True


@pytest.mark.parametrize("settings", [{}, {"ctf": None}])
def test_specification_without_ctf_block_builds_a_non_ctf_unit(settings):
    edit = CatalogEditModel(**SPEC, **settings, edit_id="test-edit")
    catalog = CatalogModel(**edit.model_dump())
    assert edit.ctf is None and catalog.ctf is None

    # Cover old persisted specifications that do not have the field at all.
    unit = _build_unit({**SPEC, **settings})
    assert unit.ctf is None
    assert unit.model_dump()["ctf"] is None


@pytest.mark.parametrize("model", [UnitModel, CatalogModel, CatalogEditModel])
def test_specifications_validate_the_ctf_block(model):
    bad_flag = {**CTF["flags"][0], "id": "Bad_Id"}
    with pytest.raises(ValidationError):
        model(**SPEC, edit_id="test-edit", ctf={**CTF, "flags": [bad_flag]})
    # A CTF block must declare at least one flag.
    with pytest.raises(ValidationError):
        model(**SPEC, edit_id="test-edit", ctf={**CTF, "flags": []})

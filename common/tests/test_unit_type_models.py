import json

import pytest
from pydantic import ValidationError

from common.models.agoge import CatalogEditModel, CatalogModel, UnitModel


def _unit_payload() -> dict:
    return {
        'id': 'unit-type-test',
        'version': '1',
        'instructor_id': ['instructor@example.com'],
        'build_type': 'unit',
        'summary': {
            'name': 'Unit type validation',
            'description': 'Validates JSON upload and persisted models consistently.',
        },
    }


def _catalog_payload() -> dict:
    return {
        **_unit_payload(),
        'discriminator': 'abcde',
    }


def _catalog_edit_payload() -> dict:
    return {
        **_catalog_payload(),
        'edit_id': 'edit-unit-type-test',
    }


@pytest.mark.parametrize(
    ('model', 'payload_factory'),
    [
        (UnitModel, _unit_payload),
        (CatalogModel, _catalog_payload),
        (CatalogEditModel, _catalog_edit_payload),
    ],
)
@pytest.mark.parametrize('unit_type', ['solo', 'community'])
def test_unit_type_accepts_the_same_values_from_json_and_python(
    model,
    payload_factory,
    unit_type,
):
    payload = payload_factory() | {'unit_type': unit_type}

    from_python = model.model_validate(payload)
    from_json_upload = model.model_validate_json(json.dumps(payload))

    assert from_python.unit_type == unit_type
    assert from_json_upload.unit_type == unit_type
    assert from_json_upload.model_dump()['unit_type'] == unit_type


@pytest.mark.parametrize(
    ('model', 'payload_factory'),
    [
        (UnitModel, _unit_payload),
        (CatalogModel, _catalog_payload),
        (CatalogEditModel, _catalog_edit_payload),
    ],
)
def test_unit_type_typo_is_rejected_for_json_upload_and_python_models(
    model,
    payload_factory,
):
    payload = payload_factory() | {'unit_type': 'commmunity'}

    with pytest.raises(ValidationError, match='unit_type'):
        model.model_validate(payload)
    with pytest.raises(ValidationError, match='unit_type'):
        model.model_validate_json(json.dumps(payload))


@pytest.mark.parametrize(
    ('model', 'payload_factory'),
    [
        (UnitModel, _unit_payload),
        (CatalogModel, _catalog_payload),
        (CatalogEditModel, _catalog_edit_payload),
    ],
)
def test_missing_unit_type_defaults_to_serializable_solo(model, payload_factory):
    validated = model.model_validate_json(json.dumps(payload_factory()))

    assert validated.unit_type == 'solo'
    assert json.loads(validated.model_dump_json())['unit_type'] == 'solo'

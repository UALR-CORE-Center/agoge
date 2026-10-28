"""Nested hosts resolve N1/N2/N4 machine types up to the nested cap, the nested list offers only
NESTED_MACHINE_TYPES, and an unknown type falls back to SMALL (V2)."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from cloud_fn_utilities.course_objects.compute.image_template_manager import ImageTemplateManager
from common.constants.build_constants import BuildConstants
from common.constants.google import ResourceType
from common.exceptions import NotFound
from common.utilities.gcp.compute.compute_machine_type import ComputeMachineTypesAPI

MACHINE_TYPES = {
    'e2-standard-4': 16384,
    'e2-standard-8': 32768,
    'n1-standard-4': 15360,
    'n1-standard-16': 61440,
    'n2-standard-4': 16384,
    'n2-standard-8': 32768,
    'n2-standard-16': 65536,
    'n2-standard-32': 131072,
    'n2-highmem-4': 32768,
    'n4-standard-8': 32768,
    'c2-standard-4': 16384,
}


def _m_type(name):
    return SimpleNamespace(
        name=name, memory_mb=MACHINE_TYPES[name], description=name, is_shared_cpu=False, guest_cpus=4,
    )


def _api():
    api = object.__new__(ComputeMachineTypesAPI)
    api.class_name = ComputeMachineTypesAPI.__name__
    api.project = 'test-dev-787001'
    api.zone = 'us-central1-a'
    api.resource_type = ResourceType.MACHINE_TYPE
    api.logger = Mock()
    api.machine_type_client = Mock()
    api.machine_type_client.list.return_value = [_m_type(name) for name in MACHINE_TYPES]
    api.machine_type_client.get.side_effect = lambda request: _m_type(request.machine_type)
    return api


def _names(m_types):
    return sorted(m_type.name for m_type in m_types)


def test_default_list_is_unchanged():
    assert _names(_api().list()) == [
        'e2-standard-4', 'n1-standard-4', 'n2-standard-4',
    ]


def test_nested_list_holds_only_the_offered_types():
    names = _names(_api().list(nested=True))

    # n2-highmem-4 is nested-capable but not offered; n2-standard-32 is offered by neither.
    assert names == [
        'n1-standard-16', 'n1-standard-4', 'n2-standard-16', 'n2-standard-4', 'n2-standard-8', 'n4-standard-8',
    ]
    assert not any(name.startswith('e2') for name in names)


@pytest.mark.parametrize('name, resolves', [
    ('n2-standard-8', True),
    ('n2-standard-16', True),
    ('n1-standard-16', True),
    ('n2-highmem-4', True),
    ('n4-standard-8', True),
    ('e2-standard-4', True),
    ('e2-standard-8', False),
    ('n2-standard-32', False),
    ('c2-standard-4', False),
])
def test_get_resolves_n1_n2_n4_up_to_the_nested_cap_and_e2_up_to_the_standard_cap(name, resolves):
    m_type = _api().get(resource=name)

    assert (m_type is not None) == resolves
    if resolves:
        assert m_type.name == name


def _manager(get):
    manager = object.__new__(ImageTemplateManager)
    manager.logger = Mock()
    manager.compute_instance = Mock(GOOGLE_MACHINE_TYPES=BuildConstants.GoogleMachineTypes.ALL.value)
    manager.compute_machine_types = Mock()
    manager.compute_machine_types.get = get
    return manager


def test_n2_standard_8_resolves_for_a_nested_server():
    manager = _manager(_api().get)

    assert manager._lookup_machine_type('n2-standard-8') == 'n2-standard-8'
    manager.logger.warning.assert_not_called()


SMALL = BuildConstants.GoogleMachineTypes.ALL.value[BuildConstants.MachineTypes.SMALL.value]


@pytest.mark.parametrize('get', [
    Mock(return_value=None),
    Mock(side_effect=NotFound(message='The requested resource or endpoint, n9-huge, was not found.')),
])
def test_unknown_machine_type_falls_back_to_small_with_a_warning(get):
    manager = _manager(get)

    assert manager._lookup_machine_type('n9-huge') == SMALL
    manager.logger.warning.assert_called_once()

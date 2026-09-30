"""Spec-time validation of nested virtualization.

enable_nested_virtualization can only be set when the instance is created, and Google rejects it
outright on the E2 family. Catching the mismatch while the specification is being saved keeps the
failure attached to the field the instructor just edited, rather than surfacing it much later as a
server that built cleanly and then could not start a single target.
"""
import pytest

from common.exceptions import AgogeValidationError
from utilities.infrastructure_as_code.object_validators.servers import ServersValidator


def _config(machine_type, nested_virtualization=False, ip_aliases=None):
    nic = {
        'network': 'external',
        'internal_ip': '10.1.1.10',
        'external_nat': True,
    }
    if ip_aliases:
        nic['ip_aliases'] = ip_aliases

    return {
        'network_map': {'external': '10.1.1.0/24'},
        'servers': [
            {
                'name': 'metasploitable',
                'machine_type': machine_type,
                'nested_virtualization': nested_virtualization,
                'nics': [nic],
            }
        ],
    }


def test_nested_virtualization_on_n2_is_accepted():
    ServersValidator(_config('n2-standard-8', nested_virtualization=True)).load()


def test_nested_virtualization_on_n1_is_accepted():
    ServersValidator(_config('n1-standard-4', nested_virtualization=True)).load()


def test_nested_virtualization_on_e2_is_rejected():
    with pytest.raises(AgogeValidationError, match='nested virtualization'):
        ServersValidator(_config('e2-standard-8', nested_virtualization=True)).load()


def test_ip_aliases_on_e2_are_rejected_too():
    """ip_aliases turns the same flag on in the build path, so it carries the same requirement."""
    with pytest.raises(AgogeValidationError, match='nested virtualization'):
        ServersValidator(_config('e2-standard-4', ip_aliases=['10.1.1.20'])).load()


def test_e2_without_nested_virtualization_is_untouched():
    ServersValidator(_config('e2-standard-4')).load()


def test_missing_machine_type_is_rejected_when_nested_virtualization_is_requested():
    config = _config('n2-standard-8', nested_virtualization=True)
    del config['servers'][0]['machine_type']

    with pytest.raises(AgogeValidationError, match='nested virtualization'):
        ServersValidator(config).load()

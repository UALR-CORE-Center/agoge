from unittest.mock import MagicMock, patch

from core.unit import Unit


def _handler(unit_record):
    handler = Unit.__new__(Unit)
    handler.collection = 'unit'
    handler.env_dict = {'project': 'agoge-test'}
    handler.logger = MagicMock()
    handler.db = MagicMock()
    handler.db.get.return_value = unit_record
    handler._validate = MagicMock()
    handler._get_unit_workouts = MagicMock(return_value=[])
    return handler


def test_reset_expiration_extends_wireguard_lease_with_the_unit():
    record = {'id': 'abcdefghij', 'workspace_settings': {'expires': 1000},
              'wireguard_lease': {'unit_id': 'abcdefghij', 'expires': 1000}}
    handler = _handler(record)
    with patch('core.unit.WireGuardProvisioningService') as service:
        handler._reset_expiration(build_id='abcdefghij', days=2)

    new_expiration = 1000 + 2 * 86400
    assert record['workspace_settings']['expires'] == new_expiration
    assert record['wireguard_lease']['expires'] == new_expiration
    service.return_value.extend_lease.assert_called_once_with('abcdefghij', new_expiration)


def test_reset_expiration_skips_lease_for_non_wireguard_units():
    handler = _handler({'id': 'abcdefghij', 'workspace_settings': {'expires': 1000}})
    with patch('core.unit.WireGuardProvisioningService') as service:
        handler._reset_expiration(build_id='abcdefghij', days=2)
    service.assert_not_called()

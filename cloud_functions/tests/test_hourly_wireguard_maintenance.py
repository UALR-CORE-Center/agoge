from unittest.mock import Mock

from cloud_fn_utilities.periodic_maintenance.hourly_maintenance import HourlyMaintenance


def test_hourly_maintenance_purges_mature_wireguard_tombstones():
    maintenance = object.__new__(HourlyMaintenance)
    maintenance.class_name = "HourlyMaintenance"
    maintenance.logger = Mock()
    maintenance.wireguard_registry = Mock()
    maintenance.wireguard_registry.purge_released.return_value = 3

    maintenance._purge_wireguard_endpoint_tombstones()

    maintenance.wireguard_registry.purge_released.assert_called_once_with()
    assert "Purged 3" in maintenance.logger.info.call_args.args[0]


def test_wireguard_tombstone_failure_does_not_abort_hourly_maintenance():
    maintenance = object.__new__(HourlyMaintenance)
    maintenance.class_name = "HourlyMaintenance"
    maintenance.logger = Mock()
    maintenance.wireguard_registry = Mock()
    maintenance.wireguard_registry.purge_released.side_effect = RuntimeError("Firestore unavailable")

    maintenance._purge_wireguard_endpoint_tombstones()

    assert "Firestore unavailable" in maintenance.logger.error.call_args.args[0]

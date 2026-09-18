from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from cloud_fn_utilities.gcp import dns_manager as dns_module


class _FakeHttpError(Exception):
    def __init__(self, status: int):
        super().__init__(f'HTTP {status}')
        self.resp = SimpleNamespace(status=status)
        self.error_details = f'HTTP {status}'


def _manager():
    manager = dns_module.DnsManager.__new__(dns_module.DnsManager)
    manager.class_name = 'DnsManager'
    manager.env = SimpleNamespace(
        parent_project='shared-dns-project',
        parent_zone='public-zone',
    )
    manager.dns = MagicMock()
    manager.logger = MagicMock()
    return manager


def test_expected_ip_delete_uses_the_current_exact_matching_rrset():
    manager = _manager()
    current_rrset = {
        'kind': 'dns#resourceRecordSet',
        'name': 'wg-12345.tenant-a.gateways.example.edu.',
        'type': 'A',
        'ttl': 60,
        'rrdatas': ['203.0.113.10'],
    }
    list_request = MagicMock()
    list_request.execute.return_value = {'rrsets': [current_rrset]}
    manager.dns.resourceRecordSets.return_value.list.return_value = list_request

    assert manager.delete_dns(
        record_name=current_rrset['name'],
        ip_address='203.0.113.10',
    ) is True

    manager.dns.resourceRecordSets.return_value.list.assert_called_once_with(
        project='shared-dns-project',
        managedZone='public-zone',
        name=current_rrset['name'],
        type='A',
    )
    manager.dns.changes.return_value.create.assert_called_once_with(
        project='shared-dns-project',
        managedZone='public-zone',
        body={'deletions': [current_rrset]},
    )


def test_delayed_delete_does_not_remove_a_record_reassigned_to_a_new_ip():
    manager = _manager()
    record_name = 'wg-12345.tenant-a.gateways.example.edu.'
    list_request = MagicMock()
    list_request.execute.return_value = {
        'rrsets': [{
            'kind': 'dns#resourceRecordSet',
            'name': record_name,
            'type': 'A',
            'ttl': 30,
            'rrdatas': ['203.0.113.99'],
        }]
    }
    manager.dns.resourceRecordSets.return_value.list.return_value = list_request

    assert manager.delete_dns(
        record_name=record_name,
        ip_address='203.0.113.10',
    ) is True

    manager.dns.changes.return_value.create.assert_not_called()
    manager.dns.resourceRecordSets.return_value.delete.assert_not_called()


def test_expected_ip_delete_fails_closed_when_the_rrset_cannot_be_read():
    manager = _manager()
    list_request = MagicMock()
    list_request.execute.side_effect = _FakeHttpError(500)
    manager.dns.resourceRecordSets.return_value.list.return_value = list_request

    with patch.object(dns_module, 'HttpError', _FakeHttpError):
        result = manager.delete_dns(
            record_name='wg-12345.tenant-a.gateways.example.edu.',
            ip_address='203.0.113.10',
        )

    assert result is False
    manager.dns.changes.return_value.create.assert_not_called()
    manager.dns.resourceRecordSets.return_value.delete.assert_not_called()

import copy
import ipaddress
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest

from cloud_functions.cloud_fn_utilities.course_objects.unit.unit_dhcp_service import UnitDHCP
from common.document_database import firestore_database
from common.document_database.firestore_database import FirestoreDatabase


class _FakeSnapshot:
    def __init__(self, data):
        self.exists = data is not None
        self._data = data

    def to_dict(self):
        return copy.deepcopy(self._data)


class _FakeDocument:
    def __init__(self, data):
        self.data = data

    def get(self, transaction=None):
        return _FakeSnapshot(self.data)


class _FakeCollection:
    def __init__(self, document):
        self._document = document

    def document(self, document_id):
        return self._document


class _FakeFirestoreClient:
    def __init__(self, document):
        self._document = document

    def collection(self, collection_name):
        return _FakeCollection(self._document)


class _FakeTransaction:
    def __init__(self):
        self.writes = []

    def set(self, document, data, merge=False):
        self.writes.append((copy.deepcopy(data), merge))
        if merge:
            document.data.update(copy.deepcopy(data))
        else:
            document.data = copy.deepcopy(data)


class _FakeDatabase:
    def __init__(self, unit):
        self.document = _FakeDocument(copy.deepcopy(unit))
        self.db = _FakeFirestoreClient(self.document)
        self.transaction_calls = 0
        self.last_transaction = None

    def transaction(self, operation_func, **kwargs):
        self.transaction_calls += 1
        self.last_transaction = _FakeTransaction()
        return operation_func(self.last_transaction, **kwargs)


class _TransactionConflict(Exception):
    pass


class _VersionedDocument:
    def __init__(self, database, collection_name, document_id):
        self.database = database
        self.key = (collection_name, document_id)

    def get(self, transaction=None):
        if transaction is not None:
            return transaction.get(self)
        with self.database.lock:
            return _FakeSnapshot(copy.deepcopy(self.database.documents.get(self.key)))


class _VersionedCollection:
    def __init__(self, database, collection_name):
        self.database = database
        self.collection_name = collection_name

    def document(self, document_id):
        return _VersionedDocument(self.database, self.collection_name, document_id)


class _VersionedFirestoreClient:
    def __init__(self, database):
        self.database = database

    def collection(self, collection_name):
        return _VersionedCollection(self.database, collection_name)


class _OptimisticTransaction:
    def __init__(self, database):
        self.database = database
        self.read_versions = {}
        self.read_values = {}
        self.writes = []

    def get(self, document):
        if document.key not in self.read_values:
            with self.database.lock:
                self.read_versions[document.key] = self.database.versions.get(document.key, 0)
                self.read_values[document.key] = copy.deepcopy(
                    self.database.documents.get(document.key)
                )
        return _FakeSnapshot(copy.deepcopy(self.read_values[document.key]))

    def set(self, document, data, merge=False):
        self.writes.append((document.key, copy.deepcopy(data), merge))

    def commit(self):
        with self.database.lock:
            if any(
                self.database.versions.get(key, 0) != version
                for key, version in self.read_versions.items()
            ):
                raise _TransactionConflict
            for key, data, merge in self.writes:
                if merge:
                    updated = copy.deepcopy(self.database.documents.get(key) or {})
                    updated.update(data)
                    self.database.documents[key] = updated
                else:
                    self.database.documents[key] = data
                self.database.versions[key] = self.database.versions.get(key, 0) + 1


class _OptimisticDatabase:
    """Small Firestore retry model used to exercise the duplicate-build race."""

    def __init__(self, unit, synchronize_first_attempts=False):
        self.documents = {
            ('unit', 'unit-12345'): copy.deepcopy(unit),
        }
        self.versions = {('unit', 'unit-12345'): 1}
        self.lock = threading.Lock()
        self.db = _VersionedFirestoreClient(self)
        self.barrier = threading.Barrier(2) if synchronize_first_attempts else None
        self.conflicts = 0

    def transaction(self, operation_func, **kwargs):
        first_attempt = True
        while True:
            transaction = _OptimisticTransaction(self)
            result = operation_func(transaction, **kwargs)
            if first_attempt and self.barrier is not None:
                self.barrier.wait(timeout=5)
            try:
                transaction.commit()
                return result
            except _TransactionConflict:
                self.conflicts += 1
                first_attempt = False

    def get_document(self, collection_name, document_id):
        with self.lock:
            return copy.deepcopy(self.documents.get((collection_name, document_id)))


def _unit(reservations=None):
    return {
        'networks': [
            {
                'name': 'external',
                'subnets': [{'name': 'default', 'ip_subnet': '10.20.0.0/29'}],
                'reservations': reservations,
            }
        ],
        'servers': [
            {
                'name': 'wireguard',
                'community_server': True,
                'nics': [{'network': 'external', 'internal_ip': '10.20.0.2'}],
            }
        ],
    }


def _dhcp(unit=None):
    allocator = object.__new__(UnitDHCP)
    allocator.unit_id = 'unit-12345'
    allocator.db = _FakeDatabase(_unit() if unit is None else unit)
    allocator.logger = Mock()
    allocator.validator = Mock()
    allocator._validate_unit = lambda data: None
    return allocator


def _dhcp_with_database(database):
    allocator = object.__new__(UnitDHCP)
    allocator.unit_id = 'unit-12345'
    allocator.db = database
    allocator.logger = Mock()
    allocator.validator = Mock()
    allocator._validate_unit = lambda data: None
    return allocator


def test_allocation_repairs_null_reservations_and_persists_atomically():
    allocator = _dhcp()

    address = allocator.get_network_address('external')

    assert address == '10.20.0.3'
    assert allocator.db.transaction_calls == 1
    assert allocator.db.last_transaction.writes == [
        ({
            'networks': [
                {
                    'name': 'external',
                    'subnets': [{'name': 'default', 'ip_subnet': '10.20.0.0/29'}],
                    'reservations': ['10.20.0.2', '10.20.0.3'],
                }
            ]
        }, True)
    ]


def test_consecutive_transactions_allocate_distinct_addresses():
    allocator = _dhcp()

    assert allocator.get_network_address('external') == '10.20.0.3'
    assert allocator.get_network_address('external') == '10.20.0.4'
    assert allocator.db.document.data['networks'][0]['reservations'] == [
        '10.20.0.2',
        '10.20.0.3',
        '10.20.0.4',
    ]


def test_server_lease_claim_is_idempotent_and_persists_its_owner_atomically():
    database = _OptimisticDatabase(_unit())
    allocator = _dhcp_with_database(database)
    server_data = {
        'name': 'kali',
        'parent_id': 'workout-67890',
        'parent_build_type': 'workout',
        'nics': [{'network': 'external', 'subnet_name': 'default'}],
    }

    first = allocator.claim_server_leases('workout-67890-kali', server_data)
    second = allocator.claim_server_leases('workout-67890-kali', server_data)

    assert first['nics'][0]['internal_ip'] == '10.20.0.3'
    assert second['nics'][0]['internal_ip'] == '10.20.0.3'
    assert database.get_document('unit', 'unit-12345')['networks'][0]['reservations'] == [
        '10.20.0.2',
        '10.20.0.3',
    ]
    assert database.get_document('agoge-server', 'workout-67890-kali')['nics'] == [{
        'network': 'external',
        'subnet_name': 'default',
        'internal_ip': '10.20.0.3',
    }]
    assert server_data['nics'][0].get('internal_ip') is None


def test_distinct_servers_replace_a_legacy_template_ip_with_dynamic_leases():
    database = _OptimisticDatabase(_unit())
    allocator = _dhcp_with_database(database)
    legacy_template = {
        'name': 'kali',
        'parent_build_type': 'workout',
        'nics': [{
            'network': 'external',
            'subnet_name': 'default',
            'internal_ip': '10.20.0.5',
        }],
    }

    first = allocator.claim_server_leases(
        'workout-11111-kali',
        {**legacy_template, 'parent_id': 'workout-11111'},
    )
    second = allocator.claim_server_leases(
        'workout-22222-kali',
        {**legacy_template, 'parent_id': 'workout-22222'},
    )

    assert first['nics'][0]['internal_ip'] == '10.20.0.3'
    assert second['nics'][0]['internal_ip'] == '10.20.0.4'
    assert database.get_document('unit', 'unit-12345')['networks'][0]['reservations'] == [
        '10.20.0.2',
        '10.20.0.3',
        '10.20.0.4',
    ]


def test_concurrent_duplicate_server_claim_retries_and_reuses_winning_lease():
    database = _OptimisticDatabase(_unit(), synchronize_first_attempts=True)
    allocator = _dhcp_with_database(database)
    server_data = {
        'name': 'kali',
        'parent_id': 'workout-67890',
        'parent_build_type': 'workout',
        'nics': [{'network': 'external', 'subnet_name': 'default'}],
    }

    with ThreadPoolExecutor(max_workers=2) as executor:
        claims = list(executor.map(
            lambda _: allocator.claim_server_leases('workout-67890-kali', server_data),
            range(2),
        ))

    assert [claim['nics'][0]['internal_ip'] for claim in claims] == [
        '10.20.0.3',
        '10.20.0.3',
    ]
    assert claims[0][UnitDHCP.LEASE_CLAIM_FIELD] == claims[1][UnitDHCP.LEASE_CLAIM_FIELD]
    assert database.conflicts == 1
    assert database.get_document('unit', 'unit-12345')['networks'][0]['reservations'] == [
        '10.20.0.2',
        '10.20.0.3',
    ]
    assert database.get_document(
        'agoge-server', 'workout-67890-kali'
    )['nics'][0]['internal_ip'] == '10.20.0.3'


def test_server_lease_release_is_durable_before_address_reuse():
    database = _OptimisticDatabase(_unit())
    allocator = _dhcp_with_database(database)
    server_data = {
        'name': 'kali',
        'parent_build_type': 'workout',
        'nics': [{'network': 'external', 'subnet_name': 'default'}],
    }
    first = allocator.claim_server_leases(
        'workout-11111-kali',
        {**server_data, 'parent_id': 'workout-11111'},
    )
    first_claim_id = first[UnitDHCP.LEASE_CLAIM_FIELD]

    assert allocator.release_server_leases(
        'workout-11111-kali', claim_id=first_claim_id
    ) is True
    # Simulate a Workout delete retry after another server has reused the IP.
    second = allocator.claim_server_leases(
        'workout-22222-kali',
        {**server_data, 'parent_id': 'workout-22222'},
    )
    assert second['nics'][0]['internal_ip'] == '10.20.0.3'
    assert allocator.release_server_leases(
        'workout-11111-kali', claim_id=first_claim_id
    ) is False
    assert database.get_document('unit', 'unit-12345')['networks'][0]['reservations'] == [
        '10.20.0.2',
        '10.20.0.3',
    ]


def test_stale_release_token_cannot_release_a_new_claim_on_same_server_record():
    database = _OptimisticDatabase(_unit())
    allocator = _dhcp_with_database(database)
    server_data = {
        'name': 'kali',
        'parent_id': 'workout-11111',
        'parent_build_type': 'workout',
        'nics': [{'network': 'external', 'subnet_name': 'default'}],
    }
    first = allocator.claim_server_leases('workout-11111-kali', server_data)
    first_claim_id = first[UnitDHCP.LEASE_CLAIM_FIELD]
    allocator.release_server_leases('workout-11111-kali', claim_id=first_claim_id)

    second = allocator.claim_server_leases('workout-11111-kali', server_data)

    assert second[UnitDHCP.LEASE_CLAIM_FIELD] != first_claim_id
    assert allocator.release_server_leases(
        'workout-11111-kali', claim_id=first_claim_id
    ) is False
    assert database.get_document('unit', 'unit-12345')['networks'][0]['reservations'] == [
        '10.20.0.2',
        '10.20.0.3',
    ]


def test_release_returns_dynamic_address_but_preserves_static_gateway_address():
    allocator = _dhcp(_unit(reservations=['10.20.0.2', '10.20.0.3']))

    assert allocator.release_network_address('external', '10.20.0.3') is True
    assert allocator.db.document.data['networks'][0]['reservations'] == ['10.20.0.2']

    assert allocator.release_network_address('external', '10.20.0.2') is False
    assert allocator.db.document.data['networks'][0]['reservations'] == ['10.20.0.2']


def test_exhausted_subnet_raises_instead_of_reserving_none():
    allocator = _dhcp(_unit(reservations=[
        '10.20.0.2',
        '10.20.0.3',
        '10.20.0.4',
        '10.20.0.5',
    ]))

    with pytest.raises(RuntimeError, match='No addresses remain'):
        allocator.get_network_address('external')


def test_allocator_only_reserves_gcp_special_addresses_for_the_whole_subnet():
    allocator = _dhcp()
    subnet = ipaddress.ip_network('10.20.0.0/23')
    reservations = [str(address) for address in subnet if int(address) < int(subnet.network_address) + 254]

    # 10.20.0.254 is valid in a /23. The former implementation incorrectly
    # treated every /24 boundary as a separate GCP subnet boundary.
    assert allocator._get_available_ip(subnet, reservations) == '10.20.0.254'


def test_missing_network_has_a_clear_configuration_error():
    allocator = _dhcp()

    with pytest.raises(ValueError, match='not defined'):
        allocator.get_network_address('missing')


def test_named_subnets_have_independent_address_pools():
    unit = _unit(reservations=None)
    unit['networks'][0]['subnets'].append({
        'name': 'secondary',
        'ip_subnet': '10.21.0.0/29',
    })
    unit['servers'][0]['nics'].append({
        'network': 'external',
        'subnet_name': 'secondary',
        'internal_ip': '10.21.0.2',
    })
    allocator = _dhcp(unit)

    assert allocator.get_network_address('external', 'secondary') == '10.21.0.3'
    assert allocator.get_network_address('external', 'default') == '10.20.0.3'
    assert allocator.db.document.data['networks'][0]['reservations'] == [
        '10.21.0.2',
        '10.21.0.3',
        '10.20.0.2',
        '10.20.0.3',
    ]


def test_missing_named_subnet_has_a_clear_configuration_error():
    allocator = _dhcp()

    with pytest.raises(ValueError, match='does not define subnet secondary'):
        allocator.get_network_address('external', 'secondary')


def test_release_rejects_address_from_a_different_named_subnet():
    unit = _unit(reservations=['10.20.0.3'])
    unit['networks'][0]['subnets'].append({
        'name': 'secondary',
        'ip_subnet': '10.21.0.0/29',
    })
    allocator = _dhcp(unit)

    with pytest.raises(ValueError, match='not in network external, subnet secondary'):
        allocator.release_network_address('external', '10.20.0.3', 'secondary')


def test_firestore_database_transaction_uses_retrying_transactional_wrapper(monkeypatch):
    raw_transaction = object()
    client = Mock()
    client.transaction.return_value = raw_transaction
    database = object.__new__(FirestoreDatabase)
    database.db = client
    database.logger = Mock()
    calls = []

    def transactional(operation):
        calls.append(('wrap', operation))

        def invoke(transaction, *args, **kwargs):
            calls.append(('invoke', transaction, args, kwargs))
            return operation(transaction, *args, **kwargs)

        return invoke

    monkeypatch.setattr(firestore_database.firestore, 'transactional', transactional)

    def operation(transaction, value):
        assert transaction is raw_transaction
        return f'allocated-{value}'

    assert database.transaction(operation, value='10.20.0.3') == 'allocated-10.20.0.3'
    assert calls == [
        ('wrap', operation),
        ('invoke', raw_transaction, (), {'value': '10.20.0.3'}),
    ]


def test_transactional_update_does_not_repeat_nontransactional_write(monkeypatch):
    document = Mock()
    collection = Mock()
    collection.document.return_value = document
    client = Mock()
    client.collection.return_value = collection
    database = object.__new__(FirestoreDatabase)
    database.db = client
    database.logger = Mock()
    database.transaction = Mock(return_value=True)

    database._update(
        collection_name=firestore_database.DbCollections.UNIT,
        doc_id='unit-12345',
        data={'networks': []},
        use_transaction=True,
    )

    database.transaction.assert_called_once()
    document.set.assert_not_called()

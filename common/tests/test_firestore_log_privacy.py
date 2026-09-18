from unittest.mock import MagicMock

import pytest

from common.constants.database import DbCollections, DbOperationTypes
from common.document_database.firestore_database import FirestoreDatabase


@pytest.mark.parametrize('transactional', [False, True])
def test_document_reads_return_payload_without_logging_credentials(transactional):
    database = object.__new__(FirestoreDatabase)
    database.db = MagicMock()
    database.logger = MagicMock()
    payload = {
        'startup_script': 'export MYSQL_PASSWORD=sentinel-password',
        'credentials': {'private_key': 'sentinel-private-key'},
    }
    document = database.db.collection.return_value.document.return_value
    document.id = 'guac-tenant-project'
    snapshot = document.get.return_value
    snapshot.exists = True
    snapshot.to_dict.return_value = payload

    if transactional:
        result = database._transaction_operation(
            transaction=MagicMock(), doc_ref=document, operation=DbOperationTypes.GET,
        )
    else:
        result = database.get(collection_name=DbCollections.IMAGE, doc_id=document.id)

    assert result == payload
    logged = repr(database.logger.mock_calls)
    assert 'guac-tenant-project' in logged
    assert 'sentinel-password' not in logged
    assert 'sentinel-private-key' not in logged
    assert 'startup_script' not in logged

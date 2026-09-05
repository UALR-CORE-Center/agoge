from unittest.mock import MagicMock, patch

from common.document_database.firestore_database import FirestoreDatabase


def test_transaction_uses_firestore_transactional_wrapper():
    database = FirestoreDatabase.__new__(FirestoreDatabase)
    database.db = MagicMock()
    database.logger = MagicMock()
    transaction = database.db.transaction.return_value
    operation = MagicMock()
    transactional_operation = MagicMock(return_value="claimed")

    with patch(
        "common.document_database.firestore_database.firestore.transactional",
        return_value=transactional_operation,
    ) as transactional:
        result = database.transaction(operation, "argument", flag=True)

    assert result == "claimed"
    transactional.assert_called_once_with(operation)
    transactional_operation.assert_called_once_with(
        transaction,
        "argument",
        flag=True,
    )

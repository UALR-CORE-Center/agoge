import logging
from main_app.backend.utilities.globals import DatabaseTypes
from main_app.backend.utilities.document_database.factory import DocumentDatabaseFactory
from main_app.backend.models.agoge import UnitModel

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Sample data for testing
sample_unit_record = {
    "id": "unit_12345",
    "version": "1.0.0",
    "instructor_id": "instructor_abc",
    "build_type": "standard",
    "summary": {
        "name": "Introduction to Cybersecurity",
        "description": "Basic cybersecurity concepts and practice lab."
    },
}

# Initialize database connection
def initialize_database():
    return DocumentDatabaseFactory.create_db_object(
        db_type=DatabaseTypes.firestorm,
        project_id='agoge-test-427119',
        database_name='agoge-test'
    )

# Insert document and verify
def test_insert_document(db, collection_name, data):
    logger.debug("Testing document insertion.")
    unit_model = UnitModel(**data)
    doc_id = db.insert(collection_name=collection_name, data=unit_model.dict())
    assert doc_id is not None, "Document insertion failed; no doc ID returned."
    logger.info(f"Document inserted with ID: {doc_id}")
    return doc_id

# Retrieve document and verify
def test_get_document(db, collection_name, doc_id):
    logger.debug("Testing document retrieval.")
    doc = db.get(collection_name=collection_name, doc_id=doc_id)
    assert doc is not None, f"Document with ID {doc_id} not found."
    logger.info(f"Document retrieved: {doc}")
    return doc

# Update document and verify
def test_update_document(db, collection_name, doc_id, updated_data):
    logger.debug("Testing document update.")
    db.update(collection_name=collection_name, doc_id=doc_id, data=updated_data)
    updated_doc = db.get(collection_name=collection_name, doc_id=doc_id)
    assert updated_doc['instructor_id'] == updated_data['instructor_id'], "Document update failed."
    logger.info("Document updated successfully.")
    return updated_doc

# Delete document and verify
def test_delete_document(db, collection_name, doc_id):
    logger.debug("Testing document deletion.")
    db.delete(collection_name=collection_name, doc_id=doc_id)
    try:
        db.get(collection_name=collection_name, doc_id=doc_id)
    except Exception as e:
        logger.info(f"Document with ID {doc_id} successfully deleted.")
        return True
    raise AssertionError("Document deletion failed.")

# Run the full test
def main():
    db = initialize_database()
    collection_name = 'test_unit'

    try:
        # Step 1: Insert
        doc_id = test_insert_document(db, collection_name, sample_unit_record)

        # Step 2: Retrieve
        doc = test_get_document(db, collection_name, doc_id)

        # Step 3: Update
        doc['instructor_id'] = 'pdhuff@ualr.edu'
        unit_model = UnitModel(**doc)
        test_update_document(db, collection_name, doc_id, unit_model.dict())

        # Step 4: Delete
        test_delete_document(db, collection_name, doc_id)

        logger.info("Firestore test completed successfully.")
    except Exception as e:
        logger.error(f"Test failed: {e}")

if __name__ == "__main__":
    main()

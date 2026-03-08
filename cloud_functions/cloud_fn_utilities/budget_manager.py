from common.constants.database import DbCollections, DatabaseTypes, DATABASE_NAME, ADMIN_INFO_DOCUMENT
from common.document_database import DocumentDatabaseFactory
from common.utilities.gcp.cloud_logger import Logger, LoggerNames


class BudgetManager:
    """
    Handles budget management to avoid cost overruns. A budget_exceeded variable is used in the datastore entity
    admin-info for the project.
    """
    BUDGET_EXCEEDED = "budget_exceeded"

    def __init__(self):
        self.logger = Logger(LoggerNames.CLOUD_FN)
        self.collection = DbCollections.ADMIN_INFO
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME
        )

    def check_budget(self):
        """
        Check whether the budget has been exceeded. If so, cloud functions should not fire.
        @return: Whether the current spending for the month has exceeded the budget.
        @rtype: Boolean
        """
        admin_info = self.db.get(collection_name=self.collection, doc_id=ADMIN_INFO_DOCUMENT)
        if self.BUDGET_EXCEEDED not in admin_info:
            admin_info[self.BUDGET_EXCEEDED] = False
            self.db.update(collection_name=self.collection, doc_id=ADMIN_INFO_DOCUMENT, data=admin_info)
            return True
        else:
            budget_exceeded = admin_info[self.BUDGET_EXCEEDED]

        if budget_exceeded:
            return False
        else:
            return True

    def set_budget_exceeded(self, set_value=True):
        """
        Sets the datastore entity variable
        @param set_value:
        @type set_value:
        @return:
        @rtype:
        """
        admin_info = self.db.get(collection_name=self.collection, doc_id=ADMIN_INFO_DOCUMENT)
        admin_info[self.BUDGET_EXCEEDED] = set_value
        self.db.update(collection_name=self.collection, doc_id=ADMIN_INFO_DOCUMENT, data=admin_info)

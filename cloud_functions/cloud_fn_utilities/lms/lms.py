"""
A base parent class for the LMS object in the Cyber Arena
"""

import random
import string
from abc import ABC, abstractmethod
from typing import Union

from common.constants.database import DbCollections, DatabaseTypes, DbOperators, DATABASE_NAME
from common.document_database import DocumentDatabaseFactory, DatabaseQueries
from common.utilities.gcp.cloud_logger import Logger, LoggerNames


class LMS:
    def __init__(
        self,
        course_code: Union[int, str] = None,
        build: dict = None,
        url: str = None,
        api_key: str = None
    ) -> None:
        self.course_code = course_code
        self.url = url
        self.api_key = api_key
        self.course_code = course_code
        self.build = build
        self.students = []
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME
        )
        self.db_queries = DatabaseQueries(db=self.db)
        self.logger = Logger(LoggerNames.CLOUD_FN)

    def get_class_list(self):
        raise NotImplementedError("get_class_list not implemented for this object.")

    def create_quiz(self):
        raise NotImplementedError("create_quiz not implemented for this object.")

    def create_assignment(self):
        raise NotImplementedError("create_quiz not implemented for this object.")

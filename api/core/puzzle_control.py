import re
import time
import uuid
from difflib import SequenceMatcher
from typing import Any

import unicodedata
from pydantic import ValidationError

from common.constants.database import DbCollections, DatabaseTypes, DATABASE_NAME, DbOperators
from common.document_database import DocumentDatabaseFactory
from common.exceptions import AgogeValidationError
from common.models.agoge import PuzzleQuestionModel, PuzzleTestModel
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import LoggerNames, Logger

import requests

from common.utilities.id_generator import IdGenerator
from common.utilities.timestamps import Timestamps

BASE = "https://openapi.api.govee.com/router/api/v1"

class PuzzleControl:
    def __init__(self):
        self.class_name = self.__class__.__name__
        self.log_name = LoggerNames.API
        self.collection_name = DbCollections.PUZZLE
        self.env = CloudEnv(log_name=self.log_name)
        self.env_dict = self.env.get_env()
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME,
            log_name=self.log_name
        )
        self.logger = Logger(self.log_name, class_name=self.class_name)

    @staticmethod
    def _norm(s: str) -> str:
        s = (s or "").strip().lower()
        s = unicodedata.normalize("NFKD", s)
        s = "".join(ch for ch in s if not unicodedata.combining(ch))
        s = re.sub(r"[^a-z0-9\s]", " ", s)
        return re.sub(r"\s+", " ", s).strip()

    @staticmethod
    def _similarity(a: str, b: str) -> float:
        return SequenceMatcher(None, a, b).ratio() * 100.0


    # Trivia Handlers
    def create_test(self, title, questions, sku, device) -> dict:
        uid = IdGenerator.uuid()
        join_code = uuid.uuid4().hex[:6].upper()
        current_ts = Timestamps.get_current_timestamp_utc()

        try:
            validated_questions = [PuzzleQuestionModel(**q) for q in questions]

            new_test = PuzzleTestModel(
                id=uid,
                title=title,
                questions=validated_questions,
                sku=sku,
                join_code=join_code,
                device=device,
                created_at=current_ts,
            )
        except ValidationError as e:
            self.logger.error(
                f"Validation error: {e}",
                collection_name=self.collection_name,
                doc_id=uid,
            )
            raise AgogeValidationError(f"Create Nerd Night Test failed with validation error: {e}")
        self.db.update(
            collection_name=self.collection_name,
            doc_id=uid,
            data=new_test.model_dump(),
        )
        return {
            "id": uid,
            "join_code": join_code,
            "sku": sku,
            "device": device
        }

    def get_tests(self) -> list[dict]:
        tests = self.db.query(collection_name=self.collection_name)
        simple_tests = []
        for t in tests:
            safe_questions = [
                {
                    "id": q.get("id"),
                    "title": q.get("title")
                }
                for q in t.get("questions")
                if q.get("id") and q.get("title")
            ]
            simple_tests.append({
                "id": t.get("id"),
                "title": t.get("title"),
                "join_code": t.get("join_code"),
                "created_at": t.get("created_at"),
                "questions": safe_questions,
                "LampDevice": {
                    "deviceId": t.get("device"),
                    "sku": t.get("sku")
                }
            })
        return simple_tests

    def get_test(self, join_code) -> dict | None:
        code = str(join_code).strip()
        results = self.db.query(
            collection_name=self.collection_name,
            filters=[('join_code', DbOperators.EQUAL, code)]
        )

        if not results or not isinstance(results, list):
            return None

        test = results[0]

        if not isinstance(test, dict):
            return None

        safe_questions = [
            {"id": q.get("id"), "title": q.get("title"), "hint": q.get("hint")}
            for q in test.get("questions", [])
            if isinstance(q, dict) and q.get("id") and q.get("title")
        ]

        return {
            "id": test.get("id"),
            "title": test.get("title"),
            "join_code": test.get("join_code"),
            "questions": safe_questions,
            "LampDevice": {
                "deviceId": test.get("device"),
                "sku": test.get("sku")
            }
        }


    def check_answer(self, question_id: str, submitted_answer: str, test_id: str) -> dict | None:
        tid = str(test_id).strip()
        qid = str(question_id).strip()
        submitted_raw = (submitted_answer or "").strip()

        results = self.db.query(
            collection_name=self.collection_name,
            filters=[("id", DbOperators.EQUAL, tid)]
        )
        if not results:
            return None

        test = next((r for r in results if r.get("id") == tid), None)
        if not test:
            return None
        questions = test.get("questions") or []
        if isinstance(questions, dict):
            questions = list(questions.values())

        question = next(
            (q for q in questions if str(q.get("id", "")).strip() == qid),
            None
        )
        if not question:
            return None

        correct_raw = (question.get("answer") or "").strip()
        submitted = self._norm(submitted_raw)
        correct = self._norm(correct_raw)

        is_correct = submitted == correct

        if not is_correct and question.get("fuzzy"):
            threshold = 85
            similarity = self._similarity(submitted, correct)
            is_correct = similarity >= threshold

        return {
            "id": str(question.get("id") or ""),
            "title": question.get("title"),
            "isCorrect": bool(is_correct),
        }

    # Lamp Handlers

    def _headers(self, api_key):
        return {"Govee-API-Key": api_key, "Content-Type": "application/json"}

    def list_devices(
            self,
    ) -> dict:
        groove_key = self.env.groove_api_key
        url = f"{BASE}/user/devices"
        r = requests.get(url, headers=self._headers(api_key=groove_key), timeout=15)
        r.raise_for_status()
        devices = r.json().get("data", [])
        return devices

    def control_device(
            self,
            sku,
            device,
            capability
    ) -> dict:
        groove_key = self.env.groove_api_key
        url = f"{BASE}/device/control"
        body = {
            "requestId": str(uuid.uuid4()),
            "payload": {
                "sku": sku,
                "device": device,
                "capability": capability,
            },
        }
        for attempt in range(3):
            r = requests.post(url, headers=self._headers(groove_key), json=body, timeout=15)
            if r.status_code == 429:
                time.sleep(1.5 + attempt)
                continue
            r.raise_for_status()
            return r.json()
import re
import time
from contextlib import contextmanager
from typing import Dict, Iterator, Optional, Union

from common.constants.database import DATABASE_NAME, DatabaseTypes, DbCollections
from common.exceptions.agoge import BadRequest, Conflict, Forbidden, Unauthorized
from common.models.agoge import CtfLogModel, LogAction
from common.models.model_validators.model_validator import ModelValidator
from common.utilities.gcp.cloud_logger import Logger, LoggerNames
from common.utilities.id_generator import IdGenerator

DetailValue = Union[str, int, bool]

# SC-18: core refusing the action is DENIED; anything else that escapes is ERROR.
DENIED_EXCEPTIONS = (Unauthorized, Forbidden, Conflict, BadRequest)
DEFAULT_FLAG_PREFIX = 'agoge'


class CtfAuditEntry:
    """Mutable view of the row being written, yielded to the audited block so it can
    fill in `target` or `detail` it only learns while running."""

    def __init__(self, target: Optional[str], flag_prefixes: tuple) -> None:
        self.target = target
        self.detail: Dict[str, DetailValue] = {}
        self._flag_patterns = [re.compile(re.escape(p) + r'\{', re.IGNORECASE) for p in flag_prefixes]

    def add_detail(self, **values: DetailValue) -> None:
        """Validate every value before storing any, so a rejected call leaves `detail` unchanged."""
        for key, value in values.items():
            # bool is an int subclass; float, None, and containers are not scalar detail.
            if not isinstance(value, (str, int, bool)):
                raise ValueError(f"Audit detail '{key}' must be a str, int, or bool")
            for text in (key, value) if isinstance(value, str) else (key,):
                # Searched anywhere, not just at the start: a flag must never reach an audit row.
                if any(p.search(text) for p in self._flag_patterns):
                    # Never echo the value: it is presumed to be a flag.
                    raise ValueError(f"Audit detail '{key}' looks like a flag value and was rejected")
        self.detail.update(values)


class CtfAudit:
    """Writes exactly one `CtfLogModel` per game-master action (SC-18)."""

    def __init__(self, env_dict: dict = None, db=None) -> None:
        self.class_name = self.__class__.__name__
        self.env_dict = env_dict
        self.logger = Logger(LoggerNames.API, class_name=self.class_name)
        if db is None:
            # Imported lazily so tests supplying a fake db need no Firestore client.
            from common.document_database.factory import DocumentDatabaseFactory

            db = DocumentDatabaseFactory.create_db_object(
                db_type=DatabaseTypes.firestore,
                database_name=DATABASE_NAME,
                log_name=LoggerNames.API,
            )
        self.db = db

    @contextmanager
    def action(
        self,
        ctf_id: str,
        action: LogAction,
        actor: str,
        target: Optional[str] = None,
        detail: Optional[Dict[str, DetailValue]] = None,
        flag_prefix: Optional[str] = None,
    ) -> Iterator[CtfAuditEntry]:
        """Run the block and append one log row: OK if it returns, DENIED if it raises one of
        DENIED_EXCEPTIONS, ERROR for anything else. The exception always propagates.

        `flag_prefix` is the event's prefix; values starting with it (or with `agoge{`) are
        rejected from `detail`. A rejected initial `detail` raises before the block runs and
        still writes an ERROR row, so every audited call leaves exactly one row.
        """
        prefixes = (DEFAULT_FLAG_PREFIX,) if not flag_prefix else (DEFAULT_FLAG_PREFIX, flag_prefix)
        entry = CtfAuditEntry(target=target, flag_prefixes=prefixes)
        result = 'ERROR'
        try:
            entry.add_detail(**(detail or {}))
            yield entry
            result = 'OK'
        except DENIED_EXCEPTIONS:
            result = 'DENIED'
            raise
        finally:
            self._write(ctf_id, action, actor, entry, result)

    def _write(self, ctf_id: str, action: str, actor: str, entry: CtfAuditEntry, result: str) -> None:
        row = {
            'id': IdGenerator.uuid(),
            'ctf_id': ctf_id,
            'action': action,
            'actor': actor,
            'target': entry.target,
            'result': result,
            'detail': dict(entry.detail) or None,
            'created_at': time.time(),
        }
        try:
            log = ModelValidator(model=CtfLogModel, log_location=LoggerNames.API).load(data=row)
            self.db.insert(collection_name=DbCollections.CTF_LOG, data=log.model_dump())
        except Exception as e:
            # Swallowed so a failed audit write neither masks the action's own exception nor
            # turns an action that already happened (e.g. a published replant) into a 500
            # the game master would retry.
            self.logger.error(
                f"{self.class_name}:{ctf_id} - Failed to write audit row: {type(e).__name__}",
                action=action, result=result,
            )

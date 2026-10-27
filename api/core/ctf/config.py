import threading
import time

from common.constants.database import ADMIN_INFO_DOCUMENT, DATABASE_NAME, DatabaseTypes, DbCollections
from common.document_database.factory import DocumentDatabaseFactory
from common.utilities.gcp.cloud_logger import Logger, LoggerNames

# ctf_enabled is read here rather than from the lifespan env_dict, which is
# loaded once per instance: a toggle in setup.py must reach running instances.
CACHE_SECONDS = 60

_lock = threading.Lock()
# The whole admin-info document is cached so budget_exceeded rides on the same read.
_cached_info = {}
_expires_at = 0.0
_db = None

logger = Logger(LoggerNames.API, class_name='CtfConfig')


def _get_db():
    global _db
    if _db is None:
        _db = DocumentDatabaseFactory.create_db_object(
            DatabaseTypes.firestore,
            database_name=DATABASE_NAME,
            log_name=LoggerNames.API,
        )
    return _db


def _admin_info():
    """admin-info/project, cached in-process for CACHE_SECONDS; None when the read fails."""
    global _cached_info, _expires_at
    with _lock:
        now = time.monotonic()
        if now < _expires_at:
            return _cached_info
        try:
            admin_info = _get_db().get(collection_name=DbCollections.ADMIN_INFO, doc_id=ADMIN_INFO_DOCUMENT)
        except Exception as e:
            # Don't cache the failure, so the next request retries.
            logger.error(f"CtfConfig - Failed to read admin-info: {type(e).__name__}")
            return None
        _cached_info = admin_info or {}
        _expires_at = now + CACHE_SECONDS
        return _cached_info


def is_ctf_enabled() -> bool:
    """Whether CTF is enabled on admin-info/project; cached in-process for CACHE_SECONDS.
    Fails closed when admin-info cannot be read."""
    # Only a real True enables the feature; a stray "false" string must not.
    return (_admin_info() or {}).get('ctf_enabled') is True


def is_budget_exceeded() -> bool:
    """Whether BudgetManager has halted the Cloud Function. The function halts silently, so the
    dashboard shows this as a banner. Unknown (a failed read) reports False."""
    return (_admin_info() or {}).get('budget_exceeded') is True


def reset_cache() -> None:
    """Forget the cached flag so the next call re-reads Firestore."""
    global _expires_at
    with _lock:
        _expires_at = 0.0

import math
import time
from typing import Optional, Tuple

from common.constants.database import DATABASE_NAME, DatabaseTypes, DbCollections, DbOperators
from common.constants.states import CtfStates
from common.exceptions.agoge import Conflict, NotFound, RateLimitExceeded
from common.models.agoge import (
    CtfBoardModel,
    CtfDigestModel,
    CtfEventModel,
    CtfRateLimitModel,
    CtfSubmissionModel,
    Verdict,
)
from common.models.model_validators.model_validator import ModelValidator
from common.models.response import CtfSubmitResponse
from common.utilities.ctf_flags import flag_digest, parse_flag_id
from common.utilities.gcp.cloud_logger import Logger, LoggerNames
from common.utilities.id_generator import IdGenerator

SUBMISSIONS_CLOSED_MESSAGE = "Submissions are closed."
RATE_LIMIT_WINDOW_SECONDS = 60
UNPARSED_BUCKET = "unparsed"


class CtfScoring:
    """Student-facing scoring for a CTF board: flag submission (PRD Submission Algorithm)."""
    MESSAGES = {
        'correct': "Correct! Flag accepted.",
        'incorrect': "Incorrect flag.",
        'duplicate': "Your team has already solved this flag.",
        'decoy': "That flag is out of scope for this exercise.",
    }

    def __init__(self, env_dict: dict = None, db=None) -> None:
        self.class_name = self.__class__.__name__
        self.log_name = LoggerNames.API
        self.logger = Logger(self.log_name, class_name=self.class_name)
        self.env_dict = env_dict
        if db is None:
            # Imported lazily so tests supplying a fake db need no Firestore client.
            from common.document_database.factory import DocumentDatabaseFactory

            db = DocumentDatabaseFactory.create_db_object(
                db_type=DatabaseTypes.firestore,
                database_name=DATABASE_NAME,
                log_name=self.log_name,
            )
        self.db = db

    def submit(self, workout_id: str, flag: str, origin_ip: Optional[str] = None) -> CtfSubmitResponse:
        """Resolve one submitted flag against the workout's active board and record it.

        The submitted value is never stored or logged; only its digest is.
        """
        board = self._active_board(workout_id)
        event = self._load_event(board.ctf_id)
        parsed_flag_id = parse_flag_id(flag, event.spec.scoring.flag_prefix)
        digest = flag_digest(flag)

        # Step 1: only a RUNNING event accepts flags; the refusal is still recorded.
        if event.state != CtfStates.RUNNING.value:
            self._record(event.id, workout_id, digest, 'closed', parsed_flag_id, origin_ip)
            raise Conflict(message=SUBMISSIONS_CLOSED_MESSAGE)

        # Step 2: a Firestore transaction, not an in-memory limiter, because Cloud Run runs several
        # instances. Values that don't parse share one bucket, so guessing can't dodge the limit.
        bucket = parsed_flag_id or UNPARSED_BUCKET
        retry_after = self.db.transaction(
            lambda transaction: self._rate_limit_in_transaction(
                transaction, event.id, workout_id, bucket, event.spec.scoring.submission_rate_limit,
            )
        )
        if retry_after is not None:
            self._record(event.id, workout_id, digest, 'rate_limited', parsed_flag_id, origin_ip)
            self.logger.warning(f"{self.class_name}:{event.id} - Submission rate limited",
                                workout_id=workout_id, bucket=bucket)
            raise RateLimitExceeded(
                message=f"Too many submissions for this challenge. Try again in {retry_after} seconds."
            )

        # Steps 3-5: one digest read resolves the value to the board and flag it was derived for.
        match = self._digest(digest)
        matched_workout_id = None
        points = 0
        if match is None or match.ctf_id != event.id:
            verdict, flag_id = 'incorrect', parsed_flag_id
        elif match.workout_id != workout_id:
            # Another team's flag: recorded for the game master, answered as plain `incorrect`.
            verdict, flag_id, matched_workout_id = 'cross_submission', match.flag_id, match.workout_id
        else:
            # Step 6: read and award inside one board transaction, so concurrent submissions of
            # one flag yield exactly one `correct` (SC-12).
            verdict, points = self.db.transaction(
                lambda transaction: self._award_in_transaction(transaction, event, board.id, match.flag_id, parsed_flag_id)
            )
            flag_id = match.flag_id

        # Step 7
        self._record(event.id, workout_id, digest, verdict, flag_id, origin_ip,
                     matched_workout_id=matched_workout_id, points_awarded=points)
        self.logger.info(f"{self.class_name}:{event.id} - Flag submitted", workout_id=workout_id, verdict=verdict)

        shown = 'incorrect' if verdict == 'cross_submission' else verdict
        shown_points = points
        if verdict == 'decoy' and not event.spec.scoring.reveal_decoy_penalty:
            shown_points = 0
        return CtfSubmitResponse(
            verdict=shown,
            correct=verdict == 'correct',
            points_awarded=shown_points,
            message=self.MESSAGES[shown],
        )

    def _rate_limit_in_transaction(
        self, transaction, ctf_id: str, workout_id: str, bucket: str, limit: int
    ) -> Optional[int]:
        """Count this submission in its 60 s window; return seconds until the window ends when over the limit."""
        doc_id = f"{ctf_id}-{workout_id}-{bucket}"
        doc_ref = self.db.db.collection(DbCollections.CTF_RATE_LIMIT.value).document(doc_id)
        snapshot = doc_ref.get(transaction=transaction)
        current = None
        if snapshot.exists:
            # An unreadable counter is treated as a fresh window rather than blocking the team.
            current = ModelValidator(CtfRateLimitModel, log_location=self.log_name).load(
                snapshot.to_dict(), halt_on_error=False
            )
        now = time.time()
        if current is None or now - current.window_start >= RATE_LIMIT_WINDOW_SECONDS:
            transaction.set(doc_ref, CtfRateLimitModel(id=doc_id, window_start=now, count=1).model_dump())
            return None
        if current.count >= limit:
            # A refused submission is not counted, so hammering cannot push the window's end back.
            return max(1, math.ceil(current.window_start + RATE_LIMIT_WINDOW_SECONDS - now))
        transaction.update(doc_ref, {'count': current.count + 1})
        return None

    def _award_in_transaction(
        self, transaction, event: CtfEventModel, board_id: str, flag_id: str, parsed_flag_id: Optional[str]
    ) -> Tuple[Verdict, int]:
        """Step 6: duplicate, decoy, or solve, decided from the board as read inside the transaction."""
        board_ref = self.db.db.collection(DbCollections.CTF_BOARD.value).document(board_id)
        snapshot = board_ref.get(transaction=transaction)
        if not snapshot.exists:
            raise NotFound(message="CTF board not found")
        board = ModelValidator(CtfBoardModel, log_location=self.log_name).load(snapshot.to_dict())
        spec_flag = next((f for f in event.spec.flags if f.id == flag_id), None)
        state = next((f for f in board.flags if f.flag_id == flag_id), None)
        now = time.time()
        updates = {}

        if spec_flag is None or state is None:
            # A digest for a flag the event or board no longer carries cannot be scored.
            self.logger.warning(
                f"{self.class_name}:{event.id} - Digest matched a flag missing from the spec or board",
                workout_id=board.workout_id, flag_id=flag_id,
            )
            verdict, points = 'incorrect', 0
        elif state.solved:
            verdict, points = 'duplicate', 0
        elif spec_flag.decoy:
            # A decoy is never marked solved, so each submission is another scope observation;
            # the rate limit bounds how often that can happen.
            verdict, points = 'decoy', spec_flag.points
            updates['score'] = board.score + points
            updates['decoy_count'] = board.decoy_count + 1
        else:
            verdict, points = 'correct', spec_flag.points
            state.solved = True
            state.solved_at = now
            updates['score'] = board.score + points
            updates['solve_count'] = board.solve_count + 1
            updates['last_solve_at'] = now

        attempted = next((f for f in board.flags if f.flag_id == parsed_flag_id), None)
        if attempted is not None:
            attempted.attempts += 1
        if attempted is not None or verdict == 'correct':
            updates['flags'] = [f.model_dump() for f in board.flags]
        if updates:
            transaction.update(board_ref, updates)
        return verdict, points

    def _active_board(self, workout_id: str) -> CtfBoardModel:
        docs = self.db.query(
            collection_name=DbCollections.CTF_BOARD,
            filters=[
                ('workout_id', DbOperators.EQUAL, workout_id),
                ('active', DbOperators.EQUAL, True),
            ],
        ) or []
        boards = ModelValidator(CtfBoardModel, log_location=self.log_name).load(docs, halt_on_error=False)
        boards = [board for board in boards if board is not None]
        if not boards:
            raise NotFound(message="CTF board not found")
        if len(boards) > 1:
            # Event creation refuses a workout already on an active board, so this is data drift.
            self.logger.error(
                f"{self.class_name}:{workout_id} - Workout has more than one active CTF board",
                count=len(boards),
            )
        return boards[0]

    def _load_event(self, ctf_id: str) -> CtfEventModel:
        doc = self.db.get(collection_name=DbCollections.CTF, doc_id=ctf_id)
        if not doc:
            raise NotFound(message="CTF event not found")
        return ModelValidator(CtfEventModel, log_location=self.log_name).load(doc)

    def _digest(self, digest: str) -> Optional[CtfDigestModel]:
        doc = self.db.get(collection_name=DbCollections.CTF_DIGEST, doc_id=digest)
        if not doc:
            return None
        return ModelValidator(CtfDigestModel, log_location=self.log_name).load(doc, halt_on_error=False)

    def _record(
        self, ctf_id: str, workout_id: str, digest: str, verdict: Verdict, flag_id: Optional[str],
        origin_ip: Optional[str], matched_workout_id: Optional[str] = None, points_awarded: int = 0,
    ) -> None:
        """Append one CtfSubmissionModel. It holds the digest, never the submitted value (SC-4)."""
        row = ModelValidator(CtfSubmissionModel, log_location=self.log_name).load({
            'id': IdGenerator.uuid(),
            'ctf_id': ctf_id,
            'workout_id': workout_id,
            'flag_id': flag_id,
            'submitted_digest': digest,
            'verdict': verdict,
            'matched_workout_id': matched_workout_id,
            'points_awarded': points_awarded,
            'submitted_at': time.time(),
            'origin_ip': origin_ip,
        })
        self.db.insert(collection_name=DbCollections.CTF_SUBMISSION, data=row.model_dump())

from datetime import datetime, timezone
from typing import Optional, Union

from common.constants.database import DATABASE_NAME, DatabaseTypes, DbCollections
from common.constants.states import CtfStates
from common.exceptions.agoge import Conflict, NotFound
from common.models.agoge import CtfEventModel
from common.models.model_validators.model_validator import ModelValidator
from common.utilities.gcp.cloud_logger import Logger, LoggerNames


class CtfStateManager:
    """Allow-listed state transitions for CTF events (collection `agoge-ctf`).

    Standalone rather than a `BaseStateManager` subclass: the API transitions event
    state too, and `BaseStateManager.state_transition()` never checks its allow-list.
    """
    S = CtfStates
    VALID_TRANSITIONS = {
        (S.DRAFT, S.ARMING), (S.DRAFT, S.ARCHIVED),
        (S.ARMING, S.ARMED), (S.ARMING, S.BROKEN),
        (S.ARMED, S.ARMING), (S.ARMED, S.RUNNING), (S.ARMED, S.ARCHIVED),
        (S.RUNNING, S.PAUSED), (S.RUNNING, S.ENDED),
        (S.PAUSED, S.RUNNING), (S.PAUSED, S.ENDED),
        (S.ENDED, S.ARCHIVED),
        (S.BROKEN, S.ARMING), (S.BROKEN, S.ARCHIVED),
    }
    # Written by the manager itself (or immutable); never accepted as extra fields.
    PROTECTED_FIELDS = {'id', 'state', 'state_timestamp'}

    def __init__(
        self,
        db=None,
        log_name: LoggerNames = LoggerNames.API
    ) -> None:
        self.class_name = self.__class__.__name__
        self.log_name = log_name
        self.logger = Logger(log_name, class_name=self.class_name)
        if db is None:
            # Imported lazily so tests supplying a fake db need no Firestore client.
            from common.document_database.factory import DocumentDatabaseFactory

            db = DocumentDatabaseFactory.create_db_object(
                db_type=DatabaseTypes.firestore,
                database_name=DATABASE_NAME,
                log_name=log_name
            )
        self.db = db

    @classmethod
    def is_valid_transition(
        cls,
        current_state: Union[CtfStates, int],
        new_state: Union[CtfStates, int]
    ) -> bool:
        try:
            return (CtfStates(cls._value(current_state)), CtfStates(cls._value(new_state))) in cls.VALID_TRANSITIONS
        except ValueError:
            return False

    def transition(
        self,
        ctf_id: str,
        new_state: Union[CtfStates, int],
        **fields
    ) -> CtfEventModel:
        """Transition an event in its own Firestore transaction.

        Raises NotFound if the event does not exist and Conflict if (current, new) is
        not allowed. `fields` are extra CtfEventModel fields written in the same update.
        """
        return self.db.transaction(
            lambda transaction: self.transition_in_transaction(transaction, ctf_id, new_state, **fields)
        )

    def transition_in_transaction(
        self,
        transaction,
        ctf_id: str,
        new_state: Union[CtfStates, int],
        event: Optional[dict] = None,
        **fields
    ) -> CtfEventModel:
        """Transition inside a caller's transaction.

        Firestore requires every read before the first write, so a caller that has
        already written in this transaction (e.g. the arm aggregation) must pass the
        event dict it read earlier as `event`; otherwise it is read here.
        """
        self._check_fields(fields)
        new_state = CtfStates(self._value(new_state))
        doc_ref = self.db.db.collection(DbCollections.CTF.value).document(ctf_id)
        if event is None:
            snapshot = doc_ref.get(transaction=transaction)
            if not snapshot.exists:
                raise NotFound(f"CTF event {ctf_id} not found")
            event = snapshot.to_dict()

        current_state = event.get('state')
        if not self.is_valid_transition(current_state, new_state):
            current_name = CtfStates(current_state).name if current_state in CtfStates._value2member_map_ \
                else str(current_state)
            raise Conflict(f"CTF event {ctf_id} cannot move from {current_name} to {new_state.name}")

        updated = {
            **event,
            **fields,
            'state': new_state.value,
            'state_timestamp': datetime.now(timezone.utc).isoformat(),
        }
        # Raises ValidationError before anything is written, so a bad field aborts the transaction.
        validated = ModelValidator(model=CtfEventModel, log_location=self.log_name).load(data=updated)
        dumped = validated.model_dump()
        mask = {key: dumped[key] for key in ['state', 'state_timestamp', *fields]}
        transaction.update(doc_ref, mask)

        self.logger.info(
            f"{self.class_name}:{ctf_id} - State Transition from {CtfStates(current_state).name} to {new_state.name}",
            existing_state=CtfStates(current_state).name,
            new_state=new_state.name
        )
        return validated

    def _check_fields(self, fields: dict) -> None:
        protected = self.PROTECTED_FIELDS & fields.keys()
        if protected:
            raise ValueError(f"{self.class_name} - fields {sorted(protected)} cannot be set through a transition")
        # CtfEventModel ignores unknown keys, so without this check a typo would be written to Firestore.
        unknown = fields.keys() - CtfEventModel.model_fields.keys()
        if unknown:
            raise ValueError(f"{self.class_name} - unknown CtfEventModel fields {sorted(unknown)}")

    @staticmethod
    def _value(state: Union[CtfStates, int]) -> int:
        return state.value if isinstance(state, CtfStates) else state

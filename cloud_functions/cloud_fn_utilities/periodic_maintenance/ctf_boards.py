from common.constants.database import DbCollections, DbOperators
from common.constants.states import CtfStates

# A board in one of these event states must keep running: the game master has armed it or the
# clock is running, and a stop would break the plant and the teams' progress on the hosts.
CTF_KEEP_RUNNING_STATES = (CtfStates.ARMING, CtfStates.ARMED, CtfStates.RUNNING, CtfStates.PAUSED)


def live_ctf_workout_ids(db) -> set:
    """Workout ids of the active boards in every event that is armed or in play"""
    events = db.query(
        collection_name=DbCollections.CTF,
        filters=[('state', DbOperators.IN, [state.value for state in CTF_KEEP_RUNNING_STATES])]
    )
    workout_ids = set()
    for event in events or []:
        boards = db.query(
            collection_name=DbCollections.CTF_BOARD,
            filters=[('ctf_id', DbOperators.EQUAL, event['id']), ('active', DbOperators.EQUAL, True)]
        )
        workout_ids.update(board['workout_id'] for board in boards or [])
    return workout_ids

from common.constants.database import DbCollections
from common.constants.pub_sub import PubSub
from common.constants.states import CtfStates

CTF_ACTIONS = ('CTF_ARM_BOARD', 'CTF_PLANT', 'CTF_HOST_RESET')


def test_ctf_actions_do_not_collide_with_existing_actions():
    # A duplicate Enum value silently becomes an alias of the earlier member, so the
    # cloud function would dispatch a CTF message as e.g. RESET_EXPIRATION. __members__
    # includes aliases; iteration does not — equal lengths mean every value is unique.
    members = PubSub.Actions.__members__
    assert len(members) == len(list(PubSub.Actions))
    for name in CTF_ACTIONS:
        assert members[name].name == name
    existing = {m.value for n, m in members.items() if n not in CTF_ACTIONS}
    assert existing.isdisjoint({members[n].value for n in CTF_ACTIONS})
    assert [members[n].value for n in CTF_ACTIONS] == [18, 19, 20]


def test_ctf_handler_and_event_attributes():
    assert PubSub.Handlers.CTF.value == 'CTF'
    assert PubSub.EventAttributes.CTF_ID == 'ctf_id'
    assert PubSub.EventAttributes.WORKOUT_ID == 'workout_id'
    assert PubSub.EventAttributes.RESET_MODE == 'reset_mode'


def test_ctf_collections_are_unique():
    ctf = {m.value for m in DbCollections if m.name.startswith('CTF')}
    assert ctf == {'agoge-ctf', 'agoge-ctf-board', 'agoge-ctf-digest', 'agoge-ctf-rate-limit',
                   'agoge-ctf-submission', 'agoge-ctf-log'}
    assert len(DbCollections.__members__) == len(list(DbCollections))


def test_ctf_states():
    assert [s.name for s in CtfStates] == ['DRAFT', 'ARMING', 'ARMED', 'RUNNING', 'PAUSED',
                                           'ENDED', 'ARCHIVED', 'BROKEN']
    assert [s.value for s in CtfStates] == list(range(8))

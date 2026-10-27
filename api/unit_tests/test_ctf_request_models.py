import pytest
from pydantic import ValidationError

from common.models.agoge import (
    MAX_CTF_TEAM_MEMBERS, CtfActionRequest, CtfCreateRequest, CtfHostResetRequest, CtfReplantRequest,
    CtfScoreAdjustRequest, CtfServersRequest, CtfSpecUpdateRequest, CtfSubmitRequest, CtfTeamMembersRequest,
    CtfTeamRequest, CtfUpdateRequest,
)


def test_create_accepts_a_spec_id_and_expiry():
    request = CtfCreateRequest(spec_id='web-lab', expires=1893456000)
    assert (request.spec_id, request.name, request.expires) == ('web-lab', None, 1893456000)


def test_create_accepts_a_name_override():
    assert CtfCreateRequest(spec_id='web-lab', expires=1.5, name='Fall CTF').name == 'Fall CTF'


@pytest.mark.parametrize('kwargs', [
    {}, {'spec_id': 'x'}, {'expires': 5}, {'spec_id': '', 'expires': 5}, {'spec_id': 'x' * 201, 'expires': 5},
    {'spec_id': 'x', 'expires': 0}, {'spec_id': 'x', 'expires': -1}, {'spec_id': 'x', 'expires': 5, 'name': ''},
    {'spec_id': 'x', 'expires': 5, 'name': 'n' * 101}, {'unit_id': 'abcdefghij'},
])
def test_create_rejects_bad_input(kwargs):
    with pytest.raises(ValidationError):
        CtfCreateRequest(**kwargs)


def test_team_members_are_trimmed_lowercased_and_deduplicated_in_order():
    request = CtfTeamMembersRequest(members=[' B@X.edu ', 'a@x.edu', 'b@x.edu', 'A@x.EDU'])
    assert request.members == ['b@x.edu', 'a@x.edu']


@pytest.mark.parametrize('members', [[], ['plain'], ['a@b'], ['a b@x.edu'], ['@x.edu'], ['a@x.edu', ''], [' ']])
def test_team_members_reject_empty_or_malformed_emails(members):
    with pytest.raises(ValidationError):
        CtfTeamMembersRequest(members=members)


def test_team_members_cap_is_fifty():
    assert len(CtfTeamMembersRequest(members=[f'm{i}@x.edu' for i in range(MAX_CTF_TEAM_MEMBERS)]).members) == 50
    with pytest.raises(ValidationError):
        CtfTeamMembersRequest(members=[f'm{i}@x.edu' for i in range(MAX_CTF_TEAM_MEMBERS + 1)])


def test_team_request_strips_the_name_and_normalizes_members():
    request = CtfTeamRequest(team_name='  Red Team ', members=['A@x.edu'])
    assert (request.team_name, request.members) == ('Red Team', ['a@x.edu'])


@pytest.mark.parametrize('team_name', ['', '   ', 'n' * 65])
def test_team_request_rejects_a_blank_or_long_name(team_name):
    with pytest.raises(ValidationError):
        CtfTeamRequest(team_name=team_name, members=['a@x.edu'])


def test_team_request_requires_a_name():
    with pytest.raises(ValidationError):
        CtfTeamRequest(members=['a@x.edu'])


def test_spec_update_requires_a_valid_ctf_block():
    flag = {'id': 'web-root', 'server': 'web', 'slot': 1, 'location_type': 'file', 'path': '/root/f.txt',
            'operating_system': 'linux', 'points': 10}
    assert CtfSpecUpdateRequest(ctf={'name': 'N', 'flags': [flag]}).ctf.flags[0].id == 'web-root'
    with pytest.raises(ValidationError):
        CtfSpecUpdateRequest(ctf={'name': 'N', 'flags': []})
    with pytest.raises(ValidationError):
        CtfSpecUpdateRequest()


@pytest.mark.parametrize('action', ['build', 'start', 'stop'])
def test_servers_accepts_known_actions(action):
    assert CtfServersRequest(action=action).action == action


@pytest.mark.parametrize('action', ['delete', 'BUILD', '', 'restart'])
def test_servers_rejects_unknown_actions(action):
    with pytest.raises(ValidationError):
        CtfServersRequest(action=action)


def test_update_empty_body_sets_no_fields():
    assert CtfUpdateRequest().model_fields_set == set()


def test_update_explicit_null_is_distinguishable_from_absent():
    # An explicit null for scoreboard_frozen_at means "unfreeze", so core must see it as set.
    request = CtfUpdateRequest.model_validate({'scoreboard_frozen_at': None})
    assert request.model_fields_set == {'scoreboard_frozen_at'}
    assert request.scoreboard_frozen_at is None


def test_update_accepts_all_fields():
    request = CtfUpdateRequest(ends_at=1700000000.0, scoreboard_frozen_at=1699999000.0,
                               public_scoreboard_enabled=True)
    assert request.model_fields_set == {'ends_at', 'scoreboard_frozen_at', 'public_scoreboard_enabled'}


@pytest.mark.parametrize('action', ['arm', 'start', 'pause', 'resume', 'end', 'archive'])
def test_action_accepts_known_actions(action):
    assert CtfActionRequest(action=action).action == action


@pytest.mark.parametrize('action', ['delete', 'ARM', '', 'restart'])
def test_action_rejects_unknown_action(action):
    with pytest.raises(ValidationError):
        CtfActionRequest(action=action)


def test_replant_defaults_to_everything():
    request = CtfReplantRequest()
    assert request.workout_ids is None
    assert request.servers is None


def test_replant_accepts_targets():
    request = CtfReplantRequest(workout_ids=['abcdefghij'], servers=['web-server'])
    assert request.workout_ids == ['abcdefghij']
    assert request.servers == ['web-server']


@pytest.mark.parametrize('mode', ['replant', 'restart', 'rebuild'])
def test_host_reset_accepts_known_modes(mode):
    assert CtfHostResetRequest(mode=mode).mode == mode


@pytest.mark.parametrize('mode', ['nuke', 'Rebuild', ''])
def test_host_reset_rejects_unknown_mode(mode):
    with pytest.raises(ValidationError):
        CtfHostResetRequest(mode=mode)


def test_host_reset_guest_is_optional():
    assert CtfHostResetRequest(mode='replant').guest is None
    assert CtfHostResetRequest(mode='restart', guest='win-dc').guest == 'win-dc'


@pytest.mark.parametrize('guest', ['a', 'Win-dc', 'web_1', '../x', 'x' * 33])
def test_host_reset_rejects_bad_guest_slug(guest):
    with pytest.raises(ValidationError):
        CtfHostResetRequest(mode='replant', guest=guest)


@pytest.mark.parametrize('delta', [-10000, -1, 0, 1, 10000])
def test_score_adjust_accepts_delta_in_range(delta):
    assert CtfScoreAdjustRequest(delta=delta, reason='manual fix').delta == delta


@pytest.mark.parametrize('delta', [-10001, 10001])
def test_score_adjust_rejects_delta_out_of_range(delta):
    with pytest.raises(ValidationError):
        CtfScoreAdjustRequest(delta=delta, reason='manual fix')


@pytest.mark.parametrize('reason', ['', 'x' * 501])
def test_score_adjust_rejects_bad_reason_length(reason):
    with pytest.raises(ValidationError):
        CtfScoreAdjustRequest(delta=5, reason=reason)


def test_score_adjust_requires_reason():
    with pytest.raises(ValidationError):
        CtfScoreAdjustRequest(delta=5)


def test_submit_accepts_flag():
    assert CtfSubmitRequest(flag='agoge{abc}').flag == 'agoge{abc}'


@pytest.mark.parametrize('flag', ['', 'x' * 201])
def test_submit_rejects_bad_flag_length(flag):
    with pytest.raises(ValidationError):
        CtfSubmitRequest(flag=flag)

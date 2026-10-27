import pytest
from pydantic import ValidationError

from common.models.response import (
    AgogeResponse, CtfBoardStatus, CtfChallenge, CtfConfigResponse, CtfEventSummary, CtfFlagBoardStatus,
    CtfFlagRevealResponse, CtfFlagRow, CtfHintResponse, CtfHostRow, CtfPublicScoreboardRow, CtfScoreboardRow,
    CtfStateResponse, CtfStudentBoardResponse, CtfSubmitResponse,
)


def _board_status(**overrides):
    data = {'workout_id': 'abcdefghij', 'team_name': 'Red', 'arm_status': 'armed', 'arm_error': None,
            'plant_failed_count': 0, 'plant_stale_count': 0}
    data.update(overrides)
    return data


def _state(**overrides):
    data = {'id': 'klmnopqrst', 'state': 3, 'state_name': 'RUNNING', 'state_timestamp': '1700000000.0',
            'starts_at': 1700000000.0, 'ends_at': None, 'paused_at': None, 'accumulated_pause_seconds': 0.0,
            'scoreboard_frozen_at': None, 'public_scoreboard_enabled': False, 'budget_exceeded': False,
            'boards': [_board_status()]}
    data.update(overrides)
    return data


def _flag_board(**overrides):
    data = {'workout_id': 'abcdefghij', 'team_name': 'Red', 'plant_status': 'planted',
            'planted_at': 1700000000.0, 'plant_error': None, 'solved': False}
    data.update(overrides)
    return data


def _flag_row(**overrides):
    data = {'flag_id': 'web-root', 'server': 'web', 'slot': 0, 'category': 'web', 'location_type': 'file',
            'points': 100, 'decoy': False, 'boards': [_flag_board()]}
    data.update(overrides)
    return data


def _challenge(**overrides):
    data = {'flag_id': 'web-root', 'category': None, 'points': 100, 'solved': False, 'solved_at': None,
            'hint_available': True, 'hint_cost': 10, 'hint': None}
    data.update(overrides)
    return data


def test_config_response():
    assert CtfConfigResponse(ctf_enabled=True).ctf_enabled is True


def test_event_summary_round_trips():
    summary = CtfEventSummary(id='klmnopqrst', name='Spring CTF', unit_id='abcdefghij', state=0,
                              state_name='DRAFT', board_count=4, creation_timestamp=1700000000.0,
                              starts_at=None, ends_at=None)
    assert CtfEventSummary(**summary.model_dump()) == summary


def test_event_summary_optional_times_are_still_required_keys():
    # Optional without a default is required in Pydantic v2; the API must always send starts_at/ends_at.
    with pytest.raises(ValidationError):
        CtfEventSummary(id='klmnopqrst', name='x', unit_id='abcdefghij', state=0, state_name='DRAFT',
                        board_count=0, creation_timestamp=0.0)


def test_state_response_nests_boards():
    state = CtfStateResponse(**_state())
    assert state.boards[0].arm_status == 'armed'
    assert CtfStateResponse(**state.model_dump()) == state


def test_board_status_rejects_unknown_arm_status():
    with pytest.raises(ValidationError):
        CtfBoardStatus(**_board_status(arm_status='done'))


def test_state_response_rejects_bad_nested_board():
    with pytest.raises(ValidationError):
        CtfStateResponse(**_state(boards=[_board_status(arm_status='bogus')]))


@pytest.mark.parametrize('status', ['pending', 'planting', 'planted', 'failed', 'stale'])
def test_flag_board_status_accepts_plant_statuses(status):
    assert CtfFlagBoardStatus(**_flag_board(plant_status=status)).plant_status == status


def test_flag_board_status_rejects_unknown_plant_status():
    with pytest.raises(ValidationError):
        CtfFlagBoardStatus(**_flag_board(plant_status='done'))


def test_flag_row_nests_boards():
    row = CtfFlagRow(**_flag_row())
    assert row.boards[0].plant_status == 'planted'


def test_flag_row_rejects_unknown_location_type():
    with pytest.raises(ValidationError):
        CtfFlagRow(**_flag_row(location_type='cookie'))


def test_flag_reveal_response():
    reveal = CtfFlagRevealResponse(flag_id='web-root', workout_id='abcdefghij', value='agoge{web-root_0123}')
    assert reveal.value == 'agoge{web-root_0123}'


def test_host_row():
    row = CtfHostRow(workout_id='abcdefghij', team_name='Red', server='web', server_state=None,
                     server_state_name=None, flag_count=2, rebuild_allowed=False)
    assert row.rebuild_allowed is False
    assert row.guest is None  # a parent-server row; guest rows set it


def test_host_row_guest():
    row = CtfHostRow(workout_id='abcdefghij', team_name='Red', server='hv-host', server_state=None,
                     server_state_name=None, flag_count=1, rebuild_allowed=True, guest='win-dc')
    assert row.guest == 'win-dc'
    with pytest.raises(ValidationError):
        CtfHostRow(workout_id='abcdefghij', team_name='Red', server='hv-host', server_state=None,
                   server_state_name=None, flag_count=1, rebuild_allowed=True, guest='Win DC')


def test_scoreboard_rows():
    row = CtfScoreboardRow(rank=1, workout_id='abcdefghij', team_name='Red', score=-50, solve_count=0,
                           decoy_count=1, last_solve_at=None)
    assert row.score == -50
    public = CtfPublicScoreboardRow(rank=1, team_label='Team 1', score=100, solve_count=1, is_you=True)
    assert 'workout_id' not in public.model_dump()  # the student board must not leak other teams' workout ids


def test_student_board_not_enrolled_needs_only_flag():
    board = CtfStudentBoardResponse(enrolled=False)
    assert board.challenges == []
    assert board.public_scoreboard_enabled is False
    assert board.ctf_id is None and board.score is None


def test_student_board_enrolled_with_challenges():
    board = CtfStudentBoardResponse(enrolled=True, ctf_id='klmnopqrst', name='Spring CTF', state_name='RUNNING',
                                    remaining_seconds=600, score=90,
                                    challenges=[_challenge(), _challenge(flag_id='db-root', hint='look in /etc')])
    assert [c.flag_id for c in board.challenges] == ['web-root', 'db-root']
    assert board.challenges[1].hint == 'look in /etc'


def test_student_board_default_challenges_are_not_shared():
    first = CtfStudentBoardResponse(enrolled=True)
    first.challenges.append(CtfChallenge(**_challenge()))
    assert CtfStudentBoardResponse(enrolled=True).challenges == []


@pytest.mark.parametrize('verdict', ['correct', 'incorrect', 'duplicate', 'decoy'])
def test_submit_response_accepts_student_verdicts(verdict):
    response = CtfSubmitResponse(verdict=verdict, correct=verdict == 'correct', points_awarded=0, message='ok')
    assert response.verdict == verdict


@pytest.mark.parametrize('verdict', ['cross_submission', 'rate_limited', 'closed'])
def test_submit_response_rejects_internal_verdicts(verdict):
    # These are stored verdicts only; the student sees 'incorrect' or an HTTP 429/409 instead.
    with pytest.raises(ValidationError):
        CtfSubmitResponse(verdict=verdict, correct=False, points_awarded=0, message='x')


def test_hint_response():
    hint = CtfHintResponse(flag_id='web-root', hint='look in /etc', hint_cost=10, score=90)
    assert hint.score == 90


def test_wraps_in_agoge_response_envelope():
    envelope = AgogeResponse[CtfStateResponse](data=CtfStateResponse(**_state()))
    assert envelope.model_dump()['data']['boards'][0]['workout_id'] == 'abcdefghij'

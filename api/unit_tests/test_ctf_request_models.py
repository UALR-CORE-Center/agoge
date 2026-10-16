import pytest
from pydantic import ValidationError

from common.models.agoge import (
    CtfActionRequest, CtfCreateRequest, CtfHostResetRequest, CtfReplantRequest, CtfScoreAdjustRequest,
    CtfSubmitRequest, CtfUpdateRequest,
)


def test_create_accepts_build_id():
    assert CtfCreateRequest(unit_id='abcdefghij').unit_id == 'abcdefghij'


@pytest.mark.parametrize('unit_id', ['abcdefghi', 'abcdefghijk', 'ABCDEFGHIJ', 'abcde12345', ''])
def test_create_rejects_non_build_id(unit_id):
    with pytest.raises(ValidationError):
        CtfCreateRequest(unit_id=unit_id)


def test_create_requires_unit_id():
    with pytest.raises(ValidationError):
        CtfCreateRequest()


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

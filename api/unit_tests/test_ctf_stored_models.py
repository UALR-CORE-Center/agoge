import pytest
from pydantic import ValidationError

from common.constants.states import CtfStates
from common.models.agoge import (
    CtfBoardModel, CtfDigestModel, CtfEventModel, CtfFlagStateModel, CtfLogModel, CtfRateLimitModel,
    CtfSubmissionModel,
)


def _spec():
    return {
        'name': 'Spring CTF',
        'flags': [{
            'id': 'web-root', 'server': 'web-server', 'slot': 1, 'location_type': 'file',
            'path': '/root/flag.txt', 'operating_system': 'linux', 'points': 100,
        }],
    }


def _event(**overrides):
    event = {
        'id': 'abcdefghij',
        'unit_id': 'klmnopqrst',
        'instructor_id': ['teacher@example.com'],
        'spec': _spec(),
        'creation_timestamp': 1700000000.0,
        'state': CtfStates.DRAFT.value,
        'state_timestamp': '2026-10-16T00:00:00+00:00',
    }
    event.update(overrides)
    return event


def _board(**overrides):
    board = {'id': 'abcdefghij-uvwxyzabcd', 'workout_id': 'uvwxyzabcd', 'ctf_id': 'abcdefghij', 'team_name': 'Red'}
    board.update(overrides)
    return board


def test_event_defaults():
    event = CtfEventModel(**_event())

    assert event.seed_version == 1
    assert event.starts_at is None and event.ends_at is None and event.paused_at is None
    assert event.accumulated_pause_seconds == 0.0
    assert event.scoreboard_frozen_at is None
    assert event.public_scoreboard_enabled is False
    assert event.board_ids == []
    assert event.boards_pending == 0
    assert event.spec.flags[0].id == 'web-root'


def test_event_validates_embedded_spec():
    bad_spec = _spec()
    bad_spec['flags'][0]['location_type'] = 'clipboard'
    with pytest.raises(ValidationError):
        CtfEventModel(**_event(spec=bad_spec))


@pytest.mark.parametrize('field', ['id', 'unit_id', 'instructor_id', 'spec', 'creation_timestamp', 'state', 'state_timestamp'])
def test_event_required_fields(field):
    data = _event()
    del data[field]
    with pytest.raises(ValidationError):
        CtfEventModel(**data)


def test_event_round_trips_through_model_dump():
    # Firestore stores model_dump() output; reloading it must give the same model.
    event = CtfEventModel(**_event(board_ids=['uvwxyzabcd'], boards_pending=1))
    assert CtfEventModel(**event.model_dump()) == event


def test_flag_state_defaults():
    flag = CtfFlagStateModel(flag_id='web-root', digest='a' * 64)

    assert flag.plant_status == 'pending'
    assert flag.solved is False and flag.hint_taken is False
    assert flag.attempts == 0
    assert flag.planted_at is None and flag.plant_error is None


def test_flag_state_rejects_unknown_plant_status():
    with pytest.raises(ValidationError):
        CtfFlagStateModel(flag_id='web-root', digest='a' * 64, plant_status='done')


def test_board_defaults_and_embedded_flags():
    board = CtfBoardModel(**_board(flags=[{'flag_id': 'web-root', 'digest': 'b' * 64, 'plant_status': 'planted'}]))

    assert board.active is True
    assert board.score == 0 and board.solve_count == 0 and board.decoy_count == 0
    assert board.last_solve_at is None
    assert board.arm_status == 'pending'
    assert board.flags[0].plant_status == 'planted'


def test_board_allows_negative_score():
    # Decoys and hint costs can push a team below zero.
    assert CtfBoardModel(**_board(score=-50)).score == -50


def test_board_rejects_unknown_arm_status():
    with pytest.raises(ValidationError):
        CtfBoardModel(**_board(arm_status='ready'))


def test_digest_requires_all_fields():
    digest = CtfDigestModel(digest='c' * 64, ctf_id='abcdefghij', workout_id='uvwxyzabcd', flag_id='web-root')
    assert digest.flag_id == 'web-root'
    with pytest.raises(ValidationError):
        CtfDigestModel(digest='c' * 64, ctf_id='abcdefghij', workout_id='uvwxyzabcd')


def test_rate_limit_defaults_count():
    limit = CtfRateLimitModel(id='abcdefghij-uvwxyzabcd-unparsed', window_start=1700000000.0)
    assert limit.count == 0


def _submission(**overrides):
    submission = {
        'id': 'f5b0c3a2-0000-4000-8000-000000000000',
        'ctf_id': 'abcdefghij',
        'workout_id': 'uvwxyzabcd',
        'submitted_digest': 'd' * 64,
        'verdict': 'incorrect',
        'submitted_at': 1700000000.0,
    }
    submission.update(overrides)
    return submission


@pytest.mark.parametrize('verdict', ['correct', 'incorrect', 'duplicate', 'decoy', 'cross_submission', 'rate_limited', 'closed'])
def test_submission_accepts_every_verdict(verdict):
    assert CtfSubmissionModel(**_submission(verdict=verdict)).verdict == verdict


def test_submission_defaults_and_rejects_unknown_verdict():
    submission = CtfSubmissionModel(**_submission())
    assert submission.flag_id is None and submission.matched_workout_id is None
    assert submission.points_awarded == 0
    assert submission.origin_ip is None
    with pytest.raises(ValidationError):
        CtfSubmissionModel(**_submission(verdict='wrong'))


def test_submission_has_no_plaintext_field():
    # The submitted value is never stored; only its digest.
    assert 'submission' not in CtfSubmissionModel.model_fields
    assert 'value' not in CtfSubmissionModel.model_fields


def _log(**overrides):
    log = {
        'id': 'f5b0c3a2-0000-4000-8000-000000000001',
        'ctf_id': 'abcdefghij',
        'action': 'CTF_START',
        'actor': 'teacher@example.com',
        'result': 'OK',
        'created_at': 1700000000.0,
    }
    log.update(overrides)
    return log


def test_log_keeps_scalar_detail_types():
    log = CtfLogModel(**_log(detail={'flag_id': 'web-root', 'delta': -25, 'ok': True}))
    assert log.detail == {'flag_id': 'web-root', 'delta': -25, 'ok': True}
    assert isinstance(log.detail['ok'], bool)
    assert log.target is None


def test_log_rejects_nested_detail():
    with pytest.raises(ValidationError):
        CtfLogModel(**_log(detail={'nested': {'a': 1}}))


@pytest.mark.parametrize('field, value', [('action', 'CTF_EXPLODE'), ('result', 'MAYBE')])
def test_log_rejects_unknown_action_or_result(field, value):
    with pytest.raises(ValidationError):
        CtfLogModel(**_log(**{field: value}))

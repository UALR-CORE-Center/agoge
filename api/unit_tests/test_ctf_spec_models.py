import pytest
from pydantic import ValidationError

from common.models.agoge import CtfFlagSpecModel, CtfScoringSpecModel, CtfSpecModel


def _flag(**overrides):
    flag = {
        'id': 'web-root',
        'server': 'web-server',
        'slot': 1,
        'location_type': 'file',
        'path': '/root/flag.txt',
        'operating_system': 'linux',
        'points': 100,
    }
    flag.update(overrides)
    return flag


def test_minimal_spec_applies_defaults():
    spec = CtfSpecModel(name='Spring CTF', flags=[_flag()])

    flag = spec.flags[0]
    assert flag.access_level == 'user'
    assert flag.decoy is False
    assert flag.hint_cost == 0
    assert flag.file_mode is None
    assert spec.scoring == CtfScoringSpecModel()
    assert spec.scoring.flag_prefix == 'agoge'
    assert spec.scoring.submission_rate_limit == 10
    assert spec.scoring.reveal_decoy_penalty is False


def test_full_flag_round_trips():
    data = _flag(category='Web', hint='look in /root', hint_cost=10, unlocks_after=['user-flag'],
                 file_mode='0600', file_owner='root:root', access_level='root')

    flag = CtfFlagSpecModel(**data)

    assert flag.file_owner == 'root:root'
    assert CtfFlagSpecModel(**flag.model_dump()) == flag


# A negative decoy value is legal at the model level; the sign rule belongs to the spec validator.
def test_decoy_may_carry_negative_points():
    assert CtfFlagSpecModel(**_flag(decoy=True, points=-50)).points == -50


@pytest.mark.parametrize('bad_id', ['a', 'Web-root', '-web', 'web_root', 'web root', 'x' * 33, ''])
def test_rejects_bad_flag_id(bad_id):
    with pytest.raises(ValidationError):
        CtfFlagSpecModel(**_flag(id=bad_id))


@pytest.mark.parametrize('bad_type', ['memory', 'FILE', 'database', ''])
def test_rejects_unknown_location_type(bad_type):
    with pytest.raises(ValidationError):
        CtfFlagSpecModel(**_flag(location_type=bad_type))


@pytest.mark.parametrize('bad_mode', ['600', '0800', '06000', '0o600', 'rw-------', '1755'])
def test_rejects_malformed_file_mode(bad_mode):
    with pytest.raises(ValidationError):
        CtfFlagSpecModel(**_flag(file_mode=bad_mode))


@pytest.mark.parametrize('field, value', [
    ('slot', 0), ('slot', 10), ('operating_system', 'macos'), ('access_level', 'system'),
    ('hint_cost', -1), ('file_owner', 'root'), ('category', 'x' * 33), ('hint', 'x' * 1001),
])
def test_rejects_other_out_of_range_flag_fields(field, value):
    with pytest.raises(ValidationError):
        CtfFlagSpecModel(**_flag(**{field: value}))


@pytest.mark.parametrize('field, value', [
    ('flag_prefix', 'Agoge'), ('flag_prefix', 'a'), ('flag_prefix', '1ctf'),
    ('submission_rate_limit', 0), ('submission_rate_limit', 101),
])
def test_rejects_bad_scoring(field, value):
    with pytest.raises(ValidationError):
        CtfScoringSpecModel(**{field: value})


def test_spec_requires_between_one_and_two_hundred_flags():
    with pytest.raises(ValidationError):
        CtfSpecModel(name='Empty', flags=[])
    with pytest.raises(ValidationError):
        CtfSpecModel(name='Huge', flags=[_flag(id=f'flag-{i}') for i in range(201)])
    assert len(CtfSpecModel(name='Max', flags=[_flag(id=f'flag-{i}') for i in range(200)]).flags) == 200

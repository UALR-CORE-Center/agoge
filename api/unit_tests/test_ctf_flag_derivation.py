import hashlib
import hmac
import itertools
import re
from unittest.mock import patch

import pytest

from common.utilities import ctf_flags
from common.utilities.ctf_flags import (derive_flag_value, flag_digest, flags_match, normalize_flag,
                                        parse_flag_id)

SEED = 'a' * 64
FLAG_IDS = ['web-login', 'priv-esc', 'db-dump', 'ssh-key']


def test_derived_value_has_contract_format():
    value = derive_flag_value(SEED, 'abcdefghij', 'web-login', 1)
    assert re.fullmatch(r'agoge\{web-login_[0-9a-f]{20}\}', value)


def test_derived_digest_is_first_20_hex_of_hmac_sha256():
    # Pins the exact derivation input so a planter built from another copy of the
    # contract cannot silently drift from the submission checker.
    expected = hmac.new(SEED.encode(), b'1:abcdefghij:web-login', hashlib.sha256).hexdigest()[:20]
    assert derive_flag_value(SEED, 'abcdefghij', 'web-login', 1) == f'agoge{{web-login_{expected}}}'


def test_custom_prefix():
    assert derive_flag_value(SEED, 'abcdefghij', 'web-login', 1, prefix='ncl').startswith('ncl{web-login_')


def test_derivation_is_deterministic():
    first = derive_flag_value(SEED, 'abcdefghij', 'priv-esc', 1)
    assert all(derive_flag_value(SEED, 'abcdefghij', 'priv-esc', 1) == first for _ in range(5))


def test_distinct_value_per_workout_sc3():
    # SC-3: 0 collisions across 1000 generated workout pairs, for every flag id.
    workout_ids = [''.join(p) for p in itertools.islice(itertools.product('abcdefghij', repeat=10), 1001)]
    pairs = list(zip(workout_ids, workout_ids[1:]))
    assert len(pairs) == 1000
    for flag_id in FLAG_IDS:
        for wid_a, wid_b in pairs:
            assert derive_flag_value(SEED, wid_a, flag_id, 1) != derive_flag_value(SEED, wid_b, flag_id, 1)


def test_distinct_value_per_flag_and_seed():
    values = {derive_flag_value(SEED, 'abcdefghij', fid, 1) for fid in FLAG_IDS}
    assert len(values) == len(FLAG_IDS)
    assert derive_flag_value(SEED, 'abcdefghij', 'web-login', 1) != \
        derive_flag_value('b' * 64, 'abcdefghij', 'web-login', 1)


def test_seed_version_changes_value():
    assert derive_flag_value(SEED, 'abcdefghij', 'web-login', 1) != \
        derive_flag_value(SEED, 'abcdefghij', 'web-login', 2)


@pytest.mark.parametrize('raw, expected', [
    ('  AGOGE{Web-Login_ABC}\n', 'agoge{web-login_abc}'),
    ('\tagoge{x_1}  ', 'agoge{x_1}'),
    ('agoge{ inner space }', 'agoge{ inner space }'),
    ('agoge{a.b,c}', 'agoge{a.b,c}'),
])
def test_normalize_only_strips_and_lowercases(raw, expected):
    assert normalize_flag(raw) == expected


def test_flag_digest_is_sha256_of_normalized_value():
    value = derive_flag_value(SEED, 'abcdefghij', 'web-login', 1)
    assert flag_digest(value) == hashlib.sha256(value.encode()).hexdigest()
    assert flag_digest(f'  {value.upper()} ') == flag_digest(value)


def test_flags_match_accepts_case_and_whitespace_variants():
    value = derive_flag_value(SEED, 'abcdefghij', 'web-login', 1)
    expected = flag_digest(value)
    assert flags_match(value, expected)
    assert flags_match(f'\n {value.upper()}\t', expected)


def test_flags_match_rejects_other_workout_and_near_misses():
    value = derive_flag_value(SEED, 'abcdefghij', 'web-login', 1)
    expected = flag_digest(value)
    assert not flags_match(derive_flag_value(SEED, 'bcdefghijk', 'web-login', 1), expected)
    assert not flags_match(value[:-1], expected)
    assert not flags_match(value.replace('-', ''), expected)
    assert not flags_match('', expected)


def test_flags_match_uses_compare_digest():
    expected = flag_digest('agoge{x_1}')
    with patch.object(ctf_flags.hmac, 'compare_digest', wraps=hmac.compare_digest) as compare:
        assert flags_match('agoge{x_1}', expected)
    compare.assert_called_once_with(expected, expected)


def test_parse_flag_id_hits():
    value = derive_flag_value(SEED, 'abcdefghij', 'web-login', 1)
    assert parse_flag_id(value, 'agoge') == 'web-login'
    assert parse_flag_id(f'  {value.upper()} ', 'agoge') == 'web-login'
    assert parse_flag_id(derive_flag_value(SEED, 'abcdefghij', 'db-dump', 1, prefix='ncl'), 'ncl') == 'db-dump'


@pytest.mark.parametrize('submitted', [
    'agoge{web-login_' + 'a' * 19 + '}',           # digest too short
    'agoge{web-login_' + 'a' * 21 + '}',           # digest too long
    'agoge{web-login_' + 'g' * 20 + '}',           # non-hex digest
    'agoge{web_login}',                            # no digest
    'agoge{_' + 'a' * 20 + '}',                    # empty flag id
    'agoge{web.login_' + 'a' * 20 + '}',           # disallowed flag id character
    'ncl{web-login_' + 'a' * 20 + '}',             # wrong prefix
    'xagoge{web-login_' + 'a' * 20 + '}',          # anchored at the start
    'agoge{web-login_' + 'a' * 20 + '}x',          # anchored at the end
    'agoge web-login_' + 'a' * 20,                 # no braces
    '',
])
def test_parse_flag_id_misses(submitted):
    assert parse_flag_id(submitted, 'agoge') is None

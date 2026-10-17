import copy

import pytest

from common.exceptions import AgogeValidationError
from utilities.infrastructure_as_code.object_validators.ctf import CtfValidator


def _flag(**overrides) -> dict:
    flag = {
        'id': 'web-root',
        'server': 'web',
        'slot': 1,
        'location_type': 'file',
        'path': '/root/flag.txt',
        'operating_system': 'linux',
        'points': 100,
    }
    flag.update(overrides)
    return flag


def _spec(flags: list) -> dict:
    return {
        'servers': [{'name': 'web'}, {'name': 'dc'}],
        'ctf': {'name': 'Spring CTF', 'flags': flags},
    }


VALID_FLAGS = [
    _flag(),
    _flag(id='web-env', slot=2, location_type='env', path='AGOGE_FLAG', unlocks_after=['web-root']),
    _flag(id='dc-file', server='dc', slot=1, operating_system='windows', path='C:\\Users\\Public\\flag 1.txt'),
    _flag(id='dc-reg', server='dc', slot=2, operating_system='windows', location_type='registry',
          path='HKLM\\SOFTWARE\\Agoge Lab:Flag', unlocks_after=['dc-file', 'web-env']),
    _flag(id='dc-ads', server='dc', slot=3, operating_system='windows', location_type='ads',
          path='C:\\Windows\\Temp\\notes.txt:hidden'),
    _flag(id='dc-env', server='dc', slot=4, operating_system='windows', location_type='env', path='_SECRET_1'),
    _flag(id='decoy-neg', server='dc', slot=5, operating_system='windows', path='C:\\decoy.txt',
          points=-50, decoy=True),
    _flag(id='decoy-zero', server='dc', slot=6, operating_system='windows', path='C:\\decoy0.txt',
          points=0, decoy=True),
]


def _rejects(flags: list, flag_id: str, fragment: str) -> None:
    with pytest.raises(AgogeValidationError) as exc:
        CtfValidator(_spec(flags)).load()
    message = str(exc.value)
    assert flag_id in message
    assert fragment in message


def test_valid_spec_covering_every_location_row_passes_unchanged():
    spec = _spec(copy.deepcopy(VALID_FLAGS))
    before = copy.deepcopy(spec)
    assert CtfValidator(spec).load() == before


def test_unknown_server_rejected():
    _rejects([_flag(), _flag(id='ghost-1', server='ghost', slot=2)], 'ghost-1', "server 'ghost'")


def test_spec_without_servers_rejects_every_flag():
    spec = {'ctf': {'name': 'x', 'flags': [_flag()]}}
    with pytest.raises(AgogeValidationError, match='web-root'):
        CtfValidator(spec).load()


def test_duplicate_flag_id_rejected():
    _rejects([_flag(), _flag(slot=2)], 'web-root', 'unique')


def test_duplicate_server_slot_rejected():
    _rejects([_flag(), _flag(id='web-two', path='/tmp/x')], 'web-two', 'slot 1')


def test_same_slot_on_different_servers_allowed():
    CtfValidator(_spec([_flag(), _flag(id='dc-one', server='dc')])).load()


def test_mixed_operating_system_on_one_server_rejected():
    _rejects(
        [_flag(), _flag(id='web-win', slot=2, operating_system='windows', path='C:\\flag.txt')],
        'web-win', 'operating_system',
    )


@pytest.mark.parametrize('location_type, path', [
    ('registry', 'HKLM\\SOFTWARE\\Agoge:Flag'),
    ('ads', 'C:\\notes.txt:hidden'),
])
def test_windows_only_location_on_linux_rejected(location_type, path):
    _rejects([_flag(id='lin-win', location_type=location_type, path=path)], 'lin-win', "requires operating_system 'windows'")


@pytest.mark.parametrize('location_type, operating_system, path', [
    ('file', 'linux', 'root/flag.txt'),                      # not absolute
    ('file', 'linux', '/root/flag;rm -rf /'),                # shell metacharacters
    ('file', 'linux', '/root/$(id)'),
    ('file', 'linux', '/root/flag.txt\n'),                    # '$' alone would accept a trailing newline
    ('file', 'windows', '/root/flag.txt'),                   # linux path on windows
    ('file', 'windows', 'C:\\flag$.txt'),
    ('registry', 'windows', 'HKCU\\Software:Flag'),          # only HKLM
    ('registry', 'windows', 'HKLM\\Software'),               # missing ':value name'
    ('registry', 'windows', 'HKLM\\Software:Fl-ag'),
    ('env', 'linux', 'agoge_flag'),                          # lowercase
    ('env', 'windows', '1FLAG'),
    ('env', 'linux', 'A' * 65),                              # over 64 characters
    ('ads', 'windows', 'C:\\notes.txt'),                     # missing ':stream'
    ('ads', 'windows', 'C:\\notes.txt:str eam'),
])
def test_path_not_matching_location_format_rejected(location_type, operating_system, path):
    _rejects(
        [_flag(id='bad-path', location_type=location_type, operating_system=operating_system, path=path)],
        'bad-path', 'does not match',
    )


def test_env_name_at_64_characters_allowed():
    CtfValidator(_spec([_flag(location_type='env', path='A' * 64)])).load()


@pytest.mark.parametrize('points', [0, -10])
def test_non_decoy_points_must_be_positive(points):
    _rejects([_flag(id='no-points', points=points)], 'no-points', 'points')


def test_decoy_may_have_negative_points():
    CtfValidator(_spec([_flag(id='trap', points=-25, decoy=True)])).load()


def test_unlocks_after_unknown_id_rejected():
    _rejects([_flag(unlocks_after=['missing-flag'])], 'web-root', "'missing-flag'")


def test_unlocks_after_self_cycle_rejected():
    _rejects([_flag(unlocks_after=['web-root'])], 'web-root', 'cycle')


def test_unlocks_after_longer_cycle_rejected():
    flags = [
        _flag(id='aa', slot=1, path='/a', unlocks_after=['cc']),
        _flag(id='bb', slot=2, path='/b', unlocks_after=['aa']),
        _flag(id='cc', slot=3, path='/c', unlocks_after=['bb']),
        _flag(id='dd', slot=4, path='/d', unlocks_after=['aa']),
    ]
    with pytest.raises(AgogeValidationError, match='cycle') as exc:
        CtfValidator(_spec(flags)).load()
    assert any(flag_id in str(exc.value) for flag_id in ('aa', 'bb', 'cc'))


def test_unlocks_after_diamond_is_not_a_cycle():
    # Shared prerequisites (a DAG with two paths to one node) must not be mistaken for a cycle
    flags = [
        _flag(id='aa', slot=1, path='/a'),
        _flag(id='bb', slot=2, path='/b', unlocks_after=['aa']),
        _flag(id='cc', slot=3, path='/c', unlocks_after=['aa']),
        _flag(id='dd', slot=4, path='/d', unlocks_after=['bb', 'cc']),
    ]
    CtfValidator(_spec(flags)).load()


def _windows_file(**overrides) -> dict:
    return _flag(**{'id': 'dc-file', 'server': 'dc', 'operating_system': 'windows',
                    'path': 'C:\\Secrets\\flag.txt', **overrides})


@pytest.mark.parametrize('options', [
    {'windows_access': 'administrators'},
    {'windows_access': 'everyone', 'hidden': True},
    {'windows_access': 'user', 'windows_user': 'student'},
    {'hidden': True},
])
def test_windows_file_access_and_hidden_allowed(options):
    CtfValidator(_spec([_windows_file(**options)])).load()


def test_windows_access_allowed_on_ads_host_file():
    flag = _windows_file(location_type='ads', path='C:\\Windows\\Temp\\notes.txt:hidden',
                         windows_access='administrators', hidden=True)
    CtfValidator(_spec([flag])).load()


@pytest.mark.parametrize('flag', [
    _flag(windows_access='administrators'),
    _flag(hidden=True),
    _flag(id='dc-reg', server='dc', operating_system='windows', location_type='registry',
          path='HKLM\\SOFTWARE\\Agoge Lab:Flag', hidden=True),
])
def test_windows_file_options_rejected_elsewhere(flag):
    _rejects([flag], flag['id'], 'apply only to Windows file and ads flags')


def test_windows_user_access_requires_a_user():
    _rejects([_windows_file(windows_access='user')], 'dc-file', 'requires windows_user')


def test_windows_user_without_user_access_rejected():
    _rejects([_windows_file(windows_access='everyone', windows_user='student')], 'dc-file', 'only with windows_access')

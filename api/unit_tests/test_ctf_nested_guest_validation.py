import copy

import pytest

from common.exceptions import AgogeValidationError
from utilities.infrastructure_as_code.object_validators.ctf import CtfValidator


def _guest(**overrides) -> dict:
    guest = {'name': 'win-dc', 'server': 'hv', 'domain': 'win2019-dc', 'operating_system': 'windows',
             'driver': 'qemu-agent'}
    guest.update(overrides)
    return guest


def _flag(**overrides) -> dict:
    flag = {'id': 'dc-admin', 'server': 'hv', 'guest': 'win-dc', 'slot': 1, 'location_type': 'registry',
            'path': 'HKLM\\SOFTWARE\\Corp:Secret', 'operating_system': 'windows', 'points': 300}
    flag.update(overrides)
    return flag


def _hv_server(**overrides) -> dict:
    server = {'name': 'hv', 'details': {'os': 'linux'},
              'nics': [{'network': 'lan', 'ip_aliases': ['10.1.1.0/24']}]}
    server.update(overrides)
    return server


def _spec(flags: list, guests: list, servers: list = None) -> dict:
    return {
        'servers': servers if servers is not None else [_hv_server(), {'name': 'web', 'details': {'os': 'linux'}}],
        'ctf': {'name': 'Nested CTF', 'flags': flags, 'nested_guests': guests},
    }


def _rejects(spec: dict, name: str, fragment: str) -> None:
    with pytest.raises(AgogeValidationError) as exc:
        CtfValidator(spec).load()
    message = str(exc.value)
    assert name in message
    assert fragment in message


VALID_GUESTS = [
    _guest(),
    _guest(name='web-1', domain='ubuntu-web', operating_system='linux', driver='offline'),
    _guest(name='files', domain='win-files', driver='offline'),
]

VALID_FLAGS = [
    _flag(),
    # Same slot as dc-admin is fine: slots are per (server, guest)
    _flag(id='hv-root', guest=None, location_type='file', path='/root/flag.txt', operating_system='linux'),
    _flag(id='web-env', guest='web-1', location_type='env', path='AGOGE_FLAG', operating_system='linux'),
    _flag(id='files-reg', guest='files', path='HKLM\\SYSTEM\\Agoge:Flag'),
    _flag(id='files-file', guest='files', slot=2, location_type='file', path='C:\\Users\\Public\\flag.txt'),
    _flag(id='files-env', guest='files', slot=3, location_type='env', path='AGOGE_FLAG'),
    _flag(id='dc-file', slot=2, location_type='file', path='C:\\Secrets\\flag.txt',
          windows_access='administrators', hidden=True),
]


def test_valid_nested_spec_passes_unchanged():
    spec = _spec(copy.deepcopy(VALID_FLAGS), copy.deepcopy(VALID_GUESTS))
    before = copy.deepcopy(spec)
    assert CtfValidator(spec).load() == before


def test_existing_spec_without_nested_guests_still_validates():
    spec = {
        'servers': [{'name': 'web'}],
        'ctf': {'name': 'Plain', 'flags': [_flag(server='web', guest=None, location_type='file',
                                                 path='/root/flag.txt', operating_system='linux')]},
    }
    CtfValidator(spec).load()


# Row 1: the parent is a Linux spec server with an ip_aliases NIC

def test_guest_on_unknown_server_rejected():
    _rejects(_spec([], [_guest(server='ghost')]), 'win-dc', "server 'ghost' does not exist")


@pytest.mark.parametrize('details', [{'os': 'windows'}, {}, None])
def test_guest_on_non_linux_server_rejected(details):
    servers = [_hv_server(details=details)]
    _rejects(_spec([], [_guest()], servers), 'win-dc', 'must be a Linux server')


@pytest.mark.parametrize('nics', [None, [], [{'network': 'lan'}], [{'network': 'lan', 'ip_aliases': []}]])
def test_guest_on_server_without_ip_aliases_rejected(nics):
    servers = [_hv_server(nics=nics)]
    _rejects(_spec([], [_guest()], servers), 'win-dc', 'ip_aliases')


def test_ip_aliases_on_any_nic_is_enough():
    servers = [_hv_server(nics=[{'network': 'mgmt'}, {'network': 'lan', 'ip_aliases': ['10.1.1.0/24']}])]
    CtfValidator(_spec([_flag()], [_guest()], servers)).load()


# V23: a parent built from a nested lab host image has nested virtualization without ip_aliases
@pytest.mark.parametrize('image', ['image-hv-host', 'hv-host', {'value': 'image-hv-host'}])
def test_nested_image_parent_without_ip_aliases_passes(image):
    servers = [_hv_server(image=image, nics=[{'network': 'lan'}])]
    loaded = []

    def loader(image_id):
        loaded.append(image_id)
        return {'id': 'hv-host', 'nested': {'guests': [], 'exposures': []}}

    CtfValidator(_spec([_flag()], [_guest()], servers), image_loader=loader).load()
    assert loaded == ['hv-host']


@pytest.mark.parametrize('image_doc', [None, {'id': 'plain'}, {'id': 'plain', 'nested': None}])
def test_non_nested_image_parent_without_ip_aliases_rejected(image_doc):
    servers = [_hv_server(image='image-plain', nics=[{'network': 'lan'}])]
    with pytest.raises(AgogeValidationError) as exc:
        CtfValidator(_spec([], [_guest()], servers), image_loader=lambda _: image_doc).load()
    assert 'win-dc' in str(exc.value)
    assert 'nested lab host image' in str(exc.value)


def test_public_image_parent_is_not_looked_up():
    servers = [_hv_server(image='projects/debian-cloud/global/images/family/debian-12', nics=[])]
    loader_calls = []
    with pytest.raises(AgogeValidationError):
        CtfValidator(_spec([], [_guest()], servers), image_loader=loader_calls.append).load()
    assert loader_calls == []


# Row 2: (server, name) unique; at most 8 guests per server

def test_duplicate_guest_name_on_one_server_rejected():
    _rejects(_spec([], [_guest(), _guest(domain='other')]), 'win-dc', 'unique')


def test_same_guest_name_on_two_servers_allowed():
    servers = [_hv_server(), _hv_server(name='hv2')]
    CtfValidator(_spec([_flag(), _flag(id='dc2', server='hv2')], [_guest(), _guest(server='hv2')], servers)).load()


def test_ninth_guest_on_a_server_rejected():
    guests = [_guest(name=f'guest-{index}', domain=f'dom{index}') for index in range(9)]
    _rejects(_spec([], guests), 'guest-8', 'more than 8')


def test_eight_guests_on_a_server_allowed():
    guests = [_guest(name=f'guest-{index}', domain=f'dom{index}') for index in range(8)]
    CtfValidator(_spec([_flag(guest='guest-0')], guests)).load()


# Row 3: flag.guest names a guest declared on flag.server

def test_flag_naming_undeclared_guest_rejected():
    _rejects(_spec([_flag(guest='nope')], [_guest()]), 'dc-admin', "guest 'nope' is not declared")


def test_flag_naming_guest_of_another_server_rejected():
    servers = [_hv_server(), _hv_server(name='hv2')]
    spec = _spec([_flag(server='hv2')], [_guest()], servers)
    _rejects(spec, 'dc-admin', "on server 'hv2'")


# Row 4: flag.operating_system equals the guest's

def test_flag_os_differs_from_guest_os_rejected():
    flag = _flag(guest='web-1', location_type='file', path='C:\\flag.txt')
    _rejects(_spec([flag], VALID_GUESTS), 'dc-admin', "does not match 'linux' on guest 'web-1'")


# Row 5: same-OS and (server, slot) rules are per (server, guest)

def test_duplicate_slot_on_one_guest_rejected():
    flags = [_flag(), _flag(id='dc-two', path='HKLM\\SOFTWARE\\Corp:Other')]
    _rejects(_spec(flags, [_guest()]), 'dc-two', "slot 1 on guest 'win-dc' on server 'hv'")


def test_duplicate_slot_on_parent_still_rejected():
    flags = [_flag(id='hv-a', guest=None, location_type='file', path='/a', operating_system='linux'),
             _flag(id='hv-b', guest=None, location_type='file', path='/b', operating_system='linux')]
    _rejects(_spec(flags, [_guest()]), 'hv-b', "slot 1 on server 'hv'")


def test_parent_and_guest_may_differ_in_os():
    flags = [_flag(), _flag(id='hv-root', guest=None, location_type='file', path='/root/f', operating_system='linux')]
    CtfValidator(_spec(flags, [_guest()])).load()


def test_os_conflict_on_parent_with_guests_rejected():
    flags = [_flag(id='hv-a', guest=None, location_type='file', path='/a', operating_system='linux'),
             _flag(id='hv-b', guest=None, slot=2, location_type='file', path='C:\\b.txt',
                   operating_system='windows')]
    _rejects(_spec(flags, [_guest()]), 'hv-b', "for server 'hv'")


# Row 6: offline Windows guests take only file/registry/env, no windows_access/hidden, HKLM SOFTWARE/SYSTEM

def _offline(**overrides) -> dict:
    return _flag(**{'guest': 'files', **overrides})


@pytest.mark.parametrize('flag, fragment', [
    (_offline(location_type='ads', path='C:\\Windows\\Temp\\notes.txt:hidden'), "location_type 'ads'"),
    (_offline(location_type='file', path='C:\\flag.txt', windows_access='everyone'), 'windows_access and hidden'),
    (_offline(location_type='file', path='C:\\flag.txt', hidden=True), 'windows_access and hidden'),
    (_offline(path='HKLM\\HARDWARE\\Agoge:Flag'), 'must start with'),
    # The prefix includes the separator, so a sibling key that merely begins with SOFTWARE is rejected
    (_offline(path='HKLM\\SOFTWAREX\\Agoge:Flag'), 'must start with'),
])
def test_offline_windows_restrictions(flag, fragment):
    _rejects(_spec([flag], VALID_GUESTS), 'dc-admin', fragment)


def test_offline_restrictions_do_not_apply_to_qemu_agent_guest():
    flag = _flag(location_type='ads', path='C:\\Windows\\Temp\\notes.txt:hidden', hidden=True)
    CtfValidator(_spec([flag], [_guest()])).load()


def test_offline_linux_guest_has_no_windows_restrictions():
    flag = _flag(guest='web-1', location_type='file', path='/root/flag.txt', operating_system='linux')
    CtfValidator(_spec([flag], VALID_GUESTS)).load()

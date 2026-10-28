from unittest.mock import MagicMock, patch

import pytest

from common.exceptions import GuacamoleServerNotFound
from core.guacamole_api import Guacamole


def _guacamole(build: dict) -> Guacamole:
    env = MagicMock(parent_dns_suffix='.example.com', main_app_url='app.example.com/lab')
    with patch('core.guacamole_api.CloudEnv', return_value=env), \
            patch('core.guacamole_api.DocumentDatabaseFactory'):
        return Guacamole(build_id='abcdefghij', env_dict={}, build=build)


def _build(human_interaction: list) -> dict:
    return {
        'proxy_connections': [
            {'server': 'nestedhost', 'internal_ip_address': '10.1.1.2', 'username': 'u', 'password': 'p'},
        ],
        'servers': [{'name': 'nestedhost', 'hostname': None, 'human_interaction': human_interaction}],
    }


PARENT_SSH = {'display': False, 'protocol': 'ssh', 'username': 'instructor'}
KALI_SSH = {'display': True, 'protocol': 'ssh', 'username': 'kali', 'alias_index': 0, 'nested_guest': 'kali'}
KALI_RDP = {'display': True, 'protocol': 'rdp', 'username': 'kali', 'alias_index': 0, 'nested_guest': 'kali',
            'security_mode': 'any'}


def _jumpbox_build() -> dict:
    """A nested host whose jumpbox guest has SSH and RDP, plus a plain server sorting before it."""
    return {
        # Stored as DisplayProxy writes them: sorted by server, registration order within a server
        'proxy_connections': [
            {'server': 'attacker', 'internal_ip_address': '10.1.1.5', 'username': 'agoge0', 'password': 'p0'},
            {'server': 'nested-host', 'internal_ip_address': '10.1.1.2', 'username': 'agoge1', 'password': 'p1'},
            {'server': 'nested-host', 'internal_ip_address': '10.1.1.2', 'username': 'agoge2', 'password': 'p2'},
        ],
        'servers': [
            {'name': 'nested-host', 'hostname': 'nested-host.example.com',
             'human_interaction': [PARENT_SSH, KALI_SSH, KALI_RDP]},
            {'name': 'attacker', 'hostname': None,
             'human_interaction': [{'display': True, 'protocol': 'vnc', 'username': 'student'}]},
        ],
    }


def test_protocol_comes_from_the_displayed_connection_not_the_hidden_parent_login():
    connections = _guacamole(_build([
        {'display': False, 'protocol': 'ssh', 'username': 'instructor'},
        {'display': True, 'protocol': 'rdp', 'username': 'admin', 'alias_index': 0, 'nested_guest': 'dc'},
    ])).get_all_connections()

    assert len(connections) == 1
    assert connections[0]['server'] == 'nestedhost'
    assert connections[0]['protocol'] == 'rdp'
    assert connections[0]['idx'] == 0
    assert connections[0]['url'] == 'https://app.example.com/lab/student/workout/abcdefghij/guacamole/0'


def test_protocol_falls_back_to_the_first_connection_when_none_is_displayed():
    connections = _guacamole(_build([{'protocol': 'vnc'}])).get_all_connections()

    assert connections[0]['protocol'] == 'vnc'


def test_every_displayed_connection_of_one_server_keeps_its_own_index_and_protocol():
    connections = _guacamole(_jumpbox_build()).get_all_connections()

    assert [(c['idx'], c['server'], c['username'], c['protocol']) for c in connections] == [
        (0, 'attacker', 'agoge0', 'vnc'),
        (1, 'nested-host', 'agoge1', 'ssh'),
        (2, 'nested-host', 'agoge2', 'rdp'),
    ]
    assert [c['url'].rsplit('/', 1)[1] for c in connections] == ['0', '1', '2']
    assert connections[1]['hostname'] == connections[2]['hostname'] == 'nested-host.example.com'


def test_registration_order_within_a_server_survives_an_unsorted_record():
    build = _jumpbox_build()
    build['proxy_connections'].reverse()

    connections = _guacamole(build).get_all_connections()

    # Stable sort by server: agoge2 was registered first for nested-host in this record, so it is the
    # server's first connection and takes the first displayed interaction
    assert [(c['idx'], c['username'], c['protocol']) for c in connections] == [
        (0, 'agoge0', 'vnc'), (1, 'agoge2', 'ssh'), (2, 'agoge1', 'rdp'),
    ]


@pytest.mark.parametrize('server_idx, username, protocol', [('1', 'agoge1', 'ssh'), ('2', 'agoge2', 'rdp')])
def test_each_connection_of_a_jumpbox_opens_its_own_guacamole_user(server_idx, username, protocol):
    guac = _guacamole(_jumpbox_build())
    session = MagicMock(token='tok')
    with patch.object(Guacamole, '_Guacamole___get_session', return_value=session) as get_session:
        result = guac.get_connection_from_server(server_idx)

    get_session.assert_called_once_with()
    assert guac.username == username
    assert result == {
        'token': 'tok', 'protocol': protocol, 'hostname': 'nested-host.example.com',
        'server': 'nested-host', 'url': 'https://abcdefghij-display.example.com/guacamole',
    }


def test_single_connection_server_is_unchanged_by_the_index():
    guac = _guacamole(_build([{'display': True, 'protocol': 'ssh', 'username': 'student'}]))
    with patch.object(Guacamole, '_Guacamole___get_session', return_value=MagicMock(token='tok')):
        result = guac.get_connection_from_server('0')

    assert guac.username == 'u'
    assert result['protocol'] == 'ssh'
    assert result['server'] == 'nestedhost'


def test_an_index_past_the_last_connection_is_not_found():
    with pytest.raises(GuacamoleServerNotFound):
        _guacamole(_jumpbox_build()).get_connection_from_server('3')


def test_jumpbox_alone_maps_index_zero_to_ssh_and_one_to_rdp():
    build = _jumpbox_build()
    build['proxy_connections'] = build['proxy_connections'][1:]
    build['servers'] = build['servers'][:1]

    connections = _guacamole(build).get_all_connections()

    assert [(c['idx'], c['username'], c['protocol']) for c in connections] == [(0, 'agoge1', 'ssh'), (1, 'agoge2', 'rdp')]

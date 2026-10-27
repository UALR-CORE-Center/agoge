from unittest.mock import MagicMock, patch

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


def test_protocol_comes_from_the_displayed_connection_not_the_hidden_parent_login():
    connections = _guacamole(_build([
        {'display': False, 'protocol': 'ssh', 'username': 'instructor'},
        {'display': True, 'protocol': 'rdp', 'username': 'admin', 'alias_index': 0, 'nested_guest': 'dc'},
    ])).get_all_connections()

    assert connections['nestedhost']['protocol'] == 'rdp'
    assert connections['nestedhost']['idx'] == 0


def test_protocol_falls_back_to_the_first_connection_when_none_is_displayed():
    connections = _guacamole(_build([{'protocol': 'vnc'}])).get_all_connections()

    assert connections['nestedhost']['protocol'] == 'vnc'

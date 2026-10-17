from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from common.models.agoge import HumanInteractionModel, NicModel, ServerModel
from cloud_fn_utilities.server_specific.guacamole.display_proxy import DisplayProxy
from cloud_fn_utilities.server_specific.guacamole.guacamole_configuration import GuacamoleConfiguration

GUAC = 'cloud_fn_utilities.server_specific.guacamole.guacamole_configuration'
PROXY = 'cloud_fn_utilities.server_specific.guacamole.display_proxy'
ALIASES = ['10.1.1.20', '10.1.1.21']


@pytest.fixture
def guac():
    with patch(f'{GUAC}.CloudEnv') as cloud_env, patch(f'{GUAC}.Logger'):
        cloud_env.return_value.parent_dns_suffix = '.example.com'
        yield GuacamoleConfiguration('abcdefghij', env_dict={'x': 1})


def _rdp_alias():
    return HumanInteractionModel(display=True, protocol='rdp', username='admin', password='pw',
                                 nested_guest='dc01', alias_index=1)


def _vnc_console():
    return HumanInteractionModel(display=True, protocol='vnc', password='vncpass', nested_guest='ws01', port=5903)


def _ordinary_ssh():
    return HumanInteractionModel(display=True, protocol='ssh', username='kali', password='pw')


def test_alias_target_connects_to_the_alias_ip(guac):
    conn = guac.prepare_guac_connection(_rdp_alias(), server_ip='10.1.1.10', ip_aliases=ALIASES)

    assert (conn['ip'], conn['port']) == ('10.1.1.21', '3389')
    script = guac.get_guac_startup_script([conn])
    assert "'hostname', '10.1.1.21'" in script
    assert "'port', '3389'" in script


def test_alias_with_a_cidr_suffix_uses_the_bare_address(guac):
    connection = _rdp_alias()
    conn = guac.prepare_guac_connection(connection, server_ip='10.1.1.10', ip_aliases=['10.1.1.20/32', '10.1.1.21/32'])

    assert conn['ip'] == '10.1.1.21'


def test_console_target_keeps_the_parent_ip_and_overrides_the_port(guac):
    conn = guac.prepare_guac_connection(_vnc_console(), server_ip='10.1.1.10', ip_aliases=ALIASES)

    assert (conn['ip'], conn['port']) == ('10.1.1.10', '5903')
    script = guac.get_guac_startup_script([conn])
    assert "'hostname', '10.1.1.10'" in script
    assert "'port', '5903'" in script
    assert "'port', '5901'" not in script


@pytest.mark.parametrize('protocol, port', [('ssh', '22'), ('vnc', '5901'), ('rdp', '3389')])
def test_ordinary_target_is_unchanged(guac, protocol, port):
    connection = HumanInteractionModel(display=True, protocol=protocol, username='u', password='pw')
    conn = guac.prepare_guac_connection(connection, server_ip='10.1.1.10')

    assert (conn['ip'], conn['port']) == ('10.1.1.10', port)
    assert f"'port', '{port}'" in guac.get_guac_startup_script([conn])


def test_out_of_range_alias_index_raises(guac):
    with pytest.raises(ValueError, match='alias_index 1 is out of range'):
        guac.prepare_guac_connection(_rdp_alias(), server_ip='10.1.1.10', ip_aliases=['10.1.1.20'])


def test_display_proxy_records_the_resolved_target_per_connection():
    server = ServerModel(
        name='ad-lab-host',
        image='image-ad-lab-host',
        machine_type='n2-standard-8',
        nics=[NicModel(network='lab', internal_ip='10.1.1.10', ip_aliases=ALIASES)],
        human_interaction=[_rdp_alias(), _vnc_console(), _ordinary_ssh()],
    )
    build_model = SimpleNamespace(servers=[server], firewalls=False, build_type='unit', networks=[])
    with patch(f'{PROXY}.CloudEnv') as cloud_env, patch(f'{PROXY}.Logger'), \
            patch(f'{PROXY}.DocumentDatabaseFactory') as db_factory, patch(f'{PROXY}.DatabaseMask'), \
            patch(f'{PROXY}.ComputeManagerFactory'), patch(f'{GUAC}.CloudEnv') as guac_env, patch(f'{GUAC}.Logger'):
        cloud_env.return_value.main_app_url = 'app.example.com'
        cloud_env.return_value.parent_dns_suffix = '.example.com'
        guac_env.return_value.parent_dns_suffix = '.example.com'
        db = db_factory.create_db_object.return_value
        proxy = DisplayProxy('abcdefghij', build_model, env_dict={'x': 1})
        # The build record is only re-saved with proxy_connections; keep the real model out of it
        proxy.model = MagicMock()
        record = proxy.model.return_value

        server_record = proxy.prepare_server_record()

    targets = {c.internal_ip_address for c in record.proxy_connections}
    assert targets == {'10.1.1.21', '10.1.1.10'}
    assert len(record.proxy_connections) == 3
    script = server_record['guacamole_startup_script']
    assert "'hostname', '10.1.1.21'" in script
    assert "'port', '5903'" in script
    assert "'port', '22'" in script
    assert db.update.call_count == 2

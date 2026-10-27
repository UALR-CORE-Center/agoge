"""Direct connect to a nested host's jumpbox: the startup-script forward, run for real with fake iptables/ip."""
import json
import shutil
import subprocess
import textwrap
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from cloud_fn_utilities.course_objects.compute.lab_server_manager import LabServerManager
from cloud_fn_utilities.server_specific.nested_scripts import (HOST_JSON_PATH, direct_connect_slot,
                                                                 render_direct_connect)

needs_tools = pytest.mark.skipif(shutil.which('bash') is None or shutil.which('jq') is None,
                                 reason='needs bash and jq')

FAKE_IPTABLES = textwrap.dedent("""\
    #!/bin/bash
    echo "iptables $*" >> "$FAKE_LOG"
    table=filter
    if [ "$1" = "-t" ]; then table=$2; shift 2; fi
    op=$1; shift
    rule="$table $*"
    touch "$FAKE_RULES"
    case "$op" in
      -C) grep -qxF -- "$rule" "$FAKE_RULES" ;;
      -N) if grep -qxF -- "chain $table $1" "$FAKE_RULES"; then exit 1; fi; echo "chain $table $1" >> "$FAKE_RULES" ;;
      -I) chain=$1; shift; [ "${1:-}" = "1" ] && shift; echo "$table $chain $*" >> "$FAKE_RULES" ;;
      *) : ;;
    esac
""")
FAKE_IP = "#!/bin/bash\necho 'default via 10.1.1.1 dev ens4 proto dhcp src 10.1.1.10 metric 100'\n"
FAKE_LOGGER = '#!/bin/bash\necho "$(basename "$0") $*" >> "$FAKE_LOG"\n'

HOST = {
    'guests': [
        {'name': 'kali', 'nics': [{'network': 'lab', 'ip': '192.168.100.10'}]},
        {'name': 'win', 'nics': [{'network': 'lab', 'ip': '192.168.100.20'}]},
    ],
    'exposures': [['kali', 0]],
}

KALI_SSH = {'display': True, 'protocol': 'ssh', 'username': 'kali', 'alias_index': 0, 'nested_guest': 'kali'}
PARENT_SSH = {'display': False, 'protocol': 'ssh', 'username': 'instructor'}
DIRECT_NIC = {'network': 'external', 'subnet_name': 'default', 'internal_ip': '10.1.1.10',
              'ip_aliases': ['10.1.1.2'], 'external_nat': True, 'direct_connect': True}


@pytest.fixture
def forward(tmp_path):
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    for name, body in (('iptables', FAKE_IPTABLES), ('ip', FAKE_IP), ('sysctl', FAKE_LOGGER)):
        path = bin_dir / name
        path.write_text(body)
        path.chmod(0o755)

    def run(slot=0, host=HOST):
        script = tmp_path / 'direct-connect'
        script.write_text(render_direct_connect(slot))
        host_json = tmp_path / 'host.json'
        host_json.write_text(json.dumps(host))
        log = tmp_path / 'log'
        log.write_text('')
        env = {
            'PATH': f"{bin_dir}:/usr/bin:/bin:/opt/homebrew/bin:/usr/local/bin",
            'FAKE_LOG': str(log), 'FAKE_RULES': str(tmp_path / 'rules'),
            'AGOGE_NESTED_HOST_JSON': str(host_json),
        }
        result = subprocess.run(['bash', str(script)], capture_output=True, text=True, env=env, timeout=30)
        assert result.returncode == 0, result.stderr
        return log.read_text().splitlines(), result.stdout

    run.bin_dir = bin_dir
    return run


def test_render_fills_the_slot_and_host_json():
    script = render_direct_connect(2)
    assert 'SLOT=2' in script
    assert f'AGOGE_NESTED_HOST_JSON:-{HOST_JSON_PATH}' in script
    assert '@@' not in script


@needs_tools
def test_outside_ssh_to_the_primary_address_goes_to_the_jumpbox(forward):
    lines, stdout = forward()

    nat = [line for line in lines if line.startswith('iptables -t nat -A AGOGE-NESTED-DIRECT')]
    assert nat == [
        'iptables -t nat -A AGOGE-NESTED-DIRECT -s 10.0.0.0/8 -j RETURN',
        'iptables -t nat -A AGOGE-NESTED-DIRECT -s 172.16.0.0/12 -j RETURN',
        'iptables -t nat -A AGOGE-NESTED-DIRECT -s 192.168.0.0/16 -j RETURN',
        'iptables -t nat -A AGOGE-NESTED-DIRECT -s 35.235.240.0/20 -j RETURN',
        'iptables -t nat -A AGOGE-NESTED-DIRECT -d 10.1.1.10 -p tcp --dport 22 -j DNAT '
        '--to-destination 192.168.100.10:22',
    ]
    assert 'iptables -t nat -I PREROUTING 1 -j AGOGE-NESTED-DIRECT' in lines
    assert ('iptables -A AGOGE-NESTED-DIRECT-FWD -d 192.168.100.10 -p tcp --dport 22 -m conntrack --ctstate DNAT '
            '-j ACCEPT') in lines
    assert 'iptables -I FORWARD 1 -j AGOGE-NESTED-DIRECT-FWD' in lines
    assert 'sysctl -qw net.ipv4.ip_forward=1' in lines
    assert 'goes to 192.168.100.10' in stdout


@needs_tools
def test_a_second_boot_flushes_instead_of_adding_another_jump(forward):
    forward()
    lines, _ = forward()

    assert 'iptables -t nat -F AGOGE-NESTED-DIRECT' in lines
    assert not any(line.startswith('iptables -t nat -I PREROUTING') for line in lines)
    assert not any(line.startswith('iptables -I FORWARD') for line in lines)


@needs_tools
def test_a_default_route_without_src_falls_back_to_the_device_address(forward):
    (forward.bin_dir / 'ip').write_text(textwrap.dedent("""\
        #!/bin/bash
        case "$*" in
          *route*) echo 'default via 10.1.1.1 dev ens4 proto dhcp metric 100' ;;
          *addr*) echo '2: ens4    inet 10.1.1.10/32 metric 100 brd 10.1.1.10 scope global dynamic ens4' ;;
        esac
    """))
    lines, _ = forward()

    assert ('iptables -t nat -A AGOGE-NESTED-DIRECT -d 10.1.1.10 -p tcp --dport 22 -j DNAT '
            '--to-destination 192.168.100.10:22') in lines


@needs_tools
def test_a_slot_with_no_guest_leaves_ssh_on_the_host(forward):
    lines, stdout = forward(slot=3)

    assert not any(line.startswith('iptables') for line in lines)
    assert 'SSH stays on this host' in stdout


def test_slot_is_the_first_displayed_ssh_guest_connection():
    rdp = {'display': True, 'protocol': 'rdp', 'alias_index': 1, 'nested_guest': 'dc'}
    assert direct_connect_slot([PARENT_SSH, rdp, KALI_SSH]) == 0
    assert direct_connect_slot([PARENT_SSH, rdp]) is None
    assert direct_connect_slot([{**KALI_SSH, 'display': False}]) is None
    assert direct_connect_slot(None) is None


def _manager(nics, human_interaction):
    # Build only what _add_metadata reads; the real __init__ needs GCP and Firestore.
    manager = object.__new__(LabServerManager)
    manager.server_spec = SimpleNamespace(
        name='abcdefghij-nestedhost', os='linux', nics=nics, metadata=None, ssh_keys=[],
        startup_script=None, guacamole_startup_script=None, human_interaction=human_interaction,
    )
    manager.assessment = MagicMock()
    manager.assessment.get_startup_scripts.return_value = None
    return manager


def _startup_script(manager):
    manager._add_metadata()
    return next(item['value'] for item in manager.server_spec.metadata['items'] if item['key'] == 'startup-script')


def test_direct_connect_nested_host_gets_the_forward_once():
    manager = _manager([DIRECT_NIC], [PARENT_SSH, KALI_SSH])
    script = _startup_script(manager)
    assert script.count('agoge-nested-direct-connect') > 0
    assert render_direct_connect(0).strip() in script

    rebuilt = _manager([DIRECT_NIC], [PARENT_SSH, KALI_SSH])
    rebuilt.server_spec.metadata = {'items': [dict(item) for item in manager.server_spec.metadata['items']]}
    assert _startup_script(rebuilt).count('SLOT=0') == 1


@pytest.mark.parametrize('nic, connections', [
    ({**DIRECT_NIC, 'direct_connect': False}, [PARENT_SSH, KALI_SSH]),
    ({**DIRECT_NIC, 'external_nat': False}, [PARENT_SSH, KALI_SSH]),
    (DIRECT_NIC, [PARENT_SSH]),
])
def test_no_forward_without_direct_connect_or_a_jumpbox(nic, connections):
    assert 'agoge-nested-direct-connect' not in _startup_script(_manager([nic], connections))

"""agoge-nested-runtime (V10): the rendered script, executed for real with fake iptables/virsh/curl."""
import json
import shutil
import subprocess
import textwrap

import pytest

from cloud_fn_utilities.server_specific import nested_scripts
from cloud_fn_utilities.server_specific.nested_scripts import (HOST_JSON_PATH, RUNTIME_PATH, render_runtime,
                                                                 render_runtime_unit)

needs_tools = pytest.mark.skipif(shutil.which('bash') is None or shutil.which('jq') is None,
                                 reason='needs bash and jq')

# Every fake appends "<name> <args>" to $FAKE_LOG.
# iptables keeps rules in $FAKE_RULES, so -C and -N answer as the real one would on a second run.
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
FAKE_VIRSH = textwrap.dedent("""\
    #!/bin/bash
    echo "virsh $*" >> "$FAKE_LOG"
    case "$1" in
      -q) printf '%s\\n' $FAKE_ACTIVE_NETWORKS ;;
      domstate) cat "$FAKE_STATES/$2" 2>/dev/null || echo "shut off" ;;
    esac
""")
FAKE_CURL = textwrap.dedent("""\
    #!/bin/bash
    echo "curl $*" >> "$FAKE_LOG"
    [ -f "$FAKE_ALIASES" ] || exit 22
    # As GCE answers: the directory lists entry indices, and recursive=true returns the values as JSON
    case "$*" in
      *recursive=true*) jq -cR '[., inputs | select(length > 0)]' "$FAKE_ALIASES" ;;
      *) awk 'NF { print NR - 1 }' "$FAKE_ALIASES" ;;
    esac
""")
FAKE_IP = "#!/bin/bash\necho 'default via 10.1.0.1 dev ens4 proto dhcp src 10.1.0.5 metric 100'\n"
FAKE_LOGGER = '#!/bin/bash\necho "$(basename "$0") $*" >> "$FAKE_LOG"\n'

HOST = {
    'networks': [
        {'name': 'lab', 'cidr': '192.168.100.0/24', 'mode': 'nat', 'parent_address': '192.168.100.1'},
        {'name': 'dmz', 'cidr': '192.168.200.0/24', 'mode': 'isolated', 'parent_address': None},
    ],
    'guests': [
        {'name': 'kali', 'autostart': True, 'start_order': 2, 'start_delay_seconds': 0,
         'nics': [{'network': 'lab', 'ip': '192.168.100.10'}]},
        {'name': 'dc', 'autostart': True, 'start_order': 0, 'start_delay_seconds': 30,
         'nics': [{'network': 'lab', 'ip': None}, {'network': 'dmz', 'ip': '192.168.200.20'}]},
        {'name': 'web', 'autostart': True, 'start_order': 2, 'start_delay_seconds': 5,
         'nics': [{'network': 'dmz', 'ip': '192.168.200.30'}]},
        {'name': 'spare', 'autostart': False, 'start_order': 0, 'start_delay_seconds': 0,
         'nics': [{'network': 'lab', 'ip': None}]},
    ],
    # Slot 0 -> web, slot 1 -> dc's second NIC, slot 2 -> kali.
    'exposures': [['web', 0], ['dc', 1], ['kali', 0]],
    'console_ports': {'kali': 5901},
}
# The instance's alias CIDRs, one per line in aliasIpRanges order; FAKE_CURL serves them the way GCE does.
ALIASES = '10.1.0.20/32\n10.1.0.21/32\n10.1.0.22/32\n'


@pytest.fixture
def runtime(tmp_path):
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    for name, body in (('iptables', FAKE_IPTABLES), ('virsh', FAKE_VIRSH), ('curl', FAKE_CURL), ('ip', FAKE_IP),
                       ('systemctl', FAKE_LOGGER), ('sysctl', FAKE_LOGGER), ('sleep', FAKE_LOGGER)):
        path = bin_dir / name
        path.write_text(body)
        path.chmod(0o755)
    (tmp_path / 'states').mkdir()
    script = tmp_path / 'agoge-nested-runtime'
    script.write_text(render_runtime())

    def run(host=HOST, aliases=ALIASES, active_networks='lab'):
        host_json = tmp_path / 'host.json'
        if host is not None:
            host_json.write_text(json.dumps(host))
        alias_file = tmp_path / 'aliases'
        if aliases is None:
            alias_file.unlink(missing_ok=True)
        else:
            alias_file.write_text(aliases)
        log = tmp_path / 'log'
        log.write_text('')
        env = {
            'PATH': f"{bin_dir}:/usr/bin:/bin:/opt/homebrew/bin:/usr/local/bin",
            'FAKE_LOG': str(log), 'FAKE_RULES': str(tmp_path / 'rules'), 'FAKE_ALIASES': str(alias_file),
            'FAKE_STATES': str(tmp_path / 'states'), 'FAKE_ACTIVE_NETWORKS': active_networks,
            'AGOGE_NESTED_HOST_JSON': str(host_json),
            'AGOGE_NESTED_LIBVIRT_GUESTS_CONF': str(tmp_path / 'libvirt-guests'),
        }
        result = subprocess.run(['bash', str(script)], capture_output=True, text=True, env=env, timeout=60)
        assert result.returncode == 0, result.stderr
        return log.read_text().splitlines(), result.stdout

    run.tmp_path = tmp_path
    return run


def _iptables(lines):
    return [line for line in lines if line.startswith('iptables ')]


def test_rendered_runtime_fills_every_placeholder():
    script = render_runtime()

    assert '@@' not in script
    assert f'AGOGE_NESTED_HOST_JSON:-{HOST_JSON_PATH}' in script
    assert 'BRIDGES="agb+"' in script


def test_unit_runs_the_runtime_once_per_boot_after_libvirt():
    unit = render_runtime_unit()

    assert f'ExecStart={RUNTIME_PATH}' in unit
    assert 'Type=oneshot' in unit
    assert 'After=network-online.target libvirtd.service' in unit
    assert 'WantedBy=multi-user.target' in unit


def test_render_refuses_a_placeholder_without_a_value(tmp_path, monkeypatch):
    (tmp_path / 'x.sh').write_text('echo @@NOPE@@\n')
    monkeypatch.setattr(nested_scripts, 'NESTED_DIR', tmp_path)

    with pytest.raises(ValueError, match='NOPE'):
        nested_scripts._render('x.sh', {})


@pytest.mark.skipif(shutil.which('bash') is None, reason='needs bash')
def test_runtime_passes_bash_syntax_check(tmp_path):
    path = tmp_path / 'runtime.sh'
    path.write_text(render_runtime())

    result = subprocess.run(['bash', '-n', str(path)], capture_output=True, text=True, timeout=30)

    assert result.returncode == 0, result.stderr


@needs_tools
def test_forward_rejects_the_metadata_server_before_anything_else(runtime):
    lines, _ = runtime()

    assert _iptables(lines)[:2] == ['iptables -C FORWARD -d 169.254.169.254 -j REJECT',
                                    'iptables -I FORWARD -d 169.254.169.254 -j REJECT']
    # Our FORWARD chain is jumped to ahead of that rule, so it repeats the reject first.
    fwd = [line for line in lines if line.startswith('iptables -A AGOGE-NESTED-FWD')]
    assert fwd[0] == 'iptables -A AGOGE-NESTED-FWD -d 169.254.169.254 -j REJECT'


@needs_tools
def test_bridges_reach_the_parent_only_for_dhcp_and_dns(runtime):
    lines, _ = runtime()

    assert [line for line in lines if line.startswith('iptables -A AGOGE-NESTED-IN')] == [
        'iptables -A AGOGE-NESTED-IN -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT',
        'iptables -A AGOGE-NESTED-IN -p udp --dport 67 -j ACCEPT',
        'iptables -A AGOGE-NESTED-IN -p udp --dport 53 -j ACCEPT',
        'iptables -A AGOGE-NESTED-IN -p tcp --dport 53 -j ACCEPT',
        'iptables -A AGOGE-NESTED-IN -j DROP',
    ]
    assert 'iptables -t filter -I INPUT 1 -i agb+ -j AGOGE-NESTED-IN' in lines


@needs_tools
def test_aliases_map_to_exposed_guests_in_slot_order(runtime):
    lines, _ = runtime()

    assert [line for line in lines if 'AGOGE-NESTED-PRE -d' in line] == [
        'iptables -t nat -A AGOGE-NESTED-PRE -d 10.1.0.20 -j DNAT --to-destination 192.168.200.30',
        'iptables -t nat -A AGOGE-NESTED-PRE -d 10.1.0.21 -j DNAT --to-destination 192.168.200.20',
        'iptables -t nat -A AGOGE-NESTED-PRE -d 10.1.0.22 -j DNAT --to-destination 192.168.100.10',
    ]
    assert [line for line in lines if 'AGOGE-NESTED-POST -s' in line] == [
        'iptables -t nat -A AGOGE-NESTED-POST -s 192.168.200.30 -o ens4 -j SNAT --to-source 10.1.0.20',
        'iptables -t nat -A AGOGE-NESTED-POST -s 192.168.200.20 -o ens4 -j SNAT --to-source 10.1.0.21',
        'iptables -t nat -A AGOGE-NESTED-POST -s 192.168.100.10 -o ens4 -j SNAT --to-source 10.1.0.22',
    ]
    assert 'iptables -A AGOGE-NESTED-FWD -d 192.168.200.30 -m conntrack --ctstate DNAT -j ACCEPT' in lines
    assert ('iptables -A AGOGE-NESTED-FWD -s 192.168.200.30 -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT'
            in lines)
    for jump in ('iptables -t nat -I PREROUTING 1 -j AGOGE-NESTED-PRE',
                 'iptables -t nat -I POSTROUTING 1 -j AGOGE-NESTED-POST',
                 'iptables -t filter -I FORWARD 1 -j AGOGE-NESTED-FWD'):
        assert jump in lines
    assert 'sysctl -qw net.ipv4.ip_forward=1' in lines


@needs_tools
def test_missing_aliases_leave_later_slots_unexposed_without_failing(runtime):
    lines, out = runtime(aliases='10.1.0.20/32\n')

    assert [line for line in lines if 'AGOGE-NESTED-PRE -d' in line] == [
        'iptables -t nat -A AGOGE-NESTED-PRE -d 10.1.0.20 -j DNAT --to-destination 192.168.200.30']
    assert 'slot 1: no alias IP on NIC 0; dc is not exposed' in out
    assert 'slot 2: no alias IP on NIC 0; kali is not exposed' in out


@needs_tools
def test_extra_aliases_are_ignored(runtime):
    lines, out = runtime(aliases=ALIASES + '10.1.0.23/32\n')

    assert not any('10.1.0.23' in line for line in lines)
    assert 'ignoring 1 extra alias IP(s)' in out


@needs_tools
def test_unreadable_aliases_expose_nothing_and_still_start_guests(runtime):
    lines, out = runtime(aliases=None)

    assert not any('DNAT' in line and '-A' in line for line in lines)
    assert 'could not read NIC 0 alias IPs' in out
    assert 'sysctl -qw net.ipv4.ip_forward=1' not in lines
    assert 'virsh start dc' in lines


@needs_tools
def test_second_run_adds_no_duplicate_jumps(runtime):
    runtime()
    lines, _ = runtime()

    assert not any(line.startswith(('iptables -I', 'iptables -t nat -I', 'iptables -t filter -I')) for line in lines)
    rules = (runtime.tmp_path / 'rules').read_text().splitlines()
    assert len(rules) == len(set(rules))


@needs_tools
def test_guests_start_in_start_order_with_their_delays(runtime):
    lines, _ = runtime()

    starts = [line for line in lines if line.startswith(('virsh start', 'sleep'))]
    # dc (order 0, 30 s), then kali and web (order 2) in list order; spare is not autostart.
    assert starts == ['sleep 30', 'virsh start dc', 'virsh start kali', 'sleep 5', 'virsh start web']
    for guest in ('kali', 'dc', 'web', 'spare'):
        assert f'virsh autostart --disable {guest}' in lines
    # Autostart is disabled for every guest before the first start.
    assert lines.index('virsh autostart --disable spare') < lines.index('virsh start dc')


@needs_tools
def test_running_guests_are_not_started_again(runtime):
    (runtime.tmp_path / 'states' / 'dc').write_text('running\n')

    lines, _ = runtime()

    assert 'virsh start dc' not in lines
    assert 'sleep 30' not in lines
    assert 'virsh start kali' in lines


@needs_tools
def test_inactive_networks_are_started_before_the_firewall(runtime):
    lines, _ = runtime(active_networks='lab')

    assert 'virsh net-start dmz' in lines
    assert 'virsh net-start lab' not in lines
    assert lines.index('virsh net-start dmz') < lines.index('iptables -t filter -I INPUT 1 -i agb+ -j AGOGE-NESTED-IN')


@needs_tools
def test_libvirt_guests_shuts_guests_down_on_stop(runtime):
    lines, _ = runtime()

    conf = (runtime.tmp_path / 'libvirt-guests').read_text().splitlines()
    for setting in ('ON_SHUTDOWN=shutdown', 'PARALLEL_SHUTDOWN=8', 'SHUTDOWN_TIMEOUT=80', 'ON_BOOT=ignore'):
        assert setting in conf
    assert 'systemctl enable --now libvirt-guests.service' in lines
    assert lines.index('systemctl enable --now libvirt-guests.service') < lines.index('virsh start dc')


@needs_tools
def test_without_host_json_only_the_metadata_reject_is_applied(runtime):
    lines, out = runtime(host=None)

    assert lines == ['iptables -C FORWARD -d 169.254.169.254 -j REJECT',
                     'iptables -I FORWARD -d 169.254.169.254 -j REJECT']
    assert 'nothing else to do' in out

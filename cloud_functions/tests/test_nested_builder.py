"""agoge-nested-builder (V9): the rendered script, executed for real with fake libvirt/curl/virt-customize.

Every fake (and a jq wrapper) logs its full argv, so a secret on any command line shows up in the log.
"""
import base64
import bz2
import gzip
import hashlib
import json
import lzma
import os
import re
import shutil
import stat
import subprocess
import sys
import textwrap
import zipfile

import pytest

from cloud_fn_utilities.server_specific import nested_scripts
from cloud_fn_utilities.server_specific.nested_scripts import (MEDIA_DIR, RUN_DIR, RUNTIME_PATH, RUNTIME_UNIT_NAME,
                                                                 render_builder, render_runtime)
from common.models.agoge import NestedHostSpecModel, NestedMediaModel, NestedOsCatalogModel
from common.utilities.nested_manifest import build_secrets, render_autounattend, render_manifest

REAL_JQ = shutil.which('jq')
needs_tools = pytest.mark.skipif(shutil.which('bash') is None or REAL_JQ is None or shutil.which('shasum') is None,
                                 reason='needs bash, jq, and shasum')

ADMIN_PASSWORD = 'Adm1n-S3cret!x'
DEB_IMAGE = b'debian cloud image bytes'
WIN_ISO = b'windows server iso bytes'
FW_ISO = b'firewall appliance iso bytes'
FW_NANO = bz2.compress(b'preinstalled firewall disk bytes')
POST_INSTALL = 'apt-get install -y nginx\necho done\n'

FAKE_CURL = textwrap.dedent("""\
    #!/bin/bash
    echo "curl $*" >> "$FAKE_LOG"
    out= data= url=
    while [ $# -gt 0 ]; do
      case "$1" in
        -o) out=$2; shift ;;
        --data|--data-binary|-d) data=$2; shift ;;
        -X|-H|-T|--retry) shift ;;
        http*) url=$1 ;;
      esac
      shift
    done
    emit() { [ -f "$1" ] || exit 22; if [ -n "$out" ]; then cat "$1" > "$out"; else cat "$1"; fi; }
    case "$url" in
      */guest-attributes/agoge-nested/*) echo "${url##*/}=$data" >> "$FAKE_DIR/attributes" ;;
      */attributes/agoge-nested-manifest) emit "$FAKE_DIR/manifest.json" ;;
      */attributes/agoge-nested-secrets) emit "$FAKE_DIR/secrets.json" ;;
      */project/project-id) printf test-project ;;
      */service-accounts/default/token) printf '{"access_token":"fake-token","expires_in":3599}' ;;
      https://storage.googleapis.com/upload/*) echo "$url" >> "$FAKE_DIR/uploads" ;;
      https://storage.googleapis.com/storage/v1/b/*)
        path=${url#https://storage.googleapis.com/storage/v1/b/}
        bucket=${path%%/*}; object=${path#*/o/}; object=${object%%\\?*}
        emit "$FAKE_DIR/gcs/$bucket/$(printf '%b' "${object//%/\\\\x}")" ;;
      https://*) emit "$FAKE_DIR/web/${url##*/}" ;;
      *) exit 22 ;;
    esac
""")
# gcloud storage cp gs://bucket/object dest, served from $FAKE_DIR/gcs.
FAKE_GCLOUD = textwrap.dedent("""\
    #!/bin/bash
    echo "gcloud $*" >> "$FAKE_LOG"
    [ "$1 $2" = "storage cp" ] || exit 2
    shift 2
    [ "$1" = "--no-user-output-enabled" ] && shift
    src=${1#gs://}
    [ -f "$FAKE_DIR/gcs/$src" ] || exit 1
    cp "$FAKE_DIR/gcs/$src" "$2"
""")
# Domains live in $FAKE_DIR/domains: <name>.xml (as defined) and <name>.state.
# Names in $FAKE_SELF_POWEROFF power themselves off after their first start (Windows Setup).
FAKE_VIRSH = textwrap.dedent("""\
    #!/bin/bash
    echo "virsh $*" >> "$FAKE_LOG"
    D="$FAKE_DIR/domains"
    mkdir -p "$D"
    case "$1" in
      net-info) exit 1 ;;
      define)
        name=$(sed -n 's:.*<name>\\(.*\\)</name>.*:\\1:p' "$2" | head -n 1)
        cp "$2" "$D/$name.xml"; echo "shut off" > "$D/$name.state" ;;
      domstate)
        [ -f "$D/$2.state" ] || exit 1
        if [ -f "$D/$2.poweroff" ]; then rm "$D/$2.poweroff"; echo running; echo "shut off" > "$D/$2.state"
        else cat "$D/$2.state"; fi ;;
      start)
        [ -f "$D/$2.state" ] || exit 1
        echo running > "$D/$2.state"
        case " $FAKE_SELF_POWEROFF " in
          *" $2 "*) [ -f "$D/$2.installed" ] || touch "$D/$2.poweroff" "$D/$2.installed" ;;
        esac ;;
      shutdown) echo "shut off" > "$D/$2.state" ;;
      undefine) rm -f "$D/$2.state" "$D/$2.xml" ;;
      qemu-agent-command)
        dom=$2; shift 2
        [ "$1" = "--timeout" ] && shift 2
        [ "$(cat "$D/$dom.state" 2>/dev/null)" = running ] || exit 1
        case "$1" in
          *guest-exec-status*) cat "$FAKE_DIR/exec-status-$dom" 2>/dev/null || echo '{"return":{"exited":true,"exitcode":0}}' ;;
          *guest-exec*) echo "$1" > "$FAKE_DIR/exec-request-$dom"; echo '{"return":{"pid":42}}' ;;
          *) echo '{"return":{}}' ;;
        esac ;;
      domblklist)
        printf ' Type   Device   Target   Source\\n------\\n file   disk    vda   /d.qcow2\\n'
        printf ' file   cdrom   sda   /os.iso\\n file   cdrom   sdb   /unattend.iso\\n' ;;
    esac
    exit 0
""")
FAKE_VIRT_INSTALL = textwrap.dedent("""\
    #!/bin/bash
    echo "virt-install $*" >> "$FAKE_LOG"
    name= graphics=
    while [ $# -gt 0 ]; do
      case "$1" in
        --name) name=$2; shift ;;
        --graphics) graphics=$2; shift ;;
        --osinfo) if [ "$2" = "${FAKE_BAD_OSINFO:-}" ]; then echo "ERROR Unknown OS name '$2'" >&2; exit 1; fi; shift ;;
      esac
      shift
    done
    echo '<domain type="kvm">'
    echo "  <name>$name</name>"
    case "$graphics" in vnc*) echo '  <graphics type="vnc" port="5901" listen="0.0.0.0">'; echo '  </graphics>' ;; esac
    echo '</domain>'
""")
FAKE_QEMU_IMG = textwrap.dedent("""\
    #!/bin/bash
    echo "qemu-img $*" >> "$FAKE_LOG"
    case "$1" in
      create) touch "${@: -2:1}" ;;
      convert) touch "${@: -1}" ;;
      info) echo '{"virtual-size": 2147483648}' ;;
    esac
""")
FAKE_GENISOIMAGE = textwrap.dedent("""\
    #!/bin/bash
    echo "genisoimage $*" >> "$FAKE_LOG"
    while [ $# -gt 0 ]; do [ "$1" = "-o" ] && { out=$2; shift; }; last=$1; shift; done
    cp "$last/autounattend.xml" "$out"
""")
FAKE_LOGGER = '#!/bin/bash\necho "$(basename "$0") $*" >> "$FAKE_LOG"\n'
FAKE_SLEEP = '#!/bin/bash\necho "sleep $*" >> "$FAKE_LOG"\n/bin/sleep 0.01\n'
FAKE_SHA256SUM = '#!/bin/bash\necho "sha256sum $*" >> "$FAKE_LOG"\nexec shasum -a 256 "$@"\n'
# p7zip is rarely installed on a dev machine; zipfile extracts `7z x -y -o<dir> <archive>` the same way, paths kept.
FAKE_7Z = textwrap.dedent(f"""\
    #!/bin/bash
    echo "7z $*" >> "$FAKE_LOG"
    for arg in "$@"; do case "$arg" in -o*) out=${{arg#-o}} ;; esac; done
    exec {sys.executable} -c 'import sys, zipfile; zipfile.ZipFile(sys.argv[2]).extractall(sys.argv[1])' "$out" "${{@: -1}}"
""")


def _sha(content):
    return hashlib.sha256(content).hexdigest()


def _entry(entry_id, **fields):
    base = dict(id=entry_id, display_name=entry_id, version='1', license_note='lab use', min_memory_mb=512,
                default_memory_mb=1024, min_disk_gb=2, default_disk_gb=10)
    base.update(fields)
    return NestedOsCatalogModel(**base)


CATALOG = {entry.id: entry for entry in (
    _entry('debian-12', family='linux', group='linux', install_method='cloud_image',
           media_url='https://cloud.debian.example/debian-12.qcow2', media_sha256=_sha(DEB_IMAGE),
           media_formats=['qcow2'], osinfo='debian12', agent=True, net_config='networkd'),
    _entry('win-server-2022-eval', family='windows', group='windows_server', install_method='unattended_iso',
           media_url='https://msft.example/server2022.iso', media_sha256=_sha(WIN_ISO), media_formats=['iso'],
           eval_days=180, osinfo='win2k22', agent=True, net_config='windows', unattend_template='autounattend',
           windows_image_index=2, virtio_win_version='0.1.262-2'),
    _entry('pfsense', family='appliance', group='appliance', install_method='manual_iso', requires_upload=True,
           media_formats=['iso'], osinfo='freebsd14.0', agent=False, net_config='none'),
    _entry('opnsense', family='appliance', group='appliance', install_method='disk_image',
           media_url='https://pkg.opnsense.example/nano.img.bz2', media_sha256=_sha(FW_NANO), media_formats=['img.bz2'],
           osinfo='freebsd14.0', agent=False, net_config='none'),
)}
UPLOAD = NestedMediaModel(id='med-1', filename='fw.iso', format='iso', size_bytes=len(FW_ISO),
                          gcs_path='gs://test-project_nested-media/media/med-1/fw.iso', uploaded_by='t@example.com',
                          uploaded_at='2026-10-17T00:00:00Z', complete=True)


def _spec(**guest_overrides):
    guests = [
        dict(name='deb', os_id='debian-12', admin_username='labadmin', admin_password=ADMIN_PASSWORD,
             packages=['nmap'], post_install_script=POST_INSTALL, start_order=1,
             nics=[{'network': 'lan', 'ip': '10.10.0.10', 'expose': True}]),
        dict(name='win', os_id='win-server-2022-eval', admin_username='labadmin', admin_password=ADMIN_PASSWORD,
             memory_mb=4096, disk_gb=40, start_order=0,
             nics=[{'network': 'lan', 'ip': '10.10.0.20'}, {'network': 'dmz', 'ip': '10.20.0.20'}]),
        dict(name='fw', os_id='pfsense', media_id='med-1', admin_username='admin', admin_password=ADMIN_PASSWORD,
             start_order=2, autostart=False, nics=[{'network': 'dmz'}]),
    ]
    for guest in guests:
        guest.update(guest_overrides.get(guest['name'], {}))
    spec = NestedHostSpecModel(
        parent_os='debian-12',
        networks=[{'name': 'lan', 'cidr': '10.10.0.0/24', 'mode': 'nat', 'parent_address': '10.10.0.1',
                   'dhcp_start': '10.10.0.100', 'dhcp_end': '10.10.0.200'},
                  {'name': 'dmz', 'cidr': '10.20.0.0/24', 'mode': 'isolated', 'parent_address': None, 'dhcp': False}],
        guests=guests)
    return spec.model_copy(update={
        'exposures': [('deb', 0)],
        'console_ports': {'deb': 5901, 'win': 5902, 'fw': 5903},
        'vnc_passwords': {'deb': 'Vnc0deb1', 'win': 'Vnc0win2', 'fw': 'Vnc0fw03'},
    })


def _secrets(spec):
    # V11 adds each Windows guest's rendered autounattend.xml (Iteration 96's recommendation).
    secrets = build_secrets(spec)
    for guest in spec.guests:
        entry = CATALOG[guest.os_id]
        if entry.install_method == 'unattended_iso':
            secrets[guest.name]['autounattend'] = render_autounattend(guest, entry, secrets, spec.networks)
    return secrets


def _secret_strings(secrets):
    return {value for guest in secrets.values() for key, value in guest.items() if key != 'autounattend'}


@pytest.fixture
def builder(tmp_path):
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    fakes = {'curl': FAKE_CURL, 'gcloud': FAKE_GCLOUD, 'virsh': FAKE_VIRSH, 'virt-install': FAKE_VIRT_INSTALL, 'qemu-img': FAKE_QEMU_IMG,
             'genisoimage': FAKE_GENISOIMAGE, 'sleep': FAKE_SLEEP, 'sha256sum': FAKE_SHA256SUM, '7z': FAKE_7Z,
             'jq': f'#!/bin/bash\necho "jq $*" >> "$FAKE_LOG"\nexec {REAL_JQ} "$@"\n'}
    for name in ('virt-customize', 'apt-get', 'systemctl', 'chgrp'):
        fakes[name] = FAKE_LOGGER
    for name, body in fakes.items():
        (bin_dir / name).write_text(body)
        (bin_dir / name).chmod(0o755)
    fake_dir = tmp_path / 'fake'
    (fake_dir / 'web').mkdir(parents=True)
    (fake_dir / 'web' / 'debian-12.qcow2').write_bytes(DEB_IMAGE)
    (fake_dir / 'web' / 'server2022.iso').write_bytes(WIN_ISO)
    (fake_dir / 'web' / 'virtio-win.iso').write_bytes(b'virtio')
    (fake_dir / 'gcs' / 'test-project_nested-media' / 'media' / 'med-1').mkdir(parents=True)
    (fake_dir / 'gcs' / 'test-project_nested-media' / 'media' / 'med-1' / 'fw.iso').write_bytes(FW_ISO)
    root = tmp_path / 'root'
    script = tmp_path / 'agoge-nested-builder'
    script.write_text(render_builder())

    def run(spec=None, secrets=None, manifest=True, extra_env=None, secrets_present=True):
        spec = spec or _spec()
        secrets = secrets if secrets is not None else _secrets(spec)
        if manifest:
            (fake_dir / 'manifest.json').write_text(render_manifest(spec, CATALOG, {UPLOAD.id: UPLOAD}))
        (fake_dir / 'secrets.json').write_text(json.dumps(secrets))
        if not secrets_present:
            # The metadata server answers 404 once the build monitor has removed the key.
            (fake_dir / 'secrets.json').unlink()
        log = tmp_path / 'log'
        log.write_text('')
        (fake_dir / 'attributes').write_text('')
        env = {
            'PATH': f"{bin_dir}:/usr/bin:/bin:/opt/homebrew/bin:/usr/local/bin",
            'FAKE_LOG': str(log), 'FAKE_DIR': str(fake_dir), 'FAKE_SELF_POWEROFF': 'win',
            'AGOGE_NESTED_ROOT': str(root), **(extra_env or {}),
        }
        result = subprocess.run(['bash', str(script)], capture_output=True, text=True, env=env, timeout=120)
        return result, log.read_text()

    run.root = root
    run.fake = fake_dir
    return run


def _attributes(fake_dir):
    """The last value written to each guest attribute, plus the full history."""
    history = [line.split('=', 1) for line in (fake_dir / 'attributes').read_text().splitlines()]
    return dict(history), history


def _commands(log, name):
    return [line for line in log.splitlines() if line.startswith(f'{name} ')]


def test_rendered_builder_passes_bash_n(tmp_path):
    script = tmp_path / 'builder.sh'
    script.write_text(render_builder())

    assert '@@' not in script.read_text()
    assert subprocess.run(['bash', '-n', str(script)], capture_output=True).returncode == 0


def test_builder_never_destroys_a_domain():
    # Guests are shut down over ACPI; a guest that will not stop is failed, never killed.
    assert not re.search(r'virsh\s+destroy', render_builder())


def test_secrets_metadata_is_read_only_into_the_tmpfs_copy():
    lines = [line for line in render_builder().splitlines() if 'agoge-nested-secrets' in line
             and not line.lstrip().startswith('#')]

    fetches = [line for line in lines if 'metadata_get' in line]
    assert len(fetches) == 1 and '> "$SECRETS"' in fetches[0]
    assert 'SECRETS="$RUN_DIR/secrets.json"' in render_builder()
    assert f'RUN_DIR="$ROOT{RUN_DIR}"' in render_builder()


def test_builder_embeds_the_current_runtime():
    assert render_runtime().rstrip('\n') in render_builder()


def test_render_refuses_a_runtime_containing_a_heredoc_delimiter(monkeypatch):
    monkeypatch.setattr(nested_scripts, 'render_runtime', lambda: 'echo\nAGOGE_NESTED_RUNTIME_SCRIPT\n')

    with pytest.raises(ValueError, match='heredoc delimiter'):
        render_builder()


@needs_tools
def test_full_build_reports_ready_and_leaves_guests_running(builder):
    result, log = builder()

    assert result.returncode == 0, result.stderr
    last, history = _attributes(builder.fake)
    assert last['phase'] == 'ready'
    assert ['phase', 'building'] in history
    assert last['guest-deb'] == 'ready'
    assert last['guest-win'] == 'ready'
    assert last['guest-fw'] == 'manual'
    assert 'heartbeat' in last
    assert last['message'] == 'ready; every guest was built'
    for guest, statuses in (('deb', ['pending', 'downloading', 'installing', 'post_install', 'ready']),
                            ('win', ['pending', 'downloading', 'installing', 'ready'])):
        assert [value for key, value in history if key == f'guest-{guest}'] == statuses
    states = {name: (builder.fake / 'domains' / f'{name}.state').read_text().strip() for name in ('deb', 'win', 'fw')}
    assert states == {'deb': 'running', 'win': 'running', 'fw': 'running'}


@needs_tools
def test_no_secret_reaches_a_command_line(builder):
    secrets = _secrets(_spec())

    result, log = builder(secrets=secrets)

    assert result.returncode == 0, result.stderr
    for secret in _secret_strings(secrets):
        assert secret not in log
    # virt-customize reads the admin password from a root-only file, which is gone afterwards.
    customize = _commands(log, 'virt-customize')
    assert len(customize) == 1
    password_file = f"{builder.root}{RUN_DIR}/password-deb"
    assert f'--password labadmin:file:{password_file}' in customize[0]
    assert not os.path.exists(password_file)
    # The VNC password is in the defined domain XML, not in virt-install's arguments.
    assert 'passwd="Vnc0deb1"' in (builder.fake / 'domains' / 'deb.xml').read_text()
    assert 'passwd="Vnc0win2"' in (builder.fake / 'domains' / 'win.xml').read_text()
    assert not list((builder.root / RUN_DIR.lstrip('/')).glob('domain-*.xml'))


@needs_tools
def test_secrets_copy_is_root_only_on_tmpfs(builder):
    result, _ = builder()

    secrets_file = builder.root / RUN_DIR.lstrip('/') / 'secrets.json'
    assert result.returncode == 0, result.stderr
    assert stat.S_IMODE(secrets_file.stat().st_mode) == 0o600
    # The unattend ISO (it holds the admin password) is deleted once Setup has finished.
    assert not list((builder.root / RUN_DIR.lstrip('/')).glob('unattend-*'))


@needs_tools
def test_media_is_verified_and_kept_under_the_libvirt_boot_directory(builder):
    result, log = builder()

    media_dir = builder.root / MEDIA_DIR.lstrip('/')
    assert result.returncode == 0, result.stderr
    assert MEDIA_DIR == '/var/lib/libvirt/boot/agoge-nested'
    assert (media_dir / f'{_sha(DEB_IMAGE)}.qcow2').read_bytes() == DEB_IMAGE
    assert (media_dir / f'{_sha(WIN_ISO)}.iso').read_bytes() == WIN_ISO
    assert (media_dir / 'upload-med-1.iso').read_bytes() == FW_ISO
    # Uploaded media comes through gcloud storage cp (V15).
    assert 'gcloud storage cp --no-user-output-enabled gs://test-project_nested-media/media/med-1/fw.iso ' in log
    assert (media_dir / 'virtio-win-0.1.262-2.iso').is_file()
    # The cache is tried first, and a verified URL download is copied into it.
    assert f"storage/v1/b/test-project_nested-media/o/cache%2F{_sha(DEB_IMAGE)}?alt=media" in log
    uploads = (builder.fake / 'uploads').read_text()
    assert f"name=cache%2F{_sha(DEB_IMAGE)}" in uploads
    assert 'virtio-win-0.1.262-2/virtio-win.iso' in log
    for line in _commands(log, 'virt-install'):
        for cdrom in re.findall(r'path=([^,]+),device=cdrom', line):
            assert cdrom.startswith(str(media_dir)) or '/unattend-' in cdrom


@needs_tools
def test_runtime_is_installed_and_started_before_the_first_virt_install(builder):
    result, log = builder()

    lines = log.splitlines()
    start = lines.index(f'systemctl restart {RUNTIME_UNIT_NAME}')
    first_install = next(index for index, line in enumerate(lines) if line.startswith('virt-install '))
    assert result.returncode == 0, result.stderr
    assert start < first_install
    assert f'systemctl enable {RUNTIME_UNIT_NAME}' in lines[:start]
    assert (builder.root / RUNTIME_PATH.lstrip('/')).read_text().rstrip('\n') == render_runtime().rstrip('\n')
    host = json.loads((builder.root / 'etc/agoge-nested/host.json').read_text())
    # The final host.json carries each guest's own autostart; while building it is off for all.
    assert {guest['name']: guest['autostart'] for guest in host['guests']} == {'deb': True, 'win': True, 'fw': False}
    assert host['exposures'] == [['deb', 0]]
    assert 'catalog' not in host['guests'][0]


@needs_tools
def test_networks_replace_libvirts_default(builder):
    result, log = builder()

    assert result.returncode == 0, result.stderr
    assert log.index('virsh net-destroy default') < log.index('virsh net-define')
    lan = (builder.root / 'var/lib/agoge-nested/work/network-lan.xml').read_text()
    dmz = (builder.root / 'var/lib/agoge-nested/work/network-dmz.xml').read_text()
    assert '<bridge name="agb0"' in lan and '<forward mode="nat"/>' in lan
    assert '<ip address="10.10.0.1" prefix="24">' in lan
    assert '<range start="10.10.0.100" end="10.10.0.200"/>' in lan
    assert 'name="deb" ip="10.10.0.10"' in lan and 'name="win" ip="10.10.0.20"' in lan
    # Isolated with no parent address: a pure L2 segment.
    assert '<bridge name="agb1"' in dmz and '<forward' not in dmz and '<ip' not in dmz
    assert 'virsh net-autostart lan' in log and 'virsh net-start dmz' in log


@needs_tools
def test_domains_get_host_passthrough_agent_channel_and_console(builder):
    result, log = builder()

    installs = {re.search(r'--name (\S+)', line).group(1): line for line in _commands(log, 'virt-install')}
    assert result.returncode == 0, result.stderr
    for name, port in (('deb', 5901), ('win', 5902), ('fw', 5903)):
        assert '--cpu host-passthrough' in installs[name]
        assert 'target.name=org.qemu.guest_agent.0' in installs[name]
        assert f'--graphics vnc,listen=0.0.0.0,port={port}' in installs[name]
    assert '--boot hd,cdrom' in installs['win']
    assert installs['win'].count('device=cdrom') == 3
    assert '--osinfo win2k22' in installs['win']
    assert 'mac=52:54:00:' in installs['win']
    # libvirt autostart stays off: the runtime starts guests in start_order (iteration 97).
    assert 'virsh autostart' not in log


@needs_tools
def test_windows_waits_for_shut_off_then_ejects_media_and_starts_again(builder):
    result, log = builder()

    win = [line for line in log.splitlines() if line.startswith('virsh ') and ' win' in line]
    assert result.returncode == 0, result.stderr
    first_start = win.index('virsh start win')
    eject = win.index('virsh change-media win sda --eject --config')
    assert first_start < eject < len(win) - 1 - win[::-1].index('virsh start win')
    assert 'virsh change-media win sdb --eject --config' in win
    iso_args = [line for line in _commands(log, 'genisoimage')]
    assert len(iso_args) == 1 and ADMIN_PASSWORD not in iso_args[0]


@needs_tools
def test_cloud_image_customization(builder):
    result, log = builder()

    customize = _commands(log, 'virt-customize')[0]
    assert result.returncode == 0, result.stderr
    assert '--hostname deb' in customize
    assert '--install qemu-guest-agent,openssh-server,nmap' in customize
    assert '--touch /etc/cloud/cloud-init.disabled' in customize
    assert 'purge' not in customize
    assert '/etc/systemd/network/10-agoge-0.network' in customize
    assert '--selinux-relabel' not in customize
    network = (builder.root / 'var/lib/agoge-nested/work/net-deb/10-agoge-0.network').read_text()
    assert 'Address=10.10.0.10/24' in network and 'Gateway=10.10.0.1' in network and 'DNS=10.10.0.1' in network
    assert f'qemu-img resize {builder.root}/var/lib/libvirt/images/deb.qcow2 20G' in log


@needs_tools
def test_rhel_family_relabels_and_unblocks_guest_exec(builder):
    rocky = _entry('rocky-9', family='linux', group='linux', install_method='cloud_image',
                   media_url='https://cloud.debian.example/debian-12.qcow2', media_sha256=_sha(DEB_IMAGE),
                   media_formats=['qcow2'], osinfo='rocky9', agent=True, net_config='nm-keyfile')
    CATALOG['rocky-9'] = rocky
    try:
        result, log = builder(spec=_spec(deb={'os_id': 'rocky-9'}))
    finally:
        del CATALOG['rocky-9']

    customize = _commands(log, 'virt-customize')[0]
    assert result.returncode == 0, result.stderr
    assert '--selinux-relabel' in customize
    assert '/etc/sysconfig/qemu-ga' in customize
    assert '/etc/NetworkManager/system-connections/agoge-0.nmconnection' in customize


@needs_tools
def test_arch_initializes_pacman_and_installs_its_own_ssh_and_sudo_packages(builder):
    arch = _entry('archlinux', family='linux', group='linux', install_method='cloud_image',
                  media_url='https://cloud.debian.example/debian-12.qcow2', media_sha256=_sha(DEB_IMAGE),
                  media_formats=['qcow2'], osinfo='archlinux', agent=True, net_config='networkd')
    CATALOG['archlinux'] = arch
    try:
        result, log = builder(spec=_spec(deb={'os_id': 'archlinux'}))
    finally:
        del CATALOG['archlinux']

    customize = _commands(log, 'virt-customize')[0]
    assert result.returncode == 0, result.stderr
    # Arch has no openssh-server package; pacman would refuse the whole --install.
    assert '--install qemu-guest-agent,sudo,openssh,nmap' in customize
    assert 'openssh-server' not in customize
    # The keyring and sync databases must exist before --install, so the order matters.
    assert customize.index('pacman -Syu --noconfirm') < customize.index('--install')
    assert '/etc/sudoers.d/10-agoge-wheel:%wheel ALL=(ALL:ALL) ALL' in customize
    assert '/etc/systemd/network/10-agoge-0.network' in customize
    assert '--selinux-relabel' not in customize


@needs_tools
def test_opensuse_relabels_and_lets_wheel_sudo_with_its_own_password(builder):
    leap = _entry('opensuse-leap-16.0', family='linux', group='linux', install_method='cloud_image',
                  media_url='https://cloud.debian.example/debian-12.qcow2', media_sha256=_sha(DEB_IMAGE),
                  media_formats=['qcow2'], osinfo='opensuse16.0', agent=True, net_config='nm-keyfile')
    CATALOG['opensuse-leap-16.0'] = leap
    try:
        result, log = builder(spec=_spec(deb={'os_id': 'opensuse-leap-16.0'}))
    finally:
        del CATALOG['opensuse-leap-16.0']

    customize = _commands(log, 'virt-customize')[0]
    assert result.returncode == 0, result.stderr
    # Leap 16 enforces SELinux; an unlabelled keyfile is ignored by NetworkManager.
    assert '--selinux-relabel' in customize
    assert '--install qemu-guest-agent,openssh-server,nmap' in customize
    # Stock SUSE sudoers is "Defaults targetpw" with root locked, so wheel needs both drop-ins to sudo at all.
    assert '/etc/sudoers.d/10-agoge-wheel:%wheel ALL=(ALL:ALL) ALL' in customize
    assert '/etc/sudoers.d/10-agoge-wheel-auth-self:Defaults:%wheel !targetpw' in customize
    assert '0440:/etc/sudoers.d/10-agoge-wheel-auth-self' in customize
    assert '/etc/NetworkManager/system-connections/agoge-0.nmconnection' in customize
    assert 'pacman' not in customize


@needs_tools
def test_non_arch_guests_skip_the_pacman_setup(builder):
    result, log = builder()

    customize = _commands(log, 'virt-customize')[0]
    assert result.returncode == 0, result.stderr
    assert 'pacman' not in customize and 'sudoers.d' not in customize


@needs_tools
def test_netplan_default_route_uses_a_cidr_older_netplan_accepts(builder):
    ubuntu = _entry('ubuntu-18.04', family='linux', group='linux', install_method='cloud_image',
                    media_url='https://cloud.debian.example/debian-12.qcow2', media_sha256=_sha(DEB_IMAGE),
                    media_formats=['qcow2'], osinfo='ubuntu18.04', agent=True, net_config='netplan')
    CATALOG['ubuntu-18.04'] = ubuntu
    try:
        result, log = builder(spec=_spec(deb={'os_id': 'ubuntu-18.04'}))
    finally:
        del CATALOG['ubuntu-18.04']

    customize = _commands(log, 'virt-customize')[0]
    assert result.returncode == 0, result.stderr
    assert '/etc/netplan/90-agoge.yaml' in customize
    netplan = (builder.root / 'var/lib/agoge-nested/work/net-deb/90-agoge.yaml').read_text()
    assert 'addresses: ["10.10.0.10/24"]' in netplan
    # netplan 0.99 (Ubuntu 18.04) has no "default" keyword; 0.0.0.0/0 works on every version.
    assert 'routes: [{to: 0.0.0.0/0, via: "10.10.0.1"}]' in netplan
    assert 'to: default' not in netplan


@needs_tools
def test_ifupdown_config_is_a_cfg_file_ubuntu_16_04_sources(builder):
    ubuntu = _entry('ubuntu-16.04', family='linux', group='linux', install_method='cloud_image',
                    media_url='https://cloud.debian.example/debian-12.qcow2', media_sha256=_sha(DEB_IMAGE),
                    media_formats=['qcow2'], osinfo='ubuntu16.04', agent=True, net_config='ifupdown')
    CATALOG['ubuntu-16.04'] = ubuntu
    try:
        result, log = builder(spec=_spec(deb={'os_id': 'ubuntu-16.04'}))
    finally:
        del CATALOG['ubuntu-16.04']

    customize = _commands(log, 'virt-customize')[0]
    assert result.returncode == 0, result.stderr
    # Ubuntu 16.04's /etc/network/interfaces sources only interfaces.d/*.cfg; a bare "agoge" is ignored.
    assert '/etc/network/interfaces.d/agoge.cfg' in customize
    assert '/etc/systemd/network/10-agoge-0.link' in customize
    interfaces = (builder.root / 'var/lib/agoge-nested/work/net-deb/agoge.cfg').read_text()
    assert 'iface agoge0 inet static\n  address 10.10.0.10/24\n  gateway 10.10.0.1\n' in interfaces


def _grow_root_command():
    """The cloud-image firstboot command that grows the root partition and filesystem."""
    rendered = nested_scripts.render_builder()
    return re.search(r"--firstboot-command '(command -v growpart[^']*)'", rendered).group(1)


# (findmnt SOURCE without --nofsroot, FSTYPE, expected resize command). Fedora's btrfs root
# carries a subvolume suffix that lsblk and the partition-number expansion cannot parse.
GROW_CASES = {
    'btrfs': ('/dev/vda4[/root]', 'btrfs', 'btrfs filesystem resize max /'),
    'xfs': ('/dev/vda4', 'xfs', 'xfs_growfs /'),
    'ext4': ('/dev/vda1', 'ext4', 'resize2fs /dev/vda1'),
}


@pytest.mark.skipif(shutil.which('bash') is None, reason='needs bash')
@pytest.mark.parametrize('fstype', GROW_CASES)
def test_firstboot_grows_the_root_filesystem_for_its_fstype(tmp_path, fstype):
    source, fs, expected = GROW_CASES[fstype]
    device = source.split('[')[0]
    log = tmp_path / 'log'
    stubs = {
        # Like util-linux: -v (--nofsroot) drops the [/subvolume] suffix.
        'findmnt': f'case "$1" in -no) [ "$2" = FSTYPE ] && echo {fs} || echo "{source}" ;; '
                   f'-nvo) echo {device} ;; *) exit 1 ;; esac',
        'lsblk': f'[ "$3" = {device} ] && echo vda || exit 1',
    }
    for name in ('growpart', 'resize2fs', 'xfs_growfs', 'btrfs'):
        stubs[name] = f'echo "{name} $*" >> {log}'
    for name, body in stubs.items():
        (tmp_path / name).write_text(f'#!/bin/bash\n{body}\n')
        (tmp_path / name).chmod(0o755)

    result = subprocess.run(['bash', '-c', _grow_root_command()], capture_output=True, text=True,
                            env={'PATH': f'{tmp_path}:/usr/bin:/bin'}, timeout=30)

    assert result.returncode == 0, result.stderr
    assert log.read_text().splitlines() == [f'growpart /dev/vda {device[-1]}', expected]


@needs_tools
def test_post_install_runs_through_guest_exec_with_the_script_as_input(builder):
    result, _ = builder()

    request = json.loads((builder.fake / 'exec-request-deb').read_text())
    assert result.returncode == 0, result.stderr
    assert request['execute'] == 'guest-exec'
    assert request['arguments']['path'] == '/bin/bash' and request['arguments']['arg'] == ['-s']
    assert base64.b64decode(request['arguments']['input-data']).decode() == POST_INSTALL
    assert not (builder.fake / 'exec-request-win').exists()


@needs_tools
def test_failed_post_install_fails_only_that_guest_with_its_stderr(builder):
    stderr = 'E: Unable to locate package nginx' + 'x' * 300
    (builder.fake / 'exec-status-deb').write_text(json.dumps(
        {'return': {'exited': True, 'exitcode': 100, 'err-data': base64.b64encode(stderr.encode()).decode()}}))

    result, _ = builder()

    last, _ = _attributes(builder.fake)
    assert result.returncode == 0, result.stderr
    assert last['guest-deb'] == f'failed:post-install exited 100: {stderr[:150]}'
    assert last['guest-win'] == 'ready'
    assert last['phase'] == 'ready'
    assert last['message'] == 'ready; failed: deb'


@needs_tools
def test_sha256_mismatch_fails_the_guest(builder):
    (builder.fake / 'web' / 'debian-12.qcow2').write_bytes(b'tampered')

    result, log = builder()

    last, _ = _attributes(builder.fake)
    assert result.returncode == 0, result.stderr
    assert last['guest-deb'].startswith(f'failed:media sha256 mismatch: expected {_sha(DEB_IMAGE)}')
    assert not list((builder.root / MEDIA_DIR.lstrip('/')).glob(f'{_sha(DEB_IMAGE)}*'))
    assert '--name deb' not in log
    assert last['phase'] == 'ready'


@needs_tools
def test_phase_is_failed_only_when_no_guest_is_usable(builder):
    for name in ('debian-12.qcow2', 'server2022.iso'):
        (builder.fake / 'web' / name).write_bytes(b'tampered')
    (builder.fake / 'gcs' / 'test-project_nested-media' / 'media' / 'med-1' / 'fw.iso').unlink()

    result, _ = builder()

    last, _ = _attributes(builder.fake)
    assert result.returncode == 0, result.stderr
    assert last['phase'] == 'failed'
    assert last['message'] == 'no guest was built; failed: deb win fw'
    assert last['guest-fw'] == 'failed:could not download the uploaded media'


@needs_tools
def test_a_second_run_resumes_instead_of_rebuilding(builder):
    builder()

    result, log = builder()

    last, _ = _attributes(builder.fake)
    # A heartbeat already in flight when the first run stopped may land late; it is harmless.
    last.pop('heartbeat', None)
    assert result.returncode == 0, result.stderr
    assert last == {'phase': 'ready'}
    assert not _commands(log, 'virt-install') and not _commands(log, 'apt-get')


@needs_tools
def test_a_run_interrupted_mid_build_skips_finished_steps_and_guests(builder):
    state = builder.root / 'var/lib/agoge-nested/state'
    state.mkdir(parents=True)
    for marker in ('packages', 'networks', 'runtime'):
        (state / marker).write_text('')
    (state / 'guest-win.done').write_text('ready\n')
    # deb finished installing before the reboot; only its post-install is left.
    (state / 'installed-deb').write_text('')
    domains = builder.fake / 'domains'
    domains.mkdir()
    (domains / 'deb.state').write_text('shut off\n')

    result, log = builder()

    last, history = _attributes(builder.fake)
    assert result.returncode == 0, result.stderr
    assert not _commands(log, 'apt-get') and 'virsh net-define' not in log
    assert '--name win' not in log and '--name deb' not in log
    assert 'virsh start deb' in log
    assert ['guest-win', 'ready'] in history
    assert last['guest-deb'] == 'ready' and last['phase'] == 'ready'


@needs_tools
def test_an_interrupted_install_is_shut_down_and_redefined(builder):
    domains = builder.fake / 'domains'
    domains.mkdir()
    (domains / 'deb.state').write_text('running\n')

    result, log = builder()

    assert result.returncode == 0, result.stderr
    assert log.index('virsh shutdown deb') < log.index('virsh undefine deb') < log.index('--name deb')


@needs_tools
def test_no_manifest_means_nothing_to_build(builder):
    (builder.fake / 'manifest.json').unlink(missing_ok=True)

    result, log = builder(manifest=False)

    assert result.returncode == 0, result.stderr
    assert 'nothing to build' in result.stdout
    assert not _commands(log, 'apt-get')


@needs_tools
def test_missing_secrets_fail_the_build(builder):
    result, _ = builder(secrets_present=False)

    last, _ = _attributes(builder.fake)
    assert result.returncode == 1
    assert last['phase'] == 'failed'
    assert 'agoge-nested-secrets is missing' in last['message']


@needs_tools
def test_an_unknown_osinfo_falls_back_to_generic(builder):
    result, log = builder(extra_env={'FAKE_BAD_OSINFO': 'debian12'})

    installs = [line for line in _commands(log, 'virt-install') if '--name deb' in line]
    assert result.returncode == 0, result.stderr
    assert '--osinfo debian12' in installs[0] and '--osinfo generic' in installs[1]


@needs_tools
def test_debian_13_parent_uses_libvirts_iptables_backend(builder):
    spec = _spec().model_copy(update={'parent_os': 'debian-13'})

    result, log = builder(spec=spec)

    conf = (builder.root / 'etc/libvirt/network.conf').read_text()
    assert result.returncode == 0, result.stderr
    assert 'firewall_backend = "iptables"' in conf
    assert log.index('systemctl try-restart virtnetworkd.service libvirtd.service') < log.index('virsh net-define')


@needs_tools
def test_a_bz2_disk_image_is_expanded_to_raw_before_conversion(builder):
    (builder.fake / 'web' / 'nano.img.bz2').write_bytes(FW_NANO)

    result, log = builder(spec=_spec(fw={'os_id': 'opnsense', 'media_id': None}))

    last, _ = _attributes(builder.fake)
    work = builder.root / MEDIA_DIR.lstrip('/') / 'work-fw'
    assert result.returncode == 0, result.stderr
    assert f'qemu-img convert -f raw -O qcow2 {work}/disk.img ' in log
    # The expanded copy lives only in scratch; the verified download stays cached for other guests.
    assert not work.exists()
    assert (builder.root / MEDIA_DIR.lstrip('/') / f'{_sha(FW_NANO)}.img.bz2').read_bytes() == FW_NANO
    assert last['guest-fw'] == 'ready'


@needs_tools
def test_a_bz2_disk_image_that_will_not_expand_fails_only_that_guest(builder):
    # The hash matches, so only the expansion can fail (in production: the parent disk filling up).
    corrupt = b'BZh9 not really bzip2'
    (builder.fake / 'web' / 'nano.img.bz2').write_bytes(corrupt)
    catalog = dict(CATALOG, opnsense=CATALOG['opnsense'].model_copy(update={'media_sha256': _sha(corrupt)}))

    with pytest.MonkeyPatch.context() as patch:
        patch.setitem(globals(), 'CATALOG', catalog)
        result, log = builder(spec=_spec(fw={'os_id': 'opnsense', 'media_id': None}))

    last, _ = _attributes(builder.fake)
    assert result.returncode == 0, result.stderr
    assert last['guest-fw'] == 'failed:could not expand the img.bz2 media'
    assert '--name fw' not in log
    assert last['guest-deb'] == 'ready'


def _xz_firewall_catalog(content):
    # The opnsense fixture, re-pointed at an img.xz medium with content's hash.
    entry = CATALOG['opnsense'].model_copy(update={
        'media_url': 'https://pkg.opnsense.example/nano.img.xz', 'media_sha256': _sha(content),
        'media_formats': ['img.xz']})
    return dict(CATALOG, opnsense=entry)


@needs_tools
@pytest.mark.skipif(shutil.which('xz') is None, reason='needs xz')
def test_an_xz_disk_image_is_expanded_to_raw_before_conversion(builder):
    nano = lzma.compress(b'preinstalled firewall disk bytes', format=lzma.FORMAT_XZ)
    (builder.fake / 'web' / 'nano.img.xz').write_bytes(nano)

    with pytest.MonkeyPatch.context() as patch:
        patch.setitem(globals(), 'CATALOG', _xz_firewall_catalog(nano))
        result, log = builder(spec=_spec(fw={'os_id': 'opnsense', 'media_id': None}))

    last, _ = _attributes(builder.fake)
    work = builder.root / MEDIA_DIR.lstrip('/') / 'work-fw'
    assert result.returncode == 0, result.stderr
    assert f'qemu-img convert -f raw -O qcow2 {work}/disk.img ' in log
    assert not work.exists()
    assert last['guest-fw'] == 'ready'


@needs_tools
@pytest.mark.skipif(shutil.which('xz') is None, reason='needs xz')
def test_an_xz_disk_image_that_will_not_expand_fails_only_that_guest(builder):
    # The hash matches, so only the expansion can fail (in production: the parent disk filling up).
    corrupt = b'\xfd7zXZ\x00 not really xz'
    (builder.fake / 'web' / 'nano.img.xz').write_bytes(corrupt)

    with pytest.MonkeyPatch.context() as patch:
        patch.setitem(globals(), 'CATALOG', _xz_firewall_catalog(corrupt))
        result, log = builder(spec=_spec(fw={'os_id': 'opnsense', 'media_id': None}))

    last, _ = _attributes(builder.fake)
    assert result.returncode == 0, result.stderr
    assert last['guest-fw'] == 'failed:could not expand the img.xz media'
    assert '--name fw' not in log
    assert not (builder.root / MEDIA_DIR.lstrip('/') / 'work-fw').exists()
    assert last['guest-deb'] == 'ready'


def _zip_firewall_catalog(content):
    # The opnsense fixture, re-pointed at a zip medium (the Metasploitable 2 shape) with content's hash.
    entry = CATALOG['opnsense'].model_copy(update={
        'media_url': 'https://pkg.opnsense.example/vm.zip', 'media_sha256': _sha(content), 'media_formats': ['zip']})
    return dict(CATALOG, opnsense=entry)


def _zip(tmp_path, members):
    path = tmp_path / 'vm.zip'
    with zipfile.ZipFile(path, 'w') as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return path.read_bytes()


@needs_tools
def test_a_zip_disk_image_converts_its_largest_disk_file(builder, tmp_path):
    # Metasploitable 2 ships a VMware folder: the vmdk next to its vmx and nvram.
    vm = _zip(tmp_path, {'Metasploitable2-Linux/Metasploitable.vmdk': b'KDMV' + b'\0' * 4096,
                         'Metasploitable2-Linux/Metasploitable.vmx': b'scsi0.virtualDev = "lsilogic"\n',
                         'Metasploitable2-Linux/Metasploitable.nvram': b'\0' * 64})
    (builder.fake / 'web' / 'vm.zip').write_bytes(vm)

    with pytest.MonkeyPatch.context() as patch:
        patch.setitem(globals(), 'CATALOG', _zip_firewall_catalog(vm))
        result, log = builder(spec=_spec(fw={'os_id': 'opnsense', 'media_id': None}))

    last, _ = _attributes(builder.fake)
    work = builder.root / MEDIA_DIR.lstrip('/') / 'work-fw'
    assert result.returncode == 0, result.stderr
    # No -f: qemu-img probes the vmdk's own header rather than being told a format.
    assert f'qemu-img convert -O qcow2 {work}/Metasploitable2-Linux/Metasploitable.vmdk ' in log
    assert not work.exists()
    assert last['guest-fw'] == 'ready'


@needs_tools
def test_a_zip_without_a_disk_file_fails_only_that_guest(builder, tmp_path):
    vm = _zip(tmp_path, {'Metasploitable2-Linux/Metasploitable.vmx': b'memsize = "512"\n'})
    (builder.fake / 'web' / 'vm.zip').write_bytes(vm)

    with pytest.MonkeyPatch.context() as patch:
        patch.setitem(globals(), 'CATALOG', _zip_firewall_catalog(vm))
        result, log = builder(spec=_spec(fw={'os_id': 'opnsense', 'media_id': None}))

    last, _ = _attributes(builder.fake)
    assert result.returncode == 0, result.stderr
    assert last['guest-fw'] == 'failed:no disk image found in the zip media'
    assert '--name fw' not in log
    assert not (builder.root / MEDIA_DIR.lstrip('/') / 'work-fw').exists()
    assert last['guest-deb'] == 'ready'


def _gz_firewall_catalog(content):
    # The pfsense fixture, re-pointed at a downloaded iso.gz medium (pfSense CE's format) with content's hash.
    entry = CATALOG['pfsense'].model_copy(update={
        'media_url': 'https://pfsense.example/fw.iso.gz', 'media_sha256': _sha(content), 'requires_upload': False,
        'media_formats': ['iso.gz', 'iso']})
    return dict(CATALOG, pfsense=entry)


@needs_tools
@pytest.mark.skipif(shutil.which('gzip') is None, reason='needs gzip')
def test_an_iso_gz_is_expanded_once_and_only_the_iso_is_kept(builder):
    packed = gzip.compress(FW_ISO)
    (builder.fake / 'web' / 'fw.iso.gz').write_bytes(packed)

    with pytest.MonkeyPatch.context() as patch:
        patch.setitem(globals(), 'CATALOG', _gz_firewall_catalog(packed))
        result, log = builder(spec=_spec(fw={'media_id': None}))

    last, _ = _attributes(builder.fake)
    media_dir = builder.root / MEDIA_DIR.lstrip('/')
    iso = media_dir / f'{_sha(packed)}.iso'
    assert result.returncode == 0, result.stderr
    assert iso.read_bytes() == FW_ISO
    # The parent disk keeps only the ISO; the cache holds the download, whose hash is the catalog's.
    assert not (media_dir / f'{_sha(packed)}.iso.gz').exists()
    assert f"name=cache%2F{_sha(packed)}" in (builder.fake / 'uploads').read_text()
    fw = [line for line in _commands(log, 'virt-install') if '--name fw' in line]
    assert len(fw) == 1 and f'path={iso},device=cdrom' in fw[0]
    assert last['guest-fw'] == 'manual'


@needs_tools
@pytest.mark.skipif(shutil.which('gzip') is None, reason='needs gzip')
def test_an_iso_gz_that_will_not_expand_fails_only_that_guest(builder):
    # The hash matches, so only the expansion can fail (in production: the parent disk filling up).
    corrupt = b'\x1f\x8b not really gzip'
    (builder.fake / 'web' / 'fw.iso.gz').write_bytes(corrupt)

    with pytest.MonkeyPatch.context() as patch:
        patch.setitem(globals(), 'CATALOG', _gz_firewall_catalog(corrupt))
        result, log = builder(spec=_spec(fw={'media_id': None}))

    last, _ = _attributes(builder.fake)
    media_dir = builder.root / MEDIA_DIR.lstrip('/')
    assert result.returncode == 0, result.stderr
    assert last['guest-fw'] == 'failed:could not expand the iso.gz media'
    assert '--name fw' not in log
    # Nothing half-expanded is left for the next run to mistake for a cached ISO.
    assert not list(media_dir.glob(f'{_sha(corrupt)}.iso*'))
    assert last['guest-deb'] == 'ready'

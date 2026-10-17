"""Render what a nested lab host's builder reads: the manifest, the secrets, and Windows unattend files.

The manifest (`agoge-nested-manifest`) is persistent template-server metadata, so it must never
carry a password or a product key; those travel only in `agoge-nested-secrets`, which the build
monitor removes once the build ends. See the Nested Image Builder Contract in PRD.md.
"""
import hashlib
import ipaddress
import json
from pathlib import Path
from string import Template
from typing import Dict, Iterable, List, Optional
from xml.sax.saxutils import escape

from common.constants.nested import NESTED_METADATA_MAX_BYTES
from common.exceptions.agoge import BadRequest
from common.models.agoge import (NestedGuestModel, NestedHostSpecModel, NestedMediaModel, NestedNetworkModel,
                                 NestedOsCatalogModel)

MANIFEST_VERSION = 1
TEMPLATE_RELATIVE_PATH = Path('cloud_fn_utilities', 'server_specific', 'nested', 'autounattend.xml.tmpl')
# Windows 11 and Server 2025 install under BIOS (Design Decisions), so Setup's TPM, Secure Boot,
# and RAM checks have to be bypassed.
LABCONFIG_OSINFO = frozenset({'win11', 'win2k25'})
LABCONFIG_CHECKS = ('BypassTPMCheck', 'BypassSecureBootCheck', 'BypassRAMCheck')
# virtio-win ISO driver directory per libosinfo id.
VIRTIO_OS_DIRECTORIES = {
    'win7': 'w7', 'win8': 'w8', 'win8.1': 'w8.1', 'win10': 'w10', 'win11': 'w11',
    'win2k8': '2k8', 'win2k8r2': '2k8R2', 'win2k12': '2k12', 'win2k12r2': '2k12R2',
    'win2k16': '2k16', 'win2k19': '2k19', 'win2k22': '2k22', 'win2k25': '2k25',
}
VIRTIO_DRIVERS = ('viostor', 'vioscsi', 'NetKVM', 'vioserial', 'Balloon')
# The OS, virtio-win, and unattend ISOs get CD-ROM letters in an order Setup does not promise.
CDROM_LETTERS = ('D', 'E', 'F', 'G')
PANTHER_UNATTEND_GLOBS = (r'C:\Windows\Panther\unattend*.xml', r'C:\Windows\Panther\Unattend\unattend*.xml')
WINLOGON_KEY = r'HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon'


def guest_mac(guest_name: str, nic_index: int) -> str:
    """A stable MAC in QEMU's 52:54:00 range, so unattend can find a NIC the builder has not created yet."""
    digest = hashlib.sha256(f'{guest_name}/{nic_index}'.encode()).hexdigest()
    return '52:54:00:' + ':'.join(digest[i:i + 2] for i in range(0, 6, 2))


def render_manifest(spec: NestedHostSpecModel, catalog: Dict[str, NestedOsCatalogModel],
                    media: Dict[str, NestedMediaModel]) -> str:
    """Return the `agoge-nested-manifest` JSON.

    :param spec: the derived host spec (exposures and console ports filled in).
    :param catalog: catalog entries by entry id; every guest's os_id must be present.
    :param media: uploaded media by id; every guest's media_id must be present.
    """
    guests = []
    macs: Dict[str, str] = {}
    for guest in spec.guests:
        entry = catalog.get(guest.os_id)
        if entry is None:
            raise ValueError(f"guest {guest.name}: no catalog entry {guest.os_id}")
        record = guest.model_dump(exclude={'admin_password'})
        for index, nic in enumerate(record['nics']):
            nic['mac'] = guest_mac(guest.name, index)
            if nic['mac'] in macs:
                raise BadRequest(f"guests {macs[nic['mac']]} and {guest.name} derive the same MAC address; "
                                 f"rename one of them")
            macs[nic['mac']] = guest.name
        record['catalog'] = entry.model_dump()
        record['media'] = _media_source(guest, entry, media)
        guests.append(record)
    manifest = {
        'version': MANIFEST_VERSION,
        **spec.model_dump(exclude={'guests', 'vnc_passwords'}),
        'guests': guests,
    }
    return _bounded_json(manifest, 'agoge-nested-manifest', "shorten the guests' post-install scripts")


def build_secrets(spec: NestedHostSpecModel, product_keys: Optional[Dict[str, str]] = None) -> Dict[str, Dict[str, str]]:
    """Return {guest: {admin_password, vnc_password?, product_key?}} for the guests in spec."""
    product_keys = product_keys or {}
    secrets = {}
    for guest in spec.guests:
        values = {'admin_password': guest.admin_password}
        if guest.name in spec.vnc_passwords:
            values['vnc_password'] = spec.vnc_passwords[guest.name]
        if product_keys.get(guest.name):
            values['product_key'] = product_keys[guest.name]
        secrets[guest.name] = values
    return secrets


def render_secrets(spec: NestedHostSpecModel, product_keys: Optional[Dict[str, str]] = None,
                   catalog: Optional[Dict[str, NestedOsCatalogModel]] = None) -> str:
    """Return the `agoge-nested-secrets` JSON.

    :param catalog: catalog entries by entry id. When given, each unattended Windows guest also gets
        its rendered `autounattend` XML, which holds its password and so cannot go in the manifest.
    """
    secrets = build_secrets(spec, product_keys)
    if catalog is not None:
        for guest in spec.guests:
            entry = catalog.get(guest.os_id)
            if entry is None:
                raise ValueError(f"guest {guest.name}: no catalog entry {guest.os_id}")
            if entry.install_method == 'unattended_iso' and entry.family == 'windows':
                secrets[guest.name]['autounattend'] = render_autounattend(guest, entry, secrets, spec.networks)
    return _bounded_json(secrets, 'agoge-nested-secrets', "use fewer guests")


def render_autounattend(guest: NestedGuestModel, entry: NestedOsCatalogModel, secrets: Dict[str, Dict[str, str]],
                        networks: Iterable[NestedNetworkModel] = (), template: Optional[str] = None) -> str:
    """Return the guest's autounattend.xml.

    :param secrets: the build_secrets map; the guest's admin password and product key come from it.
    :param networks: the spec's networks, used to configure the guest's static IPs.
    :param template: the template text; defaults to autounattend.xml.tmpl.
    """
    if entry.install_method != 'unattended_iso' or entry.family != 'windows':
        raise ValueError(f"guest {guest.name}: {entry.id} is not an unattended Windows install")
    if entry.windows_image_index is None:
        raise ValueError(f"catalog entry {entry.id} has no windows_image_index")
    guest_secrets = secrets[guest.name]
    uefi = entry.firmware == 'uefi'
    values = {
        'driver_paths': _driver_paths(entry),
        'lab_config': _lab_config(entry),
        'partitions': _partitions(uefi),
        'install_partition': '3' if uefi else '1',
        'image_index': str(entry.windows_image_index),
        'admin_username': escape(guest.admin_username),
        'admin_password': escape(guest_secrets['admin_password']),
        'product_key': _product_key(guest_secrets.get('product_key')),
        'computer_name': escape(guest.name.upper()),
        'local_account': _local_account(guest.admin_username, guest_secrets['admin_password']),
        'first_logon_commands': _first_logon_commands(guest, entry, {network.name: network for network in networks}),
    }
    return Template(template if template is not None else load_autounattend_template()).substitute(values)


def load_autounattend_template() -> str:
    # In the repo the template is under cloud_functions/; in the deployed function, common/ sits
    # beside cloud_fn_utilities/ (the .staging layout), so try both.
    root = Path(__file__).resolve().parents[2]
    for base in (root, root / 'cloud_functions'):
        path = base / TEMPLATE_RELATIVE_PATH
        if path.is_file():
            return path.read_text()
    raise FileNotFoundError(f"autounattend template {TEMPLATE_RELATIVE_PATH} not found under {root}")


def _media_source(guest: NestedGuestModel, entry: NestedOsCatalogModel,
                  media: Dict[str, NestedMediaModel]) -> Dict[str, Optional[str]]:
    if guest.media_id:
        medium = media.get(guest.media_id)
        if medium is None:
            raise ValueError(f"guest {guest.name}: no medium {guest.media_id}")
        return {'source': 'gcs', 'media_id': medium.id, 'gcs_path': medium.gcs_path,
                'sha256': medium.sha256, 'format': medium.format}
    if entry.requires_upload or not entry.media_url:
        raise ValueError(f"guest {guest.name}: {entry.id} requires an uploaded medium")
    return {'source': 'url', 'url': entry.media_url, 'sha256': entry.media_sha256, 'format': entry.media_formats[0]}


def _bounded_json(document: dict, key: str, remedy: str) -> str:
    rendered = json.dumps(document, separators=(',', ':'), sort_keys=True)
    size = len(rendered.encode())
    if size > NESTED_METADATA_MAX_BYTES:
        raise BadRequest(f"{key} is {size} bytes, over the {NESTED_METADATA_MAX_BYTES}-byte metadata limit; {remedy}")
    return rendered


def _driver_paths(entry: NestedOsCatalogModel) -> str:
    if not entry.virtio_win_version:
        return ''
    os_directory = VIRTIO_OS_DIRECTORIES.get(entry.osinfo)
    if os_directory is None:
        raise ValueError(f"catalog entry {entry.id}: no virtio-win driver directory for osinfo {entry.osinfo}")
    paths = []
    for key, (letter, driver) in enumerate(((letter, driver) for letter in CDROM_LETTERS for driver in VIRTIO_DRIVERS),
                                           start=1):
        paths.append(
            f'          <PathAndCredentials wcm:action="add" wcm:keyValue="{key}">\n'
            f'            <Path>{letter}:\\{driver}\\{os_directory}\\amd64</Path>\n'
            f'          </PathAndCredentials>'
        )
    return (
        '    <component name="Microsoft-Windows-PnpCustomizationsWinPE" processorArchitecture="amd64" '
        'publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS">\n'
        '      <DriverPaths>\n' + '\n'.join(paths) + '\n      </DriverPaths>\n'
        '    </component>'
    )


def _lab_config(entry: NestedOsCatalogModel) -> str:
    if entry.osinfo not in LABCONFIG_OSINFO:
        return ''
    commands = []
    for order, check in enumerate(LABCONFIG_CHECKS, start=1):
        commands.append(
            '        <RunSynchronousCommand wcm:action="add">\n'
            f'          <Order>{order}</Order>\n'
            f'          <Path>reg add HKLM\\SYSTEM\\Setup\\LabConfig /v {check} /t REG_DWORD /d 1 /f</Path>\n'
            '        </RunSynchronousCommand>'
        )
    return '      <RunSynchronous>\n' + '\n'.join(commands) + '\n      </RunSynchronous>'


def _partitions(uefi: bool) -> str:
    if uefi:
        created = [('EFI', '100'), ('MSR', '16'), ('Primary', None)]
        modified = [(1, 'FAT32', 'System', None), (3, 'NTFS', 'Windows', 'C')]
    else:
        created = [('Primary', None)]
        modified = [(1, 'NTFS', 'Windows', 'C')]
    create_xml = []
    for order, (kind, size) in enumerate(created, start=1):
        extent = f'<Size>{size}</Size>' if size else '<Extend>true</Extend>'
        create_xml.append(f'            <CreatePartition wcm:action="add"><Order>{order}</Order>'
                          f'<Type>{kind}</Type>{extent}</CreatePartition>')
    modify_xml = []
    for order, (partition, file_system, label, letter) in enumerate(modified, start=1):
        extras = f'<Letter>{letter}</Letter>' if letter else ''
        if not uefi:
            extras += '<Active>true</Active>'
        modify_xml.append(f'            <ModifyPartition wcm:action="add"><Order>{order}</Order>'
                          f'<PartitionID>{partition}</PartitionID><Format>{file_system}</Format>'
                          f'<Label>{label}</Label>{extras}</ModifyPartition>')
    return ('          <CreatePartitions>\n' + '\n'.join(create_xml) + '\n          </CreatePartitions>\n'
            '          <ModifyPartitions>\n' + '\n'.join(modify_xml) + '\n          </ModifyPartitions>')


def _product_key(key: Optional[str]) -> str:
    if not key:
        return ''
    return (f'        <ProductKey>\n          <Key>{escape(key)}</Key>\n'
            '          <WillShowUI>OnError</WillShowUI>\n        </ProductKey>')


def _local_account(username: str, password: str) -> str:
    # The built-in Administrator already exists and gets its password from AdministratorPassword.
    if username.lower() == 'administrator':
        return ''
    return (
        '        <LocalAccounts>\n'
        '          <LocalAccount wcm:action="add">\n'
        f'            <Name>{escape(username)}</Name>\n'
        f'            <DisplayName>{escape(username)}</DisplayName>\n'
        '            <Group>Administrators</Group>\n'
        f'            <Password><Value>{escape(password)}</Value><PlainText>true</PlainText></Password>\n'
        '          </LocalAccount>\n'
        '        </LocalAccounts>'
    )


def _first_logon_commands(guest: NestedGuestModel, entry: NestedOsCatalogModel,
                          networks: Dict[str, NestedNetworkModel]) -> str:
    commands: List[str] = []
    if entry.virtio_win_version:
        for installer in (r'virtio-win-gt-x64.msi', r'guest-agent\qemu-ga-x86_64.msi'):
            commands.append(f'cmd /c for %d in ({" ".join(CDROM_LETTERS)}) do '
                            # msiexec is a GUI binary: without start /wait, cmd returns before it installs.
                            f'if exist %d:\\{installer} start "" /wait msiexec /i %d:\\{installer} /qn /norestart')
    commands += [
        r'reg add "HKLM\SYSTEM\CurrentControlSet\Control\Terminal Server" /v fDenyTSConnections /t REG_DWORD /d 0 /f',
        r'netsh advfirewall firewall set rule group="remote desktop" new enable=Yes',
        r'netsh advfirewall firewall add rule name="Agoge ICMPv4" protocol=icmpv4:8,any dir=in action=allow',
    ]
    for index, nic in enumerate(guest.nics):
        if nic.ip:
            if nic.network not in networks:
                raise ValueError(f"guest {guest.name}: static NIC {index} names unknown network {nic.network}")
            commands.append(_static_ip_command(guest_mac(guest.name, index), nic.ip, networks[nic.network]))
    # AutoLogon leaves the password in Winlogon's DefaultPassword; Setup leaves it in Panther.
    commands += [
        f'reg add "{WINLOGON_KEY}" /v AutoAdminLogon /t REG_SZ /d 0 /f',
        f'reg delete "{WINLOGON_KEY}" /v DefaultPassword /f',
        *(f'cmd /c del /f /q {pattern}' for pattern in PANTHER_UNATTEND_GLOBS),
        # The builder waits for the domain to reach shut off (Working Note 17), then detaches the media.
        'shutdown /s /t 0 /f',
    ]
    return '\n'.join(
        '        <SynchronousCommand wcm:action="add">\n'
        f'          <Order>{order}</Order>\n'
        f'          <CommandLine>{escape(command)}</CommandLine>\n'
        '        </SynchronousCommand>'
        for order, command in enumerate(commands, start=1)
    )


def _static_ip_command(mac: str, ip: str, network: NestedNetworkModel) -> str:
    """PowerShell that waits for the NIC with this MAC, then sets its address (Windows 7 and later)."""
    cidr = ipaddress.ip_network(network.cidr)
    steps = [
        f"$m = '{mac.upper()}'",
        "$c = $null",
        "for ($i = 0; $i -lt 60 -and -not $c; $i++) { "
        "$c = Get-WmiObject Win32_NetworkAdapterConfiguration | Where-Object { $_.MACAddress -eq $m }; "
        "if (-not $c) { Start-Sleep -Seconds 2 } }",
        f"$c.EnableStatic(@('{ip}'), @('{cidr.netmask}')) | Out-Null",
    ]
    # Only a nat network routes beyond itself; the parent's dnsmasq answers DNS on any network it is on.
    if network.mode == 'nat' and network.parent_address:
        steps.append(f"$c.SetGateways(@('{network.parent_address}'), @(1)) | Out-Null")
    if network.parent_address:
        steps.append(f"$c.SetDNSServerSearchOrder(@('{network.parent_address}')) | Out-Null")
    return 'powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "' + '; '.join(steps) + '"'

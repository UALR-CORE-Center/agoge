"""Validation and derivation for a nested image create request (Nested Image Builder Contract)."""
import ipaddress
import math
import re
import secrets
import string
from typing import Dict, List, NamedTuple, Optional, Tuple

from common.constants.database import DatabaseTypes, DbCollections, DATABASE_NAME
from common.constants.nested import (
    NESTED_BUILD_SCRATCH_GB,
    NESTED_CONSOLE_BASE_PORT,
    NESTED_MACHINE_TYPES,
    NESTED_MAX_DISK_GB,
    NESTED_MAX_EXPOSURES,
    NESTED_MEDIA_MAX_BYTES,
    NESTED_PARENT_BASE_DISK_GB,
    NESTED_PARENT_OVERHEAD_MB,
)
from common.document_database.factory import DocumentDatabaseFactory
from common.exceptions import BadRequest
from common.models.agoge import (
    NestedGuestModel,
    NestedHostSpecModel,
    NestedImageCreateRequest,
    NestedMediaModel,
    NestedNetworkModel,
    NestedOsCatalogModel,
)
from common.models.google import MachineTypeModel
from common.models.model_validators.model_validator import ModelValidator
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import LoggerNames
from common.utilities.gcp.compute.compute_machine_type import ComputeMachineTypesAPI

from core.compute.image import ComputeImage

RFC1918 = tuple(ipaddress.ip_network(net) for net in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'))
# Link-local carries the metadata server; 192.168.122.0/24 is libvirt's default network on the parent.
RESERVED_NETWORKS = tuple(ipaddress.ip_network(net) for net in ('169.254.0.0/16', '192.168.122.0/24'))
MIN_PREFIX, MAX_PREFIX = 16, 29
PRODUCT_KEY = re.compile(r'^([A-Z0-9]{5}-){4}[A-Z0-9]{5}$')
PACKAGE_NAME = re.compile(r'^[a-z0-9][a-z0-9+.-]{0,63}$')
MIN_PASSWORD_LENGTH = 8
# VNC authentication only uses the first eight characters of a password.
VNC_PASSWORD_LENGTH = 8
VNC_PASSWORD_ALPHABET = string.ascii_letters + string.digits
GIB = 1024 ** 3


class NestedValidation(NamedTuple):
    entries: Dict[str, NestedOsCatalogModel]
    """Each guest's catalog entry by guest name."""
    disk_size: int
    """The parent disk in GB: the request's disk_size, or the computed minimum when it was left empty."""


class NestedHostValidator:
    """Rejects a nested image request with a BadRequest naming the network, guest, or field."""

    def __init__(self, env_dict: dict = None, db=None, machine_type_api=None) -> None:
        self.class_name = self.__class__.__name__
        self.log_name = LoggerNames.API
        self.env = CloudEnv(log_name=self.log_name, env_dict=env_dict)
        self.db = db or DocumentDatabaseFactory.create_db_object(
            DatabaseTypes.firestore,
            database_name=DATABASE_NAME,
            log_name=self.log_name
        )
        self.machine_type_api = machine_type_api or ComputeMachineTypesAPI(
            self.env.project, self.env.region, self.env.zone, log_name=self.log_name
        )
        self.catalog_validator = ModelValidator(model=NestedOsCatalogModel)
        self.media_validator = ModelValidator(model=NestedMediaModel)

    def validate(self, request: NestedImageCreateRequest) -> NestedValidation:
        """Raise BadRequest on the first broken rule; return the guests' catalog entries and the parent disk size."""
        spec = request.nested
        self._validate_server_name(request.server_name)
        networks = self._validate_networks(spec.networks)
        entries, media = self._validate_guests(spec.guests)
        self._validate_nics(spec.guests, spec.networks, networks)
        self._validate_credentials(spec.guests, entries, request.product_keys)
        for field, name in (('machine_type', request.machine_type), ('build_machine_type', spec.build_machine_type)):
            self._validate_capacity(field, self._machine_type(field, name), spec.guests)
        minimum = self.min_disk_size(spec.guests, self.media_sizes(spec.guests, entries, media))
        return NestedValidation(entries=entries, disk_size=self._validate_disk_size(request.disk_size, minimum))

    @staticmethod
    def min_disk_size(guests: List[NestedGuestModel], media_sizes: Dict[str, int]) -> int:
        """The parent boot disk the guests need, in GB; used when the request leaves disk_size empty.

        The builder keeps every medium in MEDIA_DIR on the parent disk until finalize, so each one is reserved
        on top of the scratch space that archive extraction and conversion use. media_sizes is media_sizes().
        """
        media_gb = sum(math.ceil(size / GIB) for size in media_sizes.values())
        return (NESTED_PARENT_BASE_DISK_GB + sum(guest.disk_gb for guest in guests) + NESTED_BUILD_SCRATCH_GB
                + media_gb)

    @staticmethod
    def media_sizes(guests: List[NestedGuestModel], entries: Dict[str, NestedOsCatalogModel],
                    media: Dict[str, NestedMediaModel]) -> Dict[str, int]:
        """Bytes of each distinct medium the build downloads, keyed the way builder.sh fetch_media caches it.

        Guests sharing a medium share one cached file, so it is counted once. A size the API cannot know
        (a catalog entry synced before media_size_bytes, or an upload record that is gone) reserves the
        upload limit rather than nothing.
        """
        sizes: Dict[str, int] = {}
        for guest in guests:
            # nested_manifest._media_source: a guest's media_id wins over the entry's media_url.
            if guest.media_id:
                medium = media.get(guest.media_id)
                key = (medium.sha256 if medium else None) or f'upload-{guest.media_id}'
                sizes[key] = medium.size_bytes if medium else NESTED_MEDIA_MAX_BYTES
            else:
                entry = entries[guest.name]
                sizes[entry.media_sha256 or entry.id] = entry.media_size_bytes or NESTED_MEDIA_MAX_BYTES
        return sizes

    @staticmethod
    def derive(spec: NestedHostSpecModel) -> NestedHostSpecModel:
        """Return a copy of spec with exposures, console ports, and fresh VNC passwords filled in.

        Alias slots and ports follow guest order, then NIC order, so the same spec always
        maps to the same slots; only the passwords differ between calls.
        """
        exposures = [
            (guest.name, index)
            for guest in spec.guests
            for index, nic in enumerate(guest.nics)
            if nic.expose
        ]
        console_guests = [guest.name for guest in spec.guests if guest.console]
        console_ports = {name: NESTED_CONSOLE_BASE_PORT + slot for slot, name in enumerate(console_guests)}
        vnc_passwords = {
            name: ''.join(secrets.choice(VNC_PASSWORD_ALPHABET) for _ in range(VNC_PASSWORD_LENGTH))
            for name in console_guests
        }
        return spec.model_copy(
            update={'exposures': exposures, 'console_ports': console_ports, 'vnc_passwords': vnc_passwords},
            deep=True
        )

    @staticmethod
    def _validate_server_name(server_name: str) -> None:
        ComputeImage._validate_new_name(server_name)
        # /compute/images/nested/ is a route prefix, so an image by that name could never be addressed.
        if server_name == 'nested':
            raise BadRequest('The server name nested is reserved. Choose a different server name.')

    def _validate_networks(self, networks: List[NestedNetworkModel]) -> Dict[str, ipaddress.IPv4Network]:
        parsed: Dict[str, ipaddress.IPv4Network] = {}
        for network in networks:
            name = network.name
            if name in parsed:
                raise BadRequest(f'Network {name}: the name is used by more than one network.')
            cidr = self._parse_cidr(network)
            for reserved in RESERVED_NETWORKS:
                if cidr.overlaps(reserved):
                    raise BadRequest(f'Network {name}: {cidr} overlaps the reserved range {reserved}.')
            for other_name, other in parsed.items():
                if cidr.overlaps(other):
                    raise BadRequest(f'Network {name}: {cidr} overlaps network {other_name} ({other}).')
            self._validate_network_addresses(network, cidr)
            parsed[name] = cidr
        return parsed

    @staticmethod
    def _parse_cidr(network: NestedNetworkModel) -> ipaddress.IPv4Network:
        try:
            cidr = ipaddress.ip_network(network.cidr, strict=True)
        except ValueError:
            raise BadRequest(f'Network {network.name}: {network.cidr} is not a network address in CIDR form.')
        if not isinstance(cidr, ipaddress.IPv4Network) or not any(cidr.subnet_of(net) for net in RFC1918):
            raise BadRequest(f'Network {network.name}: {network.cidr} is not an RFC 1918 private range.')
        if not MIN_PREFIX <= cidr.prefixlen <= MAX_PREFIX:
            raise BadRequest(f'Network {network.name}: the prefix must be /{MIN_PREFIX} to /{MAX_PREFIX}.')
        return cidr

    def _validate_network_addresses(self, network: NestedNetworkModel, cidr: ipaddress.IPv4Network) -> None:
        name = network.name
        addresses = {}
        for field in ('parent_address', 'dhcp_start', 'dhcp_end'):
            value = getattr(network, field)
            if value is not None:
                addresses[field] = self._host_address(cidr, value, f'Network {name}: {field}')
        if network.mode == 'nat' and 'parent_address' not in addresses:
            raise BadRequest(f'Network {name}: nat mode requires parent_address.')
        if network.dhcp:
            if 'parent_address' not in addresses:
                raise BadRequest(f'Network {name}: DHCP requires parent_address, which serves it.')
            # Without an explicit range the static-IP checks below would have nothing to test against.
            if 'dhcp_start' not in addresses or 'dhcp_end' not in addresses:
                raise BadRequest(f'Network {name}: DHCP requires dhcp_start and dhcp_end.')
            if addresses['dhcp_start'] > addresses['dhcp_end']:
                raise BadRequest(f'Network {name}: dhcp_start must not be after dhcp_end.')
            if addresses['dhcp_start'] <= addresses['parent_address'] <= addresses['dhcp_end']:
                raise BadRequest(f'Network {name}: the DHCP range must exclude parent_address.')

    @staticmethod
    def _host_address(cidr: ipaddress.IPv4Network, value: str, label: str) -> ipaddress.IPv4Address:
        try:
            address = ipaddress.ip_address(value)
        except ValueError:
            raise BadRequest(f'{label} {value} is not an IP address.')
        if address not in cidr:
            raise BadRequest(f'{label} {value} is outside {cidr}.')
        if address in (cidr.network_address, cidr.broadcast_address):
            raise BadRequest(f'{label} {value} is the network or broadcast address of {cidr}.')
        return address

    def _validate_guests(self, guests: List[NestedGuestModel]
                         ) -> Tuple[Dict[str, NestedOsCatalogModel], Dict[str, NestedMediaModel]]:
        """Return each guest's catalog entry by guest name, and every named upload by media_id."""
        entries: Dict[str, NestedOsCatalogModel] = {}
        media: Dict[str, NestedMediaModel] = {}
        for guest in guests:
            name = guest.name
            if name in entries:
                raise BadRequest(f'Guest {name}: the name is used by more than one guest.')
            entry = self._catalog_entry(guest)
            if entry.requires_upload:
                media[guest.media_id] = self._validate_media(guest, entry)
            elif guest.media_id and guest.media_id not in media:
                # The manifest uses an upload even for a downloadable entry; it is loaded here only for its size.
                medium = self._load_media(guest.media_id)
                if medium:
                    media[guest.media_id] = medium
            if guest.memory_mb < entry.min_memory_mb:
                raise BadRequest(f'Guest {name}: memory_mb must be at least {entry.min_memory_mb} for {entry.display_name}.')
            if guest.disk_gb < entry.min_disk_gb:
                raise BadRequest(f'Guest {name}: disk_gb must be at least {entry.min_disk_gb} for {entry.display_name}.')
            if guest.packages and not (entry.install_method == 'cloud_image' and entry.family == 'linux'):
                raise BadRequest(f'Guest {name}: packages are only supported for Linux cloud images.')
            for package in guest.packages:
                if not PACKAGE_NAME.fullmatch(package):
                    raise BadRequest(f'Guest {name}: {package!r} is not a valid package name.')
            entries[name] = entry
        return entries, media

    def _catalog_entry(self, guest: NestedGuestModel) -> NestedOsCatalogModel:
        record = self.db.get(collection_name=DbCollections.NESTED_OS_CATALOG, doc_id=guest.os_id)
        entry = self.catalog_validator.load(record, halt_on_error=False) if record else None
        if not entry or not entry.is_enabled:
            raise BadRequest(f'Guest {guest.name}: os_id {guest.os_id} is not an enabled catalog entry.')
        return entry

    def _load_media(self, media_id: str) -> Optional[NestedMediaModel]:
        record = self.db.get(collection_name=DbCollections.NESTED_MEDIA, doc_id=media_id)
        return self.media_validator.load(record, halt_on_error=False) if record else None

    def _validate_media(self, guest: NestedGuestModel, entry: NestedOsCatalogModel) -> NestedMediaModel:
        if not guest.media_id:
            raise BadRequest(f'Guest {guest.name}: {entry.display_name} requires uploaded media (media_id).')
        media = self._load_media(guest.media_id)
        if not media or not media.complete:
            raise BadRequest(f'Guest {guest.name}: media {guest.media_id} is not a completed upload.')
        if media.format not in entry.media_formats:
            raise BadRequest(f'Guest {guest.name}: media format {media.format} is not accepted for '
                             f'{entry.display_name} ({", ".join(entry.media_formats)}).')
        return media

    def _validate_nics(self, guests: List[NestedGuestModel], networks: List[NestedNetworkModel],
                       cidrs: Dict[str, ipaddress.IPv4Network]) -> None:
        by_name = {network.name: network for network in networks}
        static_ips: Dict[ipaddress.IPv4Address, str] = {}
        exposed = 0
        for guest in guests:
            for nic in guest.nics:
                network = by_name.get(nic.network)
                if network is None:
                    raise BadRequest(f'Guest {guest.name}: network {nic.network} does not exist.')
                if nic.expose:
                    exposed += 1
                    if nic.ip is None:
                        raise BadRequest(f'Guest {guest.name}: an exposed NIC needs a static ip.')
                    if exposed > NESTED_MAX_EXPOSURES:
                        raise BadRequest(f'Guest {guest.name}: at most {NESTED_MAX_EXPOSURES} NICs may be exposed.')
                if nic.ip is None:
                    continue
                address = self._host_address(cidrs[nic.network], nic.ip, f'Guest {guest.name}: ip')
                if address in static_ips:
                    raise BadRequest(f'Guest {guest.name}: ip {nic.ip} is already used by guest {static_ips[address]}.')
                if network.parent_address and address == ipaddress.ip_address(network.parent_address):
                    raise BadRequest(f'Guest {guest.name}: ip {nic.ip} is the parent_address of network {network.name}.')
                if network.dhcp and (ipaddress.ip_address(network.dhcp_start) <= address
                                     <= ipaddress.ip_address(network.dhcp_end)):
                    raise BadRequest(f'Guest {guest.name}: ip {nic.ip} is inside the DHCP range of network {network.name}.')
                static_ips[address] = guest.name

    def _validate_credentials(self, guests: List[NestedGuestModel], entries: Dict[str, NestedOsCatalogModel],
                              product_keys: Dict[str, str]) -> None:
        for guest_name in product_keys:
            if guest_name not in entries:
                raise BadRequest(f'Guest {guest_name}: a product key was given for a guest that does not exist.')
        for guest in guests:
            entry = entries[guest.name]
            windows = entry.family == 'windows'
            if windows and entry.install_method == 'unattended_iso' and entry.eval_days is None:
                if not PRODUCT_KEY.fullmatch(product_keys.get(guest.name) or ''):
                    raise BadRequest(f'Guest {guest.name}: {entry.display_name} requires a product key '
                                     f'in the form XXXXX-XXXXX-XXXXX-XXXXX-XXXXX.')
            if windows and not self._meets_windows_complexity(guest.admin_password):
                raise BadRequest(f'Guest {guest.name}: admin_password needs at least {MIN_PASSWORD_LENGTH} '
                                 f'characters from three of: uppercase, lowercase, digits, symbols.')
            if len(guest.admin_password) < MIN_PASSWORD_LENGTH:
                raise BadRequest(f'Guest {guest.name}: admin_password needs at least {MIN_PASSWORD_LENGTH} characters.')

    @staticmethod
    def _meets_windows_complexity(password: str) -> bool:
        classes = (
            any(c.isupper() for c in password),
            any(c.islower() for c in password),
            any(c.isdigit() for c in password),
            any(not c.isalnum() for c in password),
        )
        return len(password) >= MIN_PASSWORD_LENGTH and sum(classes) >= 3

    def _machine_type(self, field: str, name: str) -> MachineTypeModel:
        if name not in NESTED_MACHINE_TYPES:
            raise BadRequest(
                f'{field}: {name} is not offered for nested images; choose one of {", ".join(NESTED_MACHINE_TYPES)}.'
            )
        machine_type: Optional[MachineTypeModel] = self.machine_type_api.get(name)
        if not machine_type:
            raise BadRequest(f'{field}: {name} is not an available machine type.')
        return machine_type

    @staticmethod
    def _validate_capacity(field: str, machine_type: MachineTypeModel, guests: List[NestedGuestModel]) -> None:
        memory = sum(guest.memory_mb for guest in guests) + NESTED_PARENT_OVERHEAD_MB
        if memory > machine_type.memory_mb:
            raise BadRequest(f'{field}: {machine_type.name} has {machine_type.memory_mb} MB, but the guests '
                             f'plus {NESTED_PARENT_OVERHEAD_MB} MB parent overhead need {memory} MB.')
        vcpus = sum(guest.vcpus for guest in guests)
        if vcpus > 2 * machine_type.guest_cpus:
            raise BadRequest(f'{field}: {machine_type.name} allows at most {2 * machine_type.guest_cpus} '
                             f'guest vCPUs; the guests ask for {vcpus}.')

    @staticmethod
    def _validate_disk_size(disk_size: Optional[int], minimum: int) -> int:
        size = minimum if disk_size is None else disk_size
        if size < minimum:
            raise BadRequest(f'disk_size: {disk_size} GB is below the {minimum} GB the guests and their media need.')
        if size > NESTED_MAX_DISK_GB:
            raise BadRequest(f'disk_size: {size} GB exceeds the {NESTED_MAX_DISK_GB} GB limit.')
        return size

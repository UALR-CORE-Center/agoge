import math
import time
from typing import Optional

from google.api_core.exceptions import NotFound as GoogleNotFound

from cloud_fn_utilities.course_objects.compute.base_compute_manager import BaseComputeManager
from cloud_fn_utilities.gcp.address_manager import AddressManager
from cloud_fn_utilities.gcp.dns_manager import DnsManager
from cloud_fn_utilities.gcp.route_manager import RouteManager
from cloud_fn_utilities.server_specific.assessment_manager import AssessmentManager
from cloud_fn_utilities.server_specific.nested_scripts import direct_connect_slot, render_direct_connect
from cloud_fn_utilities.server_specific.wireguard_gateway import (
    BOOT_METADATA_KEY, SECRET_METADATA_KEY, UBUNTU_IMAGE,
    WireGuardGatewayIdentity, managed_metadata,
)
from cloud_fn_utilities.state_managers import ServerStateManager
from common.constants.build_constants import BuildConstants
from common.constants.database import DbCollections, DatabaseTypes, DATABASE_NAME
from common.constants.pub_sub import PubSub
from common.constants.states import ServerStates
from common.document_database import DocumentDatabaseFactory
from common.exceptions import Conflict, NotFound, BadRequest, BaseAgogeException
from common.services.wireguard_endpoint import WireGuardEndpointRegistry
from common.utilities.ctf_plant_contract import (
    LINUX_LOADER,
    LINUX_LOADER_METADATA_KEY,
    WATCHER_INSTALLER,
    WINDOWS_LOADER,
    WINDOWS_LOADER_METADATA_KEY,
)
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import Logger, LoggerNames
from common.utilities.gcp.compute.resources.attached_disk_resource import AttachedDiskResource
from common.utilities.gcp.compute.resources.disks_resource import DiskResource
from common.utilities.gcp.compute.resources.network_interface_resource import NetworkInterfaceResource
from common.utilities.wireguard_firewall import has_public_wireguard_ingress


class LabServerManager(BaseComputeManager):
    # BUILD must never resurrect a VM that an older lifecycle already stopped
    # or retired. START is valid from STOPPED, but not while teardown is in
    # progress or after the server reached a terminal state.
    _WIREGUARD_BUILD_BLOCKED_STATES = frozenset({
        ServerStates.STOPPING.value,
        ServerStates.STOPPED.value,
        ServerStates.EXPIRED.value,
        ServerStates.MISFIT.value,
        ServerStates.DELETING.value,
        ServerStates.DELETED.value,
    })
    _WIREGUARD_START_BLOCKED_STATES = frozenset({
        ServerStates.STOPPING.value,
        ServerStates.EXPIRED.value,
        ServerStates.MISFIT.value,
        ServerStates.DELETING.value,
        ServerStates.DELETED.value,
    })

    def __init__(self, env_dict: dict = None):
        super().__init__(env_dict=env_dict, images=True, disks=True)
        self.logger = Logger(self.log_name, class_name=self.class_name)
        self.env = CloudEnv(env_dict=env_dict) if env_dict else CloudEnv()
        self.env_dict = self.env.get_env()
        self.course_object = PubSub.CourseObjects.LAB_SERVER
        self.dns_manager = DnsManager(env_dict=self.env_dict)
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME
        )
        self.state_manager = ServerStateManager()
        self.collection = DbCollections.SERVER
        self.address_manager = AddressManager(env_dict=self.env_dict)
        self.wireguard_registry = WireGuardEndpointRegistry(
            env_dict=self.env_dict,
            db=self.db,
            log_name=LoggerNames.CLOUD_FN,
        )

    def load(
        self,
        server_name: str,
        network_prefix: str = None,
        **kwargs
    ) -> None:
        if 'server_spec' in kwargs:
            server_spec = kwargs['server_spec']
        else:
            server_spec = self.db.get(collection_name=self.collection, doc_id=server_name)

        if not server_spec:
            self.logger.error(f"{self.class_name}:{self.server_name} - No record exists for compute record!")
            raise LookupError

        self._load_lab_server(server_name, server_spec=server_spec, network_prefix=network_prefix)
        self.nested_host = self._image_is_nested(self.server_spec.image)

        self.state_manager.set_build_record(server_name)
        self.assessment = AssessmentManager(
            build_id=self.parent_build_id,
            build_type=self.parent_build_type,
            env_dict=self.env_dict
        )

    def _image_is_nested(self, image: Optional[str]) -> bool:
        """Returns True when the server's image record is a nested lab host."""
        if not image:
            return False
        _, image_doc_id = self._extract_image_and_server_names(image)
        image_record = self.db.get(collection_name=DbCollections.IMAGE, doc_id=image_doc_id)
        return bool(image_record and image_record.get('nested'))

    def build(self) -> None:
        """Builds an individual server based on the server specifications."""
        # Pub/Sub is at-least-once. Once all VM dependencies have completed and
        # the server is RUNNING, a redelivered build must be a no-op instead of
        # turning an existing-instance Conflict into a BROKEN state.
        current_state = self.state_manager.get_state()
        if current_state == self.s.RUNNING.value:
            return
        if self._wireguard_action_is_blocked("BUILD", current_state):
            return

        # This guard intentionally runs before _build_server: that method's NIC
        # assembly reserves the static address before it inserts the VM. A stale
        # same-owner event must therefore be rejected before either GCP mutation.
        self._require_wireguard_provisionable()

        try:
            if self._managed_wireguard():
                self._prepare_wireguard_bootstrap()
            # A Lab Server is not RUNNING until its DNS, routes, and endpoint
            # publication are complete. Otherwise parent Unit/Workout polling
            # can observe a false success while these dependencies still fail.
            self._build_server(finalize_state=False)
            if self._managed_wireguard():
                self._refresh_wireguard_external_ip()
            # Verify endpoint ownership before any shared DNS mutation. A stale
            # build delivery can outlive the old ID's tombstone quarantine.
            self._stage_wireguard_endpoint()
            self._ensure_dns_record()
            self._build_routes()
            # Compute Engine completion and the cloud dependencies determine
            # lifecycle success. Guest telemetry and peer handshakes can arrive
            # later and must not keep a successfully created lab in BUILDING.
            # Keep a freshly built gateway unpublished until its parent Unit has
            # installed the ingress firewall rules. The Unit promotes it to
            # active only after that final dependency succeeds.
            self.state_manager.state_transition(self.s.RUNNING)
        except Exception:
            self.state_manager.state_transition(self.s.BROKEN)
            self._mark_wireguard_endpoint_error()
            raise

    def start(self, *, community_start_claim=None) -> None:
        if community_start_claim is not None and not self._community_claim_is_current('start', community_start_claim):
            return
        # A retry after DNS publication failed must not issue another start for
        # an instance that is already running. Reuse the VM and retry only the
        # public endpoint dependencies.
        current_state = self.state_manager.get_state()
        if self._wireguard_action_is_blocked("START", current_state):
            return

        # Validate endpoint lifecycle before Compute Engine receives a start
        # request. Ownership checks alone do not catch stale deliveries from the
        # same Unit after its endpoint entered releasing/released.
        self._require_wireguard_provisionable()

        managed_started = False
        if current_state != self.s.RUNNING.value:
            if self._managed_wireguard():
                self._prepare_wireguard_bootstrap(for_start=True)
                managed_started = self._start_server(finalize_state=False)
            else:
                self._start_server()
        if (
            self._wireguard_endpoint_id()
            and (self.state_manager.get_state() == self.s.RUNNING.value or managed_started)
        ):
            try:
                if self._managed_wireguard():
                    self._refresh_wireguard_external_ip()
                else:
                    self.primary_external_ip = self._reserved_external_ip()
                # Stage is also an atomic ownership check. BaseComputeManager
                # intentionally skips WireGuard DNS so this check happens first.
                self._stage_wireguard_endpoint()
                self._ensure_dns_record()
                self._activate_wireguard_endpoint()
                if managed_started:
                    self.state_manager.state_transition(self.s.RUNNING)
            except Exception:
                if self._managed_wireguard():
                    self.state_manager.state_transition(self.s.BROKEN)
                self._mark_wireguard_endpoint_error()
                raise

    def stop(self, *, community_stop_claim=None) -> None:
        if community_stop_claim is not None and not self._community_claim_is_current('stop', community_stop_claim):
            return
        endpoint = None
        if self._managed_wireguard():
            self._require_wireguard_provisionable()
            endpoint = self.wireguard_registry.get(self._wireguard_endpoint_id())
            # Revoke the prior boot nonce before stopping, so delayed health
            # reports cannot make the stopped gateway look usable.
            self._wireguard_provisioning().prepare_boot(self.parent_build_id, force=True)
            self.wireguard_registry.mark_reserved(
                endpoint.id, unit_id=self.parent_build_id,
            )
        self._stop_server()
        if (
            self._wireguard_endpoint_id()
            and self.state_manager.get_state() == self.s.STOPPED.value
        ):
            self.wireguard_registry.mark_reserved(
                self._wireguard_endpoint_id(),
                unit_id=self.parent_build_id,
            )
            if endpoint and endpoint.public_ip:
                if not self.dns_manager.delete_dns(
                    record_name=endpoint.hostname, ip_address=endpoint.public_ip,
                ):
                    raise BaseAgogeException('WireGuard stopped, but DNS removal failed; retry stop')
        if community_stop_claim is not None:
            # A duplicate stop RPC can observe the first RPC still STOPPING.
            # Do not release a waiting first-student start until GCP and this
            # stop's endpoint/DNS cleanup have both finished.
            deadline = time.monotonic() + 300
            while self._get_instance_status() != 'TERMINATED':
                if time.monotonic() >= deadline:
                    raise TimeoutError(f'Automatic stop was not confirmed by GCP for {self.server_name}')
                time.sleep(5)
            self._complete_community_stop(community_stop_claim)

    def _complete_community_stop(self, token):
        reference = self.db.db.collection(DbCollections.SERVER.value).document(self.server_name)

        def complete(transaction):
            snapshot = reference.get(transaction=transaction)
            record = snapshot.to_dict() if snapshot.exists else {}
            claim = record.get('community_stop_claim') or {}
            if claim.get('token') == token and record.get('state') == ServerStates.STOPPED.value:
                transaction.set(reference, {'community_stop_claim': {**claim, 'completed': True}}, merge=True)

        self.db.transaction(complete)

    def _community_claim_is_current(self, action, token):
        record = self.db.get(collection_name=DbCollections.SERVER, doc_id=self.server_name) or {}
        claim = record.get(f'community_{action}_claim') or {}
        if action == 'stop':
            # GCP can finish before endpoint/DNS cleanup fails. Keep that exact
            # unfinished claim retryable from STOPPED, while completed claims
            # and claims replaced by a later start remain harmless redeliveries.
            expected_state = record.get('state') in (ServerStates.STOPPING.value, ServerStates.STOPPED.value)
            expected_state = expected_state and claim.get('completed') is not True
        else:
            expected_state = record.get('state') == ServerStates.STARTING.value
        current = (isinstance(token, str) and bool(token) and claim.get('token') == token
                   and expected_state)
        if not current:
            self.logger.info(f'Ignoring obsolete automatic community {action} for {self.server_name}')
        return current

    def delete(
        self,
        delete_image: bool = False,
        state_transition: bool = True,
    ) -> bool:
        """
        Deletes a compute instance based on the specification in the database document
        with the name server_name.

        Args:
            delete_image (bool): Delete image and image records; Defaults to False
            state_transition (): Include state transition; Defaults to True

        Returns:

        """
        # A duplicate delete delivery must not release endpoint resources a
        # second time. Do not skip DELETING: a failed delivery must be able to
        # resume its remaining cleanup on retry.
        if self.state_manager.get_state() == self.s.DELETED.value:
            return True

        if state_transition:
            self.state_manager.state_transition(self.s.DELETING)

        self.logger.info(f'{self.class_name}:{self.server_name} - Deleting server')
        wireguard_endpoint = self._mark_wireguard_endpoint_releasing()
        self._delete_routes()

        dns_deleted = True
        if dns_record := self._dns_record():
            self.logger.info(f'{self.class_name}:{self.server_name} - Deleting DNS record for server, '
                             f'{self.parent_build_id}')
            if self._wireguard_endpoint_id():
                # A delayed delete can arrive after the five-digit ID has been
                # purged and assigned to another Unit. Only delete the RRset
                # when this Unit still owns the endpoint and the A record still
                # contains its recorded public address.
                if wireguard_endpoint and wireguard_endpoint.public_ip:
                    dns_deleted = self.dns_manager.delete_dns(
                        record_name=dns_record,
                        ip_address=wireguard_endpoint.public_ip,
                    )
                else:
                    self.logger.warning(
                        f'{self.class_name}:{self.server_name} - Skipping WireGuard DNS deletion because '
                        f'the endpoint is missing, belongs to another Unit, or has no recorded public IP'
                    )
            else:
                dns_deleted = self.dns_manager.delete_dns(record_name=dns_record)

        try:
            deleted = self.compute_instance.delete(resource_name=self.server_name, wait=True)
            if not deleted:
                self.logger.error(
                    f'{self.class_name}:{self.server_name} - Compute Engine did not confirm server deletion'
                )
                if state_transition:
                    self.state_manager.state_transition(self.s.BROKEN)
                self._mark_wireguard_endpoint_error()
                return False
        except (NotFound, GoogleNotFound):
            # If the resource can't be found, it was either already deleted or never created
            self.logger.info(
                f'{self.class_name}:{self.server_name} - Server is already absent; '
                'continuing with the rebuild.'
            )
        except (BadRequest, BaseAgogeException):
            if state_transition:
                self.state_manager.state_transition(self.s.BROKEN)
            self._mark_wireguard_endpoint_error()
            return False

        if not dns_deleted:
            # Keep the address reserved while a stale A record still points to
            # it. A later idempotent delete can retry DNS removal before the
            # address becomes eligible for reassignment.
            self.logger.error(
                f'{self.class_name}:{self.server_name} - DNS deletion was not confirmed; '
                f'retaining the reserved external address'
            )
            if state_transition:
                self.state_manager.state_transition(self.s.BROKEN)
            self._mark_wireguard_endpoint_error()
            return False

        # Do not report the server deleted until all resources tied to the
        # public locator are released. An exception leaves the build retryable
        # in DELETING instead of allowing the parent Unit to tear down early.
        self._release_reserved_external_addresses()
        if self._managed_wireguard():
            self._wireguard_provisioning().release(self.parent_build_id)
            WireGuardGatewayIdentity(self.env.project).delete(self.parent_build_id)
        self._release_wireguard_endpoint()

        if state_transition:
            self.state_manager.state_transition(self.s.DELETED)

        return True

    def nuke(self) -> None:
        """
        Deletes a server based on the specification in the database with the name server_name.
        Then rebuilds the server.
        """
        if not self.delete():
            raise RuntimeError(
                f"Cannot rebuild {self.server_name}: server deletion failed."
            )
        self.build()

    def _add_disks(self) -> None:
        disks = None
        if self.server_spec.build_type != BuildConstants.ServerBuildType.MACHINE_IMAGE:
            boot_disk = self._get_boot_disk(
                image_source=UBUNTU_IMAGE,
                disk_size_gb=max(10, getattr(self.server_spec, 'disk_size', 10) or 10),
            ) if self._managed_wireguard() else self._get_boot_disk()
            disks = [boot_disk]

            # Add any additional disks
            add_disk = self.server_spec.add_disk
            if add_disk != 0:
                # Create the AttachedDisk object
                attached_disk_resource = AttachedDiskResource()
                new_attached_disk = attached_disk_resource.new(boot=False, auto_delete=True)
                disks.append(new_attached_disk)

                try:
                    # Now build the disk, so it is ready to attach when the server is built.
                    disk_name = f'{self.server_name}-disk-1'
                    new_disk = DiskResource(project=self.env.project, zone=self.env.zone).new(
                        name=disk_name,
                        size_gb=add_disk
                    )
                    self.compute_disk.create(
                        resource_name=disk_name,
                        wait=True,
                        disk=new_disk
                    )
                except Conflict:
                    # Disk already exists. Ignore Disk.insert request
                    pass

        self.server_spec.disks = disks

    def _add_metadata(self):
        if getattr(self.server_spec, 'community_proxy', False):
            # Generated shared proxies carry only the repository-owned bootstrap.
            # Assessment scripts must never run under the signing-key identity.
            return
        if self._managed_wireguard():
            # Managed gateways run only the repository bootstrap. Catalog or
            # assessment scripts must not replace its security policy.
            self.server_spec.metadata = self._managed_wireguard_metadata
            return
        metadata = {'items': []}
        if self.server_spec.metadata:
            if isinstance(self.server_spec.metadata, dict) and 'items' in self.server_spec.metadata:
                for item in self.server_spec.metadata['items']:
                    self._merge_metadata_item(metadata['items'], item)
            elif isinstance(self.server_spec.metadata, list):
                for item in self.server_spec.metadata:
                    self._merge_metadata_item(metadata['items'], item)
            elif isinstance(self.server_spec.metadata, dict):
                self._merge_metadata_item(metadata['items'], self.server_spec.metadata)
        if self.server_spec.ssh_keys:
            self._merge_metadata_item(metadata['items'], {"key": "ssh-keys", "value": self._ssh_keys()})
        if self.server_spec.startup_script:
            self._merge_metadata_item(
                metadata['items'],
                {"key": "startup-script", "value": self.server_spec.startup_script},
            )
        if self.server_spec.guacamole_startup_script:
            self._merge_metadata_item(
                metadata['items'],
                {"key": "startup-script", "value": self.server_spec.guacamole_startup_script},
            )
        assessment_startup_script = self.assessment.get_startup_scripts(server_name=self.server_spec.name)
        if assessment_startup_script:
            self._merge_metadata_item(metadata['items'], assessment_startup_script)
        if self._is_linux_nested_host():
            self._add_ctf_watcher(metadata['items'])
            self._add_nested_direct_connect(metadata['items'])
        self._add_ctf_loaders(metadata['items'])
        self.server_spec.metadata = metadata

    def _is_linux_nested_host(self) -> bool:
        """A Linux server with an ip_aliases NIC, or one the unit's CTF block names as a nested_guests parent."""
        # Reads the spec, not self.ip_aliases, because _add_nics sets that after _add_metadata runs
        if getattr(self.server_spec, 'os', None) != 'linux':
            return False
        if any(isinstance(nic, dict) and nic.get('ip_aliases') for nic in getattr(self.server_spec, 'nics', None) or []):
            return True
        return self._declares_nested_guests()

    def _declares_nested_guests(self) -> bool:
        """True when ctf.nested_guests on the unit (already loaded by AssessmentManager) names this server."""
        unit = getattr(self.assessment, 'unit', None)
        if not isinstance(unit, dict):
            return False
        guests = (unit.get('ctf') or {}).get('nested_guests') or []
        # Instance names are f"{parent_id}-{spec name}"; guests reference the spec name
        spec_name = self.server_spec.name.removeprefix(f"{getattr(self.server_spec, 'parent_id', None)}-")
        return any(isinstance(guest, dict) and guest.get('server') == spec_name for guest in guests)

    @classmethod
    def _add_ctf_watcher(cls, items: list) -> None:
        """Merge the plant watcher installer into startup-script, so a nested host is planted without a reset."""
        # Spec metadata copied from an already-built server may carry the installer; one copy only.
        if any(
            item.get('key') == LINUX_LOADER_METADATA_KEY and WATCHER_INSTALLER in (item.get('value') or '')
            for item in items
        ):
            return
        cls._merge_metadata_item(items, {'key': LINUX_LOADER_METADATA_KEY, 'value': WATCHER_INSTALLER})

    def _add_nested_direct_connect(self, items: list) -> None:
        """On a direct-connect nested host, merge the forward that sends outside SSH to its jumpbox guest."""
        nics = getattr(self.server_spec, 'nics', None) or []
        nic0 = nics[0] if nics and isinstance(nics[0], dict) else {}
        if not (nic0.get('direct_connect') and nic0.get('external_nat')):
            return
        slot = direct_connect_slot(getattr(self.server_spec, 'human_interaction', None))
        if slot is None:
            return
        script = render_direct_connect(slot)
        # Spec metadata copied from an already-built server may carry the forward; one copy only.
        if any(item.get('key') == 'startup-script' and script in (item.get('value') or '') for item in items):
            return
        self._merge_metadata_item(items, {'key': 'startup-script', 'value': script})

    @classmethod
    def _add_ctf_loaders(cls, items: list) -> None:
        """Append the fixed CTF loaders last, so they run after every other boot script.

        Every lab server gets both: the guest agent only runs the key for its own OS, and a
        loader with no `agoge-ctf-plant` key present does nothing. A CTF event can only plant
        servers built with these loaders, so they are not gated on the unit having a ctf block.
        """
        for key, loader in ((LINUX_LOADER_METADATA_KEY, LINUX_LOADER), (WINDOWS_LOADER_METADATA_KEY, WINDOWS_LOADER)):
            # Spec metadata copied from an already-built server may carry the loader; one copy only.
            if any(item.get('key') == key and loader in (item.get('value') or '') for item in items):
                continue
            cls._merge_metadata_item(items, {'key': key, 'value': loader})

    def _add_nics(self) -> None:
        network_interface_resource = NetworkInterfaceResource(region=self.env.region, project=self.env.project)
        network_prefix = self.server_spec.network_prefix
        network_interfaces = []

        for network in self.server_spec.nics:
            access_configs = None
            internal_ip = None
            alias_ip_ranges = None

            if network.get("external_nat", None):
                public_ip = None
                if (requested_address_name := network.get('external_ip_name')) and not self._managed_wireguard():
                    address_name = self._external_address_name(requested_address_name)
                    public_ip = self.address_manager.reserve(
                        name=address_name,
                        description=f'Reserved public address for Agoge server {self.server_name}',
                    )
                    network['external_ip_name'] = address_name
                    if self.primary_external_ip is None:
                        self.primary_external_ip = public_ip
                access_configs = [
                    network_interface_resource.access_config(
                        type_='ONE_TO_ONE_NAT',
                        name='External NAT',
                        nat_ip=public_ip,
                    )
                ]

            if 'internal_ip' in network:
                internal_ip = network['internal_ip']

            if ip_aliases := network.get('ip_aliases', None):
                self.ip_aliases = True
                alias_ip_ranges = []
                for ipaddr in ip_aliases:
                    alias_ip_range = network_interface_resource.alias_ip_range(ip_cidr_range=f'{ipaddr}/32')
                    alias_ip_ranges.append(alias_ip_range)

            network_interface = network_interface_resource.new(
                network_name=f'{network_prefix}-{network["network"]}',
                subnetwork_name=f'{network_prefix}-{network["network"]}-{network["subnet_name"]}',
                access_configs=access_configs,
                alias_ip_ranges=alias_ip_ranges,
                internal_ip=internal_ip
            )
            network_interfaces.append(network_interface)
        self.server_spec.network_interfaces = network_interfaces

    def _external_address_name(self, requested_name: str) -> str:
        prefix = self.server_spec.network_prefix or self.server_spec.parent_id
        return requested_name if requested_name.startswith(f'{prefix}-') else f'{prefix}-{requested_name}'

    def _reserved_external_address_names(self) -> list[str]:
        if self._managed_wireguard():
            return []
        if not hasattr(self, 'server_spec'):
            return []
        return [
            self._external_address_name(nic['external_ip_name'])
            for nic in (self.server_spec.nics or [])
            if nic.get('external_ip_name')
        ]

    def _release_reserved_external_addresses(self) -> None:
        for address_name in self._reserved_external_address_names():
            self.address_manager.release(address_name)

    def _reserved_external_ip(self) -> str | None:
        address_names = self._reserved_external_address_names()
        return self.address_manager.get(address_names[0]) if address_names else None

    def _build_routes(self) -> None:
        if routes := getattr(getattr(self, 'server_spec', None), 'routes', None):
            RouteManager(self.server_spec.network_prefix or self.parent_build_id, env_dict=self.env_dict).build(
                routes
            )

    def _ensure_dns_record(self) -> None:
        if dns_record := self._dns_record():
            success = self.dns_manager.add_dns_record(
                dns_record,
                self.server_name,
                ip_address=self.primary_external_ip,
            )
            if (self._wireguard_endpoint_id() or getattr(self.server_spec, 'community_proxy', False)) and not success:
                raise BaseAgogeException(f'Unable to publish DNS record {dns_record}')

    def _delete_routes(self) -> None:
        if routes := getattr(getattr(self, 'server_spec', None), 'routes', None):
            RouteManager(self.server_spec.network_prefix or self.parent_build_id, env_dict=self.env_dict).delete(
                routes
            )

    def _activate_wireguard_endpoint(self) -> None:
        if endpoint_id := self._wireguard_endpoint_id():
            # Shared gateways are reactivated here after their VM starts. Repeat
            # the parent Unit's policy check so this path cannot bypass the
            # CommunityUnit build-time publication guard.
            endpoint = self.wireguard_registry.require_provisionable(
                endpoint_id,
                unit_id=self.parent_build_id,
            )
            unit = self.db.get(
                collection_name=DbCollections.UNIT,
                doc_id=self.parent_build_id,
            )
            if not unit or not has_public_wireguard_ingress(unit, endpoint.port):
                raise BadRequest(
                    f'Refusing to activate WireGuard endpoint {endpoint_id}: the Unit '
                    f'does not allow public UDP/{endpoint.port} ingress to its gateway.'
                )
            if self._managed_wireguard():
                lease = self._wireguard_provisioning().get_lease(self.parent_build_id)
                if (lease.status != 'reserved' or not math.isfinite(lease.expires) or lease.expires <= time.time()
                        or lease.unit_id != self.parent_build_id or lease.endpoint_id != endpoint_id):
                    raise BadRequest('The WireGuard lab lease is expired, released, or no longer owns this endpoint')
            self.wireguard_registry.activate(
                endpoint_id,
                unit_id=self.parent_build_id,
                public_ip=self.primary_external_ip,
            )

    def _require_wireguard_provisionable(self) -> None:
        if endpoint_id := self._wireguard_endpoint_id():
            self.wireguard_registry.require_provisionable(
                endpoint_id,
                unit_id=self.parent_build_id,
            )

    def _wireguard_action_is_blocked(self, action: str, current_state: int) -> bool:
        shared_proxy = getattr(self.server_spec, 'community_proxy', False)
        if not self._wireguard_endpoint_id() and not shared_proxy:
            return False
        blocked_states = (
            self._WIREGUARD_BUILD_BLOCKED_STATES
            if action == "BUILD"
            else self._WIREGUARD_START_BLOCKED_STATES
        )
        # A community proxy enters STARTING only after the initial build, when
        # a student or instructor starts the parked service. Delayed BUILD
        # deliveries must not race that separate runtime operation.
        if current_state not in blocked_states and not (
                shared_proxy and action == 'BUILD' and current_state == self.s.STARTING.value):
            return False
        self.logger.warning(
            f'{self.class_name}:{self.server_name} - Ignoring stale shared-service {action} '
            f'event while server is in state {self.s(current_state).name}'
        )
        return True

    def _stage_wireguard_endpoint(self) -> None:
        if endpoint_id := self._wireguard_endpoint_id():
            self.wireguard_registry.stage(
                endpoint_id,
                unit_id=self.parent_build_id,
                public_ip=self.primary_external_ip,
            )

    def _mark_wireguard_endpoint_error(self) -> None:
        if endpoint_id := self._wireguard_endpoint_id():
            try:
                self.wireguard_registry.mark_error(
                    endpoint_id,
                    unit_id=self.parent_build_id,
                )
            except (NotFound, BadRequest) as error:
                self.logger.warning(
                    f'{self.class_name}:{endpoint_id} - Could not mark WireGuard endpoint error: {error}'
                )
            if self._managed_wireguard() and self.primary_external_ip and self._dns_record():
                # An unready ephemeral address must not remain advertised after
                # its VM is later deleted or recreated. Preserve ownership/IP
                # checks and leave failures visible for cleanup retries.
                if not self.dns_manager.delete_dns(
                    record_name=self._dns_record(), ip_address=self.primary_external_ip,
                ):
                    self.logger.warning('Unable to remove DNS for an unready WireGuard gateway')

    def _mark_wireguard_endpoint_releasing(self):
        if endpoint_id := self._wireguard_endpoint_id():
            try:
                return self.wireguard_registry.mark_releasing(
                    endpoint_id,
                    unit_id=self.parent_build_id,
                )
            except (NotFound, BadRequest) as error:
                self.logger.warning(
                    f'{self.class_name}:{endpoint_id} - Could not mark WireGuard endpoint releasing: {error}'
                )
        return None

    def _release_wireguard_endpoint(self) -> None:
        if endpoint_id := self._wireguard_endpoint_id():
            try:
                self.wireguard_registry.release(endpoint_id, unit_id=self.parent_build_id)
            except (NotFound, BadRequest) as error:
                self.logger.warning(
                    f'{self.class_name}:{endpoint_id} - Could not release WireGuard endpoint: {error}'
                )

    def _dns_record(self) -> str | bool:
        if not hasattr(self, 'server_spec'):
            return False
        return self._server_dns_record()

    def _wireguard_endpoint_id(self) -> str | None:
        """Return the endpoint ID without requiring legacy specs to define it."""
        return getattr(getattr(self, 'server_spec', None), 'wireguard_endpoint_id', None)

    def _managed_wireguard(self) -> bool:
        return getattr(getattr(self, 'server_spec', None), 'wireguard_managed', False) is True

    def _wireguard_provisioning(self):
        from common.services.wireguard_provisioning import WireGuardProvisioningService

        return WireGuardProvisioningService(self.env_dict, db=self.db)

    def _prepare_wireguard_bootstrap(self, for_start: bool = False) -> None:
        service = self._wireguard_provisioning()
        lease = service.get_lease(self.parent_build_id)
        if (lease.status != 'reserved' or not math.isfinite(lease.expires) or lease.expires <= time.time()
                or lease.unit_id != self.parent_build_id or lease.endpoint_id != self._wireguard_endpoint_id()):
            raise BadRequest('The WireGuard lab lease is expired or released')
        identity = WireGuardGatewayIdentity(self.env.project)
        email = identity.ensure(self.parent_build_id)
        service.grant_gateway_access(self.parent_build_id, email)
        self.server_spec.service_accounts = [{
            'email': email,
            'scopes': ['https://www.googleapis.com/auth/cloud-platform'],
        }]
        self.server_spec.can_ip_forward = True
        self.server_spec.build_type = None

        try:
            existing = self.compute_instance.get(resource_name=self.server_name)
        except (NotFound, GoogleNotFound):
            if for_start:
                raise BadRequest('The managed gateway VM is missing; rebuild the lab')
            existing = None

        current_metadata = self._resource_field(existing, 'metadata', {}) if existing else {}
        items = list(self._resource_field(current_metadata, 'items', []) or [])
        fields = {self._resource_field(item, 'key'): self._resource_field(item, 'value')
                  for item in items}
        if existing:
            accounts = self._resource_field(existing, 'service_accounts', []) or []
            status = str(self._resource_field(existing, 'status', '')).upper()
            prior_configurations = [getattr(lease, 'previous_secret_version_name', None),
                                    *(getattr(lease, 'secret_history', None) or [])]
            saved_change = (for_start and status == 'TERMINATED' and getattr(lease, 'configuration_pending', False)
                            and bool(fields.get(SECRET_METADATA_KEY))
                            and fields.get(SECRET_METADATA_KEY) in prior_configurations)
            if (
                not any(self._resource_field(account, 'email') == email for account in accounts)
                or (fields.get(SECRET_METADATA_KEY) != lease.secret_version_name and not saved_change)
            ):
                raise BadRequest('Existing gateway identity or configuration differs; rebuild the lab')

        status = str(self._resource_field(existing, 'status', '')).upper()
        running = status in {'RUNNING', 'PROVISIONING', 'STAGING'}
        nonce = fields.get(BOOT_METADATA_KEY) if running else None
        if nonce:
            if nonce != lease.boot_id:
                raise BadRequest('Gateway boot generation differs from its lease; stop and restart the lab')
        else:
            nonce = service.prepare_boot(self.parent_build_id)
        metadata = managed_metadata(lease.secret_version_name, nonce)
        self._managed_wireguard_metadata = metadata
        if for_start and existing and not running:
            if getattr(lease, 'configuration_pending', False):
                from cloud_fn_utilities.server_specific.wireguard_configuration import apply_saved_wireguard_network
                apply_saved_wireguard_network(self, lease)
            # Fingerprint prevents overwriting concurrent metadata changes.
            metadata['fingerprint'] = self._resource_field(current_metadata, 'fingerprint')
            preserved = [
                {'key': self._resource_field(item, 'key'), 'value': self._resource_field(item, 'value')}
                for item in items
                if self._resource_field(item, 'key') not in {
                    BOOT_METADATA_KEY, SECRET_METADATA_KEY, 'startup-script', 'startup-script-url',
                }
            ]
            metadata['items'] = preserved + metadata['items']
            if not self.compute_instance.replace_metadata(self.server_name, metadata, wait=True):
                raise BaseAgogeException('Unable to update WireGuard startup configuration; retry start')
            if getattr(lease, 'configuration_pending', False):
                service.configuration_applied(self.parent_build_id, lease.configuration_revision)

    def _refresh_wireguard_external_ip(self) -> None:
        instance = self.compute_instance.get(resource_name=self.server_name)
        self.primary_external_ip = None
        for nic in self._resource_field(instance, 'network_interfaces', []) or []:
            for config in self._resource_field(nic, 'access_configs', []) or []:
                if address := self._resource_field(config, 'nat_i_p'):
                    self.primary_external_ip = address
                    return
        raise BaseAgogeException('The WireGuard gateway has no public IPv4 address')

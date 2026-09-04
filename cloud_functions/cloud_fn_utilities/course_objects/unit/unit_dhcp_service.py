import copy
import ipaddress
import uuid
from typing import List, Optional

from common.constants.database import DbCollections, DatabaseTypes, DATABASE_NAME
from common.document_database import DocumentDatabaseFactory, DatabaseQueries
from common.utilities.gcp.cloud_logger import Logger, LoggerNames
from common.models.agoge import UnitModel
from common.models.model_validators.model_validator import ModelValidator


class UnitDHCP:
    """
    Manages the allocation of network addresses for a unit within a specified network.

    This class provides functionality to retrieve available network addresses from a specified subnet
    within a unit, taking into account any reserved addresses.

    Attributes:
        unit_id (str): The unique identifier of the unit.
        db (DocumentDatabase): An instance of DocumentDatabase for managing unit data.
        logger (Logger): Logger for logging messages.

    """
    LEASE_CLAIM_FIELD = 'dhcp_lease_claim_id'
    LEASE_RELEASED_FIELD = 'dhcp_leases_released'

    def __init__(
        self,
        unit_id: str
    ) -> None:
        self.unit_id = unit_id
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME
        )
        self.db_queries = DatabaseQueries(db=self.db)
        self.logger = Logger(LoggerNames.CLOUD_FN)
        self.validator = ModelValidator

    def get_network_address(
        self,
        network_name: str,
        subnet_name: str = 'default'
    ) -> str:
        """
        Retrieves an available network address from a specified network.

        Attempts to find and return an unreserved IP address from the specified network. If no address
        is available or an error occurs, it raises an exception.

        Args:
            network_name (str): The name of the network from which to retrieve an address.
            subnet_name (str): The named subnet from which to retrieve an address.

        Returns:
            str: The allocated IP address as a string.

        Raises:
            LookupError: If the Unit does not exist.
            ValueError: If the network or subnet configuration is invalid.
            RuntimeError: If the subnet has no allocatable addresses remaining.
        """
        try:
            # Reading and writing inside one Firestore transaction is essential here.
            # Separate transactional get/update calls use separate transactions and can
            # allocate the same address to simultaneous workout builds.
            return self.db.transaction(
                operation_func=self._reserve_network_address,
                network_name=network_name,
                subnet_name=subnet_name,
            )
        except Exception as error:
            self.logger.error(
                f"Could not allocate a network address for unit {self.unit_id} "
                f"on network {network_name}, subnet {subnet_name}: {error}"
            )
            raise

    def claim_server_leases(
        self,
        server_name: str,
        server_data: dict,
    ) -> dict:
        """Atomically reserve all dynamic NIC addresses and persist their owner.

        The server document is the durable lease claim. Keeping its write in the
        same Firestore transaction as the Unit reservation update makes duplicate
        workout build deliveries idempotent: after a write conflict, the losing
        transaction sees the winning server record and reuses its addresses.

        Args:
            server_name: Full, workout-qualified server document ID.
            server_data: Serialized server template whose dynamic NICs need IPs.

        Returns:
            A copy of ``server_data`` containing the claimed NIC addresses.
        """
        if not server_name:
            raise ValueError("A server name is required to claim DHCP leases.")
        try:
            candidate_claim_id = uuid.uuid4().hex
            return self.db.transaction(
                operation_func=self._claim_server_leases,
                server_name=server_name,
                server_data=server_data,
                candidate_claim_id=candidate_claim_id,
            )
        except Exception as error:
            self.logger.error(
                f"Could not claim network addresses for server {server_name} "
                f"in unit {self.unit_id}: {error}"
            )
            raise

    def release_server_leases(
        self,
        server_name: str,
        claim_id: Optional[str] = None,
    ) -> bool:
        """Release one server's leases once, guarded by its durable claim ID.

        ``claim_id`` comes from the server record captured by the delete
        delivery. A stale delivery cannot release a newer incarnation of the
        same server document, and a retry sees the released marker and no-ops.
        Legacy records without a claim ID are released only when the caller also
        has no claim ID.
        """
        if not server_name:
            raise ValueError("A server name is required to release DHCP leases.")
        try:
            return self.db.transaction(
                operation_func=self._release_server_leases,
                server_name=server_name,
                expected_claim_id=claim_id,
            )
        except Exception as error:
            self.logger.error(
                f"Could not release network addresses for server {server_name} "
                f"in unit {self.unit_id}: {error}"
            )
            raise

    def release_network_address(
        self,
        network_name: str,
        address: str,
        subnet_name: str = 'default'
    ) -> bool:
        """Atomically release a dynamically allocated address back to the Unit pool."""
        try:
            return self.db.transaction(
                operation_func=self._release_network_address,
                network_name=network_name,
                address=address,
                subnet_name=subnet_name,
            )
        except Exception as error:
            self.logger.error(
                f"Could not release network address {address} for unit {self.unit_id} "
                f"on network {network_name}, subnet {subnet_name}: {error}"
            )
            raise

    def _reserve_network_address(
        self,
        transaction,
        network_name: str,
        subnet_name: str = 'default'
    ) -> str:
        """Firestore transaction callback that reserves and persists one address."""
        doc_ref = self.db.db.collection(DbCollections.UNIT.value).document(self.unit_id)
        snapshot = doc_ref.get(transaction=transaction)
        if not snapshot.exists:
            raise LookupError(f"Unit {self.unit_id} does not exist.")

        unit = snapshot.to_dict()
        network = self._get_network(unit, network_name)
        subnet = self._get_subnet(network, network_name, subnet_name)
        reservations = self._get_reservations(unit, network_name, subnet_name)
        available_ip = self._get_available_ip(subnet, reservations=reservations)
        if available_ip is None:
            raise RuntimeError(
                f"No addresses remain in network {network_name}, subnet {subnet_name} "
                f"for unit {self.unit_id}."
            )

        network['reservations'].append(available_ip)
        self._validate_unit(unit)
        transaction.set(doc_ref, {'networks': unit['networks']}, merge=True)
        return available_ip

    def _claim_server_leases(
        self,
        transaction,
        server_name: str,
        server_data: dict,
        candidate_claim_id: str,
    ) -> dict:
        """Firestore callback coupling Unit reservations to one server record."""
        unit_ref = self.db.db.collection(DbCollections.UNIT.value).document(self.unit_id)
        server_ref = self.db.db.collection(DbCollections.SERVER.value).document(server_name)

        # Firestore requires every transactional read to precede the first write.
        unit_snapshot = unit_ref.get(transaction=transaction)
        server_snapshot = server_ref.get(transaction=transaction)
        if not unit_snapshot.exists:
            raise LookupError(f"Unit {self.unit_id} does not exist.")

        unit = unit_snapshot.to_dict()
        existing_server = server_snapshot.to_dict() if server_snapshot.exists else {}
        existing_nics = existing_server.get('nics') or []
        existing_claim_active = bool(existing_server) and not existing_server.get(
            self.LEASE_RELEASED_FIELD, False
        )
        claimed_server = copy.deepcopy(server_data)

        for nic_index, nic in enumerate(claimed_server.get('nics') or []):
            network_name = nic.get('network')
            if not network_name:
                raise ValueError(
                    f"NIC {nic_index} on server {server_name} does not define a network."
                )
            subnet_name = nic.get('subnet_name') or 'default'
            network = self._get_network(unit, network_name)
            subnet = self._get_subnet(network, network_name, subnet_name)
            reservations = self._get_reservations(unit, network_name, subnet_name)

            existing_nic = existing_nics[nic_index] if nic_index < len(existing_nics) else {}
            existing_subnet = existing_nic.get('subnet_name') or 'default'
            existing_address = existing_nic.get('internal_ip')
            if (
                existing_claim_active
                and existing_nic.get('network') == network_name
                and existing_subnet == subnet_name
                and self._is_reusable_address(existing_address, subnet)
            ):
                internal_ip = existing_address
                # Repair a legacy/incomplete Unit reservation while preserving the
                # existing server as the authoritative owner of the lease.
                if internal_ip not in reservations:
                    network['reservations'].append(internal_ip)
            else:
                # Per-workout servers always receive a dynamic address. Ignore a
                # legacy IP copied from the shared Unit template; otherwise every
                # student workout would attempt to claim that same template IP.
                internal_ip = self._get_available_ip(subnet, reservations=reservations)
                if internal_ip is None:
                    raise RuntimeError(
                        f"No addresses remain in network {network_name}, subnet {subnet_name} "
                        f"for unit {self.unit_id}."
                    )
                network['reservations'].append(internal_ip)
            nic['internal_ip'] = internal_ip

        active_claim_id = existing_server.get(self.LEASE_CLAIM_FIELD)
        claimed_server[self.LEASE_CLAIM_FIELD] = (
            active_claim_id if existing_claim_active and active_claim_id
            else candidate_claim_id
        )
        claimed_server[self.LEASE_RELEASED_FIELD] = False

        # A provisioning retry must not erase state written by the compute
        # worker between build deliveries.
        for runtime_field in ('state', 'state_timestamp', 'shutoff_timestamp'):
            if runtime_field in existing_server:
                claimed_server[runtime_field] = existing_server[runtime_field]

        self._validate_unit(unit)
        transaction.set(unit_ref, {'networks': unit['networks']}, merge=True)
        transaction.set(server_ref, claimed_server, merge=True)
        return claimed_server

    def _release_server_leases(
        self,
        transaction,
        server_name: str,
        expected_claim_id: Optional[str],
    ) -> bool:
        """Firestore callback that removes and tombstones an owned lease claim."""
        unit_ref = self.db.db.collection(DbCollections.UNIT.value).document(self.unit_id)
        server_ref = self.db.db.collection(DbCollections.SERVER.value).document(server_name)

        unit_snapshot = unit_ref.get(transaction=transaction)
        server_snapshot = server_ref.get(transaction=transaction)
        if not unit_snapshot.exists:
            raise LookupError(f"Unit {self.unit_id} does not exist.")
        if not server_snapshot.exists:
            return False

        unit = unit_snapshot.to_dict()
        server = server_snapshot.to_dict()
        if server.get(self.LEASE_RELEASED_FIELD, False):
            return False

        persisted_claim_id = server.get(self.LEASE_CLAIM_FIELD)
        if persisted_claim_id != expected_claim_id:
            self.logger.warning(
                f"Refusing to release stale DHCP claim for server {server_name}."
            )
            return False

        released_any = False
        for nic in server.get('nics') or []:
            network_name = nic.get('network')
            address = nic.get('internal_ip')
            if not network_name or not address:
                continue
            subnet_name = nic.get('subnet_name') or 'default'
            network = self._get_network(unit, network_name)
            subnet = self._get_subnet(network, network_name, subnet_name)
            if not self._is_reusable_address(address, subnet):
                raise ValueError(
                    f"Address {address} on server {server_name} is not allocatable "
                    f"in network {network_name}, subnet {subnet_name}."
                )
            if address in self._get_static_reservations(unit, network_name, subnet_name):
                continue

            existing_reservations = list(network.get('reservations') or [])
            network['reservations'] = [
                reserved_address
                for reserved_address in existing_reservations
                if reserved_address != address
            ]
            released_any = released_any or (
                len(network['reservations']) != len(existing_reservations)
            )
            self._get_reservations(unit, network_name, subnet_name)

        self._validate_unit(unit)
        transaction.set(unit_ref, {'networks': unit['networks']}, merge=True)
        transaction.set(
            server_ref,
            {self.LEASE_RELEASED_FIELD: True},
            merge=True,
        )
        return released_any

    def _release_network_address(
        self,
        transaction,
        network_name: str,
        address: str,
        subnet_name: str = 'default'
    ) -> bool:
        """Firestore transaction callback that releases one non-static address."""
        doc_ref = self.db.db.collection(DbCollections.UNIT.value).document(self.unit_id)
        snapshot = doc_ref.get(transaction=transaction)
        if not snapshot.exists:
            raise LookupError(f"Unit {self.unit_id} does not exist.")

        unit = snapshot.to_dict()
        network = self._get_network(unit, network_name)
        subnet = self._get_subnet(network, network_name, subnet_name)
        try:
            release_address = ipaddress.ip_address(address)
        except ValueError as error:
            raise ValueError(f"Invalid IPv4 address {address}.") from error
        if release_address.version != 4 or release_address not in subnet:
            raise ValueError(
                f"Address {address} is not in network {network_name}, subnet {subnet_name} "
                f"({subnet})."
            )

        static_reservations = set(
            self._get_static_reservations(unit, network_name, subnet_name)
        )
        if address in static_reservations:
            self.logger.warning(
                f"Refusing to release static community-server address {address} "
                f"from unit {self.unit_id}."
            )
            return False

        existing_reservations = list(network.get('reservations') or [])
        network['reservations'] = [
            reserved_address
            for reserved_address in existing_reservations
            if reserved_address != address
        ]
        # This also repairs legacy null reservation arrays and preserves all
        # configured community-server addresses.
        self._get_reservations(unit, network_name, subnet_name)
        self._validate_unit(unit)
        transaction.set(doc_ref, {'networks': unit['networks']}, merge=True)
        return len(network['reservations']) != len(existing_reservations)

    @staticmethod
    def _get_network(unit: dict, network_name: str) -> dict:
        network = next(
            (network for network in unit.get('networks') or [] if network.get('name') == network_name),
            None
        )
        if network is None:
            raise ValueError(f"Network {network_name} is not defined in the Unit.")
        return network

    @staticmethod
    def _get_subnet(
        network: dict,
        network_name: str,
        subnet_name: str = 'default'
    ) -> ipaddress.IPv4Network:
        subnets = network.get('subnets') or []
        subnet_config = next(
            (
                subnet for subnet in subnets
                if subnet.get('name', 'default') == subnet_name
            ),
            None
        )
        if subnet_config is None or not subnet_config.get('ip_subnet'):
            raise ValueError(
                f"Network {network_name} does not define subnet {subnet_name}."
            )
        subnet = ipaddress.ip_network(subnet_config['ip_subnet'])
        if subnet.version != 4:
            raise ValueError("Unit DHCP currently supports IPv4 subnets only.")
        return subnet

    def _validate_unit(self, unit: dict) -> None:
        self.validator(UnitModel, log_location=LoggerNames.CLOUD_FN).load(data=unit)

    @staticmethod
    def _get_reservations(
        unit: dict,
        network_name: str,
        subnet_name: str = 'default'
    ) -> List:
        """
        Updates the reservation information for a given network within a unit.

        Args:
            unit (dict): The unit dictionary containing network and server information.
            network_name (str): The name of the network for which reservations are to be updated.

        Returns:
            List: An array of network IP addresses already reserved.
        """

        network = UnitDHCP._get_network(unit, network_name)
        existing_reservations = list(network.get('reservations') or [])
        static_reservations = UnitDHCP._get_static_reservations(
            unit,
            network_name,
            subnet_name
        )

        # dict preserves insertion order while removing duplicates. Persisting the
        # repaired value also upgrades legacy records with missing/null reservations.
        network['reservations'] = list(dict.fromkeys([
            *existing_reservations,
            *static_reservations,
        ]))
        return network['reservations']

    @staticmethod
    def _get_static_reservations(
        unit: dict,
        network_name: str,
        subnet_name: str = 'default'
    ) -> List[str]:
        return [
            nic['internal_ip']
            for server in unit.get('servers') or []
            if server.get('community_server', False)
            for nic in server.get('nics') or []
            if nic.get('network') == network_name
            and nic.get('subnet_name', 'default') == subnet_name
            and nic.get('internal_ip')
        ]

    def _get_available_ip(
        self,
        subnet: ipaddress.IPv4Network,
        reservations: List
    ) -> Optional[str]:
        """
        Generates an available IP address from a subnet, excluding reserved and special IPs.

        Args:
            subnet (ipaddress.IPv4Network): The subnet to check for available IP addresses.
            reservations (list): A list of already reserved IP addresses.

        Returns:
            An available IP address, or ``None`` when the subnet is exhausted.
        """
        reserved_ips = {ipaddress.ip_address(ip) for ip in reservations}
        for ip in subnet:
            if ip not in reserved_ips and not self._is_special_ip(ip, subnet):
                return str(ip)

    @staticmethod
    def _is_reusable_address(
        address: Optional[str],
        subnet: ipaddress.IPv4Network,
    ) -> bool:
        """Return whether a persisted lease is valid for the requested subnet."""
        if not address:
            return False
        try:
            parsed_address = ipaddress.ip_address(address)
        except ValueError:
            return False
        return (
            parsed_address.version == 4
            and parsed_address in subnet
            and not UnitDHCP._is_special_ip(parsed_address, subnet)
        )

    @staticmethod
    def _is_special_ip(
        ip: ipaddress.IPv4Address,
        subnet: ipaddress.IPv4Network
    ) -> bool:
        """Check if an IP is the first, second, last, or second-to-last in a subnet."""
        first, last = subnet.network_address, subnet.broadcast_address
        return ip in {first, first + 1, last - 1, last}

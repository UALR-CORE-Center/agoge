import ipaddress
from ipaddress import IPv4Address
from typing import Union, Tuple, Any, List

from common.constants.database import DbCollections, DATABASE_NAME, DatabaseTypes
from common.constants.states import WorkoutStates
from common.constants.google import AddressTypes, FirewallDirection, FirewallRuleAction
from common.document_database import DatabaseMask
from common.document_database.factory import DocumentDatabaseFactory
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import Logger, LoggerNames
from common.utilities.gcp.compute.compute_firewall import ComputeFirewallsAPI
from common.utilities.gcp.compute.resources.firewall_resource import FirewallResource
from common.exceptions import (
    Conflict,
    BadRequest,
    ServiceUnavailable,
    NotReady,
    NotAllowed,
    NotFound,
    BaseAgogeException
)
from common.utilities.gcp.compute.resources.network_resource import NetworkResource


class WorkoutInternetFirewall:
    """
    Manages the Google Cloud firewall rule permitting Internet access for a given workout lab

    This class provides methods to add and remove student IP addresses to the lab's
    firewall rules, allowing for dynamic access control based on the students'
    external IP addresses.
    """

    def __init__(
        self,
        workout_id: str,
        env_dict: dict
    ) -> None:
        """
        Initialize the LabFirewall instance.

        Args:
            workout_id (str): The unique identifier for the workout lab.
            env_dict (dict): A dictionary of environment variables.
                                       Defaults to None.

        Raises:
            NotFound: If the workout lab is not found in the datastore.
        """
        self.class_name = self.__class__.__name__
        self.log_name = LoggerNames.API
        self.workout_id = workout_id
        self.env = CloudEnv(env_dict=env_dict)
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME
        )
        self.collection = DbCollections.WORKOUT
        workout = self.db.get(collection_name=self.collection, doc_id=self.workout_id)
        unit_id = workout.get('parent_id', None)
        self.firewalls_client = ComputeFirewallsAPI(
            project=self.env.project,
            region=self.env.region,
            zone=self.env.zone,
            log_name=self.log_name
        )
        self.firewall_resource = FirewallResource()
        self.logger = Logger(
            log_name=self.log_name,
            unit_id=unit_id,
            workout_id=workout_id,
            class_name=self.class_name
        )
        self.db_mask = DatabaseMask(self.logger)
        self.workout = None
        self._refresh_cache()  # Populate self.workout
        self.direct_connect_networks = self._find_direct_connect_networks()

    @staticmethod
    def firewall_rule_name(
        workout_id: str,
        network: str,
        suffix: str
    ) -> str:
        return f"{workout_id}-{network}-{suffix}"

    @staticmethod
    def _get_ip_ranges(ip_addresses: List[str]) -> dict:
        """Generates IP ranges based on IP addr type"""
        sorted_addresses = {AddressTypes.IPv4: [], AddressTypes.IPv6: []}
        for ip_address in ip_addresses:
            if ip_address != "":
                if isinstance(ipaddress.ip_address(ip_address), IPv4Address):
                    sorted_addresses[AddressTypes.IPv4].append(f"{ip_address}/32")
                else:
                    sorted_addresses[AddressTypes.IPv6].append(f"{ip_address}/128")
        return sorted_addresses

    def direct_connect_rule_name(self, network: str, address_type: AddressTypes = AddressTypes.IPv4) -> str:
        return self.firewall_rule_name(self.workout_id, network, f"{address_type}-allow-direct-connect")

    def display_proxy_rule_name(self, network: str) -> str:
        return self.firewall_rule_name(self.workout_id, network, "student-entry")

    def add_ip_address(
        self,
        json_data: dict = None,
        ip_address: str = None
    ) -> None:
        """
        Add an IP address to the lab firewall to allow access.

        Args:
            json_data (dict): FastAPI Request with submitted JSON data
            ip_address (str): The IP address to be added in string format.

        Raises:
            NotFound: If the workout lab is not found.
            Exception: If an error occurs during the update process.
        """
        if not self.env.student_workout_firewall:
            self._replace_lab_firewall_rule(ip_addresses=['0.0.0.0/0'], add_default=True)
            raise NotAllowed(message="Request to add IP to student workout firewall failed. "
                                     "Feature is disabled on project!")
        if not ip_address and not json_data:
            raise BadRequest("Requested to add IP failed. Values 'request' or 'ip_address' were missing!")
        elif not ip_address and json_data:
            ip_address = json_data.get('ip_address')
            if ip_address in ["", "null"]:
                raise BadRequest(f"Invalid or missing object for `ip_address`. `{ip_address}`")

        self.logger.info(f"{self.class_name}: Adding IP address {ip_address} to workout {self.workout_id}")

        self._refresh_cache()
        ip_addresses = self.workout.get('student_external_ip_addresses') or []
        if ip_address not in ip_addresses:
            ip_addresses.append(ip_address)
            self.workout['student_external_ip_addresses'] = ip_addresses
            try:
                self._replace_lab_firewall_rule(ip_addresses)
            except Exception as e:
                self.logger.error(
                    f"{self.class_name} - Failed to add IP address {ip_address} to lab firewall: {e}",
                    ip_address=ip_address
                )
                raise ServiceUnavailable(message=f"Failed to add IP address to lab firewall.")

            # Rule is updated. It's safe to update Datastore record
            self.logger.info(
                f"IP address {ip_address} added to lab firewall.",
                ip_address=ip_address
            )
            db_mask = self.db_mask.get(self.workout, ['student_external_ip_addresses'])
            self.db.update(collection_name=self.collection, doc_id=self.workout_id, data=db_mask)
            return
        else:
            msg = (f"{self.class_name} - IP address {ip_address} already exists in lab firewall for "
                   f"workout {self.workout_id}")
            self.logger.info(msg, ip_address=ip_address)
            raise Conflict(message=msg)

    def disable_internet_access(self) -> None:
        """Delete the workout Internet firewall rule to deny access.

        Raises:
            NotFound: If the workout lab is not found.
            Exception: If an error occurs during the update process.
        """
        self.logger.debug(f"{self.class_name} - Disabling Internet access to workout {self.workout_id}")

        self._refresh_cache()

        list_filter = f"(name = {self.workout_id}*-*-allow-direct-connect)"
        firewall_rules = self.firewalls_client.list(filter_=list_filter)
        firewall_rule_names = [rule["name"] for rule in firewall_rules]
        for firewall_rule_name in firewall_rule_names:
            self._delete_rule(firewall_rule_name)

        self.workout['student_external_ip_addresses'] = []
        db_mask = self.db_mask.get(self.workout, ['student_external_ip_addresses'])
        self.db.update(collection_name=self.collection, doc_id=self.workout_id, data=db_mask)

    def _refresh_cache(self) -> None:
        """
        Refresh the local cache of the workout data from the datastore.

        Raises:
            NotFound: If the workout lab is not found in the datastore.
            NotReady: If workout lab exists but is in a premature build state
        """
        self.logger.debug(f"{self.class_name} - Refreshing cache for workout {self.workout_id}")

        self.workout = self.db.get(collection_name=self.collection, doc_id=self.workout_id)
        if not self.workout:
            self.logger.error(f"{self.class_name} - No workout lab found for ID: {self.workout_id}")
            raise NotFound(message=f"No workout lab found for ID: {self.workout_id}")
        else:
            current_state = self.workout.get('state')
            if current_state <= WorkoutStates.COMPLETED_FIREWALL_RULES.value:
                msg = (f"Requested firewall access for workout lab with ID: {self.workout_id},"
                       f" but resources were not ready. Try again once current build process is complete.")
                self.logger.warning(msg, current_state=current_state)
                raise NotReady(msg)

    def _replace_lab_firewall_rule(
        self,
        ip_addresses: list,
        add_default: bool = False
    ) -> None:
        """
        Replace the lab firewall rule with updated IP addresses.

        Args:
            ip_addresses (list): A list of IP addresses to include in the firewall rule.

        Raises:
            Exception: If an error occurs during the firewall rule update.
        """
        if not add_default:
            ip_ranges = self._get_ip_ranges(ip_addresses)
            self.logger.info(f"{self.class_name} - Replacing lab firewall rules for workout {self.workout_id}",
                             ip_addresses=ip_addresses)

            for network in self.direct_connect_networks:
                if network is None:
                    continue

                for address_types in ip_ranges:
                    ip_type_ranges = ip_ranges[address_types]
                    firewall_name, firewall = self._direct_connect_rule(network, address_types, ip_type_ranges)
                    if self._rule_exists(firewall_name):
                        self._patch_rule(firewall_name, firewall)
                    else:
                        self._create_rule(firewall_name, firewall)
        else:
            # Feature is disabled. Add default public access rule
            for network in self.direct_connect_networks:
                firewall_name, firewall = self._direct_connect_rule(
                    network,
                    address_types=AddressTypes.IPv4,
                    ip_ranges=['0.0.0.0/0']
                )
                if self._rule_exists(firewall_name):
                    self._patch_rule(firewall_name, firewall)
                else:
                    self._create_rule(firewall_name, firewall)

    def _find_direct_connect_networks(self) -> Union[list, list[str]]:
        """
        Identify networks with direct connect enabled from the workout servers.

        Returns:
            list: A list of network names where direct connect is enabled.
        """
        self.logger.debug(f"{self.class_name} - Finding direct connect networks for workout {self.workout_id}")

        direct_connect_networks = []
        servers = self.workout.get('servers', [])
        for server in servers:
            for nic in server.get('nics', []):
                network = f"{server.get('parent_id')}-{nic.get('network')}"
                if nic.get('direct_connect') and network and network not in direct_connect_networks:
                    direct_connect_networks.append(network)
        self.logger.debug(f"{self.class_name} - Direct connect networks found: {direct_connect_networks}")
        return direct_connect_networks

    def _rule_exists(
        self,
        firewall_rule_name: str
    ) -> bool:
        """Checks for the existence of a firewall rule for a given name.

        Args:
            firewall_rule_name (str): The name of the firewall rule.

        Returns (bool): Rule exists

        Raises:
            Exception: If a non-404 error occurs during GET operation
        """
        self.logger.info(f"{self.class_name} - Checking if firewall rule {firewall_rule_name} exists.",
                         firewall_rule_name=firewall_rule_name)
        try:
            self.firewalls_client.get(resource_name=firewall_rule_name)
        except NotFound:
            self.logger.debug(f"{self.class_name} - Firewall rule {firewall_rule_name} not found.",
                              firewall_rule_name=firewall_rule_name)
            return False
        return True

    def _create_rule(
        self,
        firewall_rule_name: str,
        firewall_body: Any
    ) -> None:
        """
        Create VPC firewall rule for given firewall rule name and body.
        Args:
            firewall_rule_name (str): Name of firewall rule to create
            firewall_body (dict): Body of firewall rule to create

        Returns:
        """
        self.logger.info(
            f"{self.class_name} - Inserting new firewall rule: {firewall_rule_name}",
            firewall_body=str(firewall_body)
        )
        self.firewalls_client.create(resource_name=firewall_rule_name, firewall_resource=firewall_body)
        self.logger.info(
            f"{self.class_name} - Firewall rule {firewall_rule_name} updated successfully.",
            firewall_rule=firewall_rule_name,
            firewall_body=str(firewall_body)
        )

    def _delete_rule(
        self,
        firewall_rule_name: str
    ) -> None:
        """
        Delete a target GCP VPC firewall rule for the given firewall rule name
        Args:
            firewall_rule_name (str): Name of firewall rule to delete

        Returns:

        """
        try:
            self.firewalls_client.delete(resource_name=firewall_rule_name)
        except NotFound:
            self.logger.warning(f"{self.class_name} - Firewall rule {firewall_rule_name} not found. "
                                f"Ignoring delete request.")
        except BaseAgogeException as e:
            self.logger.error(f"{self.class_name} - Error deleting firewall rule {firewall_rule_name}: {e}")
            raise

    def _patch_rule(
        self,
        firewall_rule_name: str,
        firewall_body: Any
    ) -> None:
        """
        Update an existing GCP VPC firewall rule for given firewall rule name and body
        Args:
            firewall_rule_name (str): Name of firewall rule to update
            firewall_body (dict): Body of firewall rule to update
        """
        try:
            self.firewalls_client.patch(resource_name=firewall_rule_name, firewall_body=firewall_body)
            self.logger.info(
                f"{self.class_name} - Firewall rule {firewall_rule_name} patched successfully.",
                firewall_rule=firewall_rule_name,
                firewall_body=str(firewall_body)
            )
        except BaseAgogeException:
            raise
        except Exception as e:
            self.logger.error(
                f"Error updating firewall rule with name {firewall_rule_name}. {e}",
                firewall_rule_name=firewall_rule_name,
                firewall_body=str(firewall_body)
            )

    def _direct_connect_rule(
        self,
        network: str,
        address_types: Union[AddressTypes, str],
        ip_ranges: list
    ) -> Tuple[str, Any]:
        firewall_rule_name = self.direct_connect_rule_name(network, address_types)
        allowed = [self.firewall_resource.allowed(ports=["22", "53", "80", "443", "3389"])]
        firewall = self.firewall_resource.new(
            name=firewall_rule_name,
            direction=FirewallDirection.INGRESS,
            network=NetworkResource.network_path(network, self.env.project),
            target_tags=[f"{self.workout_id}-direct-connect"],
            priority=990,
            action=FirewallRuleAction.ALLOW,
            rules=allowed,
            ip_ranges=ip_ranges
        )
        return firewall_rule_name, firewall

    def _display_proxy_rule(
        self,
        network: str,
        ip_ranges: list
    ) -> Tuple[str, Any]:
        firewall_rule_name = self.display_proxy_rule_name(network)
        allowed = [
            self.firewall_resource.allowed(ports=["22", "80", "443", "4822", "8443"])
        ]
        firewall = self.firewall_resource.new(
            name=firewall_rule_name,
            direction=FirewallDirection.INGRESS,
            network=NetworkResource.network_path(network, self.env.project),
            target_tags=[f"{self.workout_id}-direct-connect"],
            priority=990,
            action=FirewallRuleAction.ALLOW,
            rules=allowed,
            ip_ranges=ip_ranges
        )
        return firewall_rule_name, firewall

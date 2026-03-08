import ipaddress
from typing import List

from google.cloud.exceptions import Conflict

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
        network_name: str
    ) -> str:
        """
        Retrieves an available network address from a specified network.

        Attempts to find and return an unreserved IP address from the specified network. If no address
        is available or an error occurs, it raises an exception.

        Args:
            network_name (str): The name of the network from which to retrieve an address.

        Returns:
            str: The allocated IP address as a string.

        Raises:
            Exception: If unable to allocate an IP address after a specified number of attempts.
        """
        max_tries = 5
        for i in range(max_tries):
            unit = self.db.get(collection_name=DbCollections.UNIT, doc_id=self.unit_id, use_transaction=True)
            # Loop through the unit networks to find the one matching the passed network name
            network = next((net for net in unit.get('networks', []) if net['name'] == network_name), None)

            subnet = ipaddress.ip_network(network['subnets'][0]['ip_subnet'])

            # Get the reservations already existing or create reservations from existing community server ip addresses
            reservations = self._get_reservations(unit, network_name)

            # Find an available IP address
            available_ip = self._get_available_ip(subnet, reservations=reservations)

            # Set the IP address in the unit object and save the unit record to preserve the reservation.
            network['reservations'].append(available_ip)
            if self.validator(UnitModel).load(data=unit):
                try:
                    self.db.update(
                        collection_name=DbCollections.UNIT,
                        doc_id=self.unit_id,
                        data=unit,
                        use_transaction=True
                    )
                    # Finally, return the reserved IP address
                    return available_ip
                except Conflict as e:
                    self.logger.error(f"Attempt {i + 1}/{max_tries} failed: {e}")
                    if i == max_tries - 1:
                        error_msg = f"Could not get network address for unit {self.unit_id} after {max_tries} attempts."
                        self.logger.error(error_msg)
                        raise Exception(error_msg)

    @staticmethod
    def _get_reservations(
        unit: dict,
        network_name: str
    ) -> List:
        """
        Updates the reservation information for a given network within a unit.

        Args:
            unit (dict): The unit dictionary containing network and server information.
            network_name (str): The name of the network for which reservations are to be updated.

        Returns:
            List: An array of network IP addresses already reserved.
        """

        # Test if 'reservations' exists and return if it's already filled
        for network in unit['networks']:
            if network['name'] == network_name:
                # If reservations are not present, compute and assign them
                if 'reservations' not in network:
                    network['reservations'] = [
                        nic['internal_ip']
                        for server in unit.get('servers', [])
                        if server.get('community_server', False)
                        for nic in server.get('nics', [])
                        if nic.get('network') == network_name
                    ]
                return network['reservations']

    def _get_available_ip(
        self,
        subnet: ipaddress.IPv4Network,
        reservations: List
    ) -> str:
        """
        Generates an available IP address from a subnet, excluding reserved and special IPs.

        Args:
            subnet (ipaddress.IPv4Network): The subnet to check for available IP addresses.
            reservations (list): A list of already reserved IP addresses.

        Yields:
            str: An available IP address within the subnet.
        """
        for sub_subnet in subnet.subnets(new_prefix=24):
            reserved_ips = set(ipaddress.ip_address(ip) for ip in reservations)
            for ip in sub_subnet:
                if ip not in reserved_ips and not self._is_special_ip(ip, sub_subnet):
                    return str(ip)

    @staticmethod
    def _is_special_ip(
        ip: ipaddress.IPv4Address,
        subnet: ipaddress.IPv4Network
    ) -> bool:
        """Check if an IP is the first, second, last, or second-to-last in a subnet."""
        first, last = subnet.network_address, subnet.broadcast_address
        return ip in {first, first + 1, last - 1, last}

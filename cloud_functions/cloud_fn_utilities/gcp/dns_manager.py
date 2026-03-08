import time

import googleapiclient.discovery
from googleapiclient.errors import HttpError

from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import Logger, LoggerNames
from common.utilities.gcp.compute.compute_instance import ComputeInstanceAPI


class DnsManager:
    MAX_ITERATIONS = 20
    SLEEP_TIME = 10

    def __init__(self, env_dict=None):
        self.class_name = self.__class__.__name__
        self.log_name = LoggerNames.CLOUD_FN
        self.env = CloudEnv(env_dict=env_dict) if env_dict else CloudEnv()
        self.compute_instance = ComputeInstanceAPI(
            project=self.env.project,
            region=self.env.region,
            zone=self.env.zone,
            log_name=self.log_name
        )
        self.dns = googleapiclient.discovery.build('dns', 'v1', cache_discovery=False)
        self.logger = Logger(self.log_name, class_name=self.class_name)
        # Adding new parent dns logic
        self.parent_dns_project = self.env.parent_project
        self.parent_dns_zone = self.env.parent_zone

    def add_dns_record(self, dns_record, server_name):
        response = self.dns.resourceRecordSets().list(
            project=self.env.parent_project,
            managedZone=self.env.parent_zone,
            name=dns_record
        ).execute()
        existing_rrset = response['rrsets']
        new_ip_address = self._get_external_ip_address(server_name)
        if not new_ip_address:
            self.logger.error(f"{self.class_name}:{server_name} - Cannot set the DNS for {dns_record}. "
                              f"The external IP address could not be obtained")
            return
        change_body = {
            "deletions": existing_rrset,
            "additions": [
                {
                    "kind": "dns#resourceRecordSet",
                    "name": dns_record,
                    "rrdatas": [new_ip_address],
                    "type": "A",
                    "ttl": 30
                }
            ],
        }
        # Try first to perform the DNS change, but in case the DNS did not exist, try again without the deletion change.
        try:
            self.dns.changes().create(
                project=self.env.parent_project,
                managedZone=self.env.parent_zone,
                body=change_body
            ).execute()
        except HttpError as e:
            try:
                self.logger.warning(f"{self.class_name}:{server_name} - Error in adding DNS record: "
                                    f"{e.error_details}. Attempting to remove the prior deletion.")
                del change_body["deletions"]
                self.dns.changes().create(
                    project=self.env.parent_project,
                    managedZone=self.env.parent_zone,
                    body=change_body
                ).execute()
            except HttpError as e:
                self.logger.warning(f"{self.class_name}:{server_name} - Another error when attempting to only add "
                                    f"the DNS record: {e.error_details}")

    def delete_dns(self, record_name=None, ip_address=None):
        """
        Deletes a DNS record based on the build_id host name and IP address or by record name.
        :param record_name: The record name to delete. Generally in format <build_id>.<dns_suffix>.
                            e.g. abiurkjdyx.somedomain.com. or kjeiurkjlo-display.somedomain.com.
        :param ip_address: The IP address of the record to delete.
        :return: None
        """
        change_body = {"deletions": [
            {
                "kind": "dns#resourceRecordSet",
                "name": record_name,
                "type": "A",
                "ttl": 30
            },
        ]}
        if not ip_address:
            return self._delete_dns_record_set(record_name)
        else:
            change_body["deletions"][0]["rrdatas"] = [ip_address]

        try:
            self.dns.changes().create(
                project=self.env.parent_project,
                managedZone=self.env.parent_zone,
                body=change_body
            ).execute()
        except HttpError as e:
            self.logger.error(f"{self.class_name}:{record_name} - Error when trying to delete DNS: {e.error_details}")
            return False
        return True

    def _delete_dns_record_set(self, record_name):
        """
        This is the intended deletion method to be used when the
        rrdata object is not known in the record.
        """
        try:
            request = self.dns.resourceRecordSets().delete(
                project=self.env.parent_project,
                managedZone=self.env.parent_zone,
                name=record_name,
                type='A'
            )
            response = request.execute()
        except HttpError as e:
            self.logger.error(f"{self.class_name}:{record_name} - Error when trying to delete DNS for "
                              f"{e.error_details}")
            return False
        return True

    def add_active_directory_dns(self, build_id, ip_address, network):
        """
        Add a DNS forwarding rule to support an Active Directory server acting as the default DNS server
        @param build_id: The ID of the workout or arena with the DNS server
        @type build_id: String
        @param ip_address: IP address of the active directory server
        @type ip_address: String
        @param network: A list of network names to use for DNS forwarding
        @type network: List
        @return: Status
        @rtype: Boolean
        """

        managed_zone_body = {
            "kind": "dns#managedZone",
            "name": build_id,
            "dnsName": "cybergym.local.",
            "visibility": "private",
            "description": "",
            "privateVisibilityConfig": {
                "kind": "dns#managedZonePrivateVisibilityConfig",
                "networks": []
            },
            "forwardingConfig": {
                "kind": "dns#managedZoneForwardingConfig",
                "targetNameServers": [
                    {
                        "kind": "dns#managedZoneForwardingConfigNameServerTarget",
                        "ipv4Address": ip_address,
                        "forwardingPath": "default"
                    }
                ],
            }
        }

        forwarding_network = {
            "kind": "dns#managedZonePrivateVisibilityConfigNetwork",
            "networkUrl": f"https://www.googleapis.com/compute/v1/projects/{self.env.parent_project}/global/networks/{network}"
        }
        managed_zone_body["privateVisibilityConfig"]["networks"].append(forwarding_network)

        # Try first to perform the DNS change, but in case the DNS did not previously exist,
        # try again without the deletion change.
        try:
            self.dns.managedZones().create(project=self.env.parent_project, body=managed_zone_body).execute()
        except HttpError as e:
            self.logger.error(f"{self.class_name}:{build_id} - Error when adding a DNS forwarding rule "
                              f"in Active Directory for {build_id} and network {network}: {e.error_details}")
            raise e

    def delete_active_directory_dns(self, managed_zone):
        """
        Deletes the given managed zone
        @param managed_zone: Managed zone for deleting
        @type managed_zone: str
        @return: Status
        @rtype: bool
        """
        try:
            request = self.dns.managedZones().delete(project=self.env.parent_project, managedZone=managed_zone)
            request.execute()
        except HttpError as e:
            self.logger.error(f"{self.class_name}:{managed_zone} - Error when deleting a DNS forwarding "
                              f"rule for Active Directory on managed zone: {e.error_details}")
            raise e

    def _get_external_ip_address(self, server_name):
        """
        Provides the IP address of a given server name.
        :param server_name: The server name in the cloud project
        :return: The IP address of the server or throws an error
        """
        i = 0
        while i < self.MAX_ITERATIONS:
            try:
                new_instance = self.compute_instance.get(resource_name=server_name)
                ip_address = new_instance.network_interfaces[0].access_configs[0].nat_i_p
                return ip_address
            except KeyError:
                self.logger.debug(f"{self.class_name}:{server_name} - Error: No IP address exists. "
                                  f"The server may still be building. Trying again in "
                                  f"{self.SLEEP_TIME} seconds.")
                time.sleep(self.SLEEP_TIME)
                i += 1
        return False

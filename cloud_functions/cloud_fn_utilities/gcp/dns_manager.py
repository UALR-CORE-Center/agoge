import time

import googleapiclient.discovery
from googleapiclient.errors import HttpError

from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import Logger, LoggerNames
from common.utilities.gcp.compute.compute_instance import ComputeInstanceAPI


class DnsManager:
    MAX_ITERATIONS = 20
    MAX_CHANGE_RETRIES = 3
    CHANGE_RETRY_DELAY = 1
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

    def add_dns_record(self, dns_record, server_name=None, ip_address=None):
        """Idempotently point an A record at a server or a known public IP.

        Reserved addresses are known before an instance is created, so callers
        can avoid polling the instance API by supplying ``ip_address``. Existing
        callers that only provide ``server_name`` retain their previous behavior.
        """
        dns_record = self._fqdn(dns_record)
        new_ip_address = ip_address or self._get_external_ip_address(server_name)
        if not new_ip_address:
            self.logger.error(f"{self.class_name}:{server_name} - Cannot set the DNS for {dns_record}. "
                              f"The external IP address could not be obtained")
            return False

        for attempt in range(self.MAX_CHANGE_RETRIES):
            try:
                existing_rrset = self._list_a_records(dns_record)
            except HttpError as error:
                self.logger.warning(
                    f"{self.class_name}:{server_name} - Error listing DNS record {dns_record}: "
                    f"{self._http_error_details(error)}"
                )
                return False

            if len(existing_rrset) == 1 and existing_rrset[0].get('rrdatas') == [new_ip_address]:
                return True

            change_body = {
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
            if existing_rrset:
                change_body["deletions"] = existing_rrset

            try:
                self.dns.changes().create(
                    project=self.env.parent_project,
                    managedZone=self.env.parent_zone,
                    body=change_body
                ).execute()
                return True
            except HttpError as error:
                # Concurrent idempotent builders can race to publish the same
                # record. Re-read after a conflict; the next iteration returns
                # success if the desired address is already present.
                if self._http_status(error) == 409 and attempt + 1 < self.MAX_CHANGE_RETRIES:
                    self.logger.info(
                        f"{self.class_name}:{server_name} - Concurrent DNS update for {dns_record}; retrying"
                    )
                    time.sleep(self.CHANGE_RETRY_DELAY)
                    continue
                self.logger.warning(
                    f"{self.class_name}:{server_name} - Error in upserting DNS record {dns_record}: "
                    f"{self._http_error_details(error)}"
                )
                return False
        return False

    def _list_a_records(self, dns_record: str) -> list[dict]:
        response = self.dns.resourceRecordSets().list(
            project=self.env.parent_project,
            managedZone=self.env.parent_zone,
            name=dns_record,
            type='A',
        ).execute()
        return [
            record
            for record in response.get('rrsets', [])
            if record.get('name') == dns_record and record.get('type') == 'A'
        ]

    @staticmethod
    def _http_status(error: HttpError) -> int | None:
        return getattr(getattr(error, 'resp', None), 'status', None)

    @staticmethod
    def _http_error_details(error: HttpError) -> str:
        return str(getattr(error, 'error_details', None) or error)

    def delete_dns(self, record_name=None, ip_address=None):
        """
        Deletes a DNS record based on the build_id host name and IP address or by record name.
        :param record_name: The record name to delete. Generally in format <build_id>.<dns_suffix>.
                            e.g. abiurkjdyx.somedomain.com. or kjeiurkjlo-display.somedomain.com.
        :param ip_address: The IP address of the record to delete.
        :return: None
        """
        if not record_name:
            return False
        record_name = self._fqdn(record_name)
        if not ip_address:
            return self._delete_dns_record_set(record_name)

        # Ownership-safe deletion for public endpoint records. Read the exact
        # RRset first and delete it only if it still points solely to the
        # caller's recorded address. A delayed teardown must not delete a name
        # that has since been reassigned to another endpoint.
        try:
            existing_rrsets = self._list_a_records(record_name)
        except HttpError as error:
            self.logger.error(
                f"{self.class_name}:{record_name} - Error listing DNS before deletion: "
                f"{self._http_error_details(error)}"
            )
            return False

        if not existing_rrsets:
            return True

        if (
            len(existing_rrsets) != 1
            or existing_rrsets[0].get("rrdatas") != [ip_address]
        ):
            self.logger.warning(
                f"{self.class_name}:{record_name} - Skipping DNS deletion because the A record "
                f"no longer matches the expected address"
            )
            return True

        existing = existing_rrsets[0]
        deletion = {
            key: existing[key]
            for key in ("kind", "name", "type", "ttl", "rrdatas")
            if key in existing
        }
        change_body = {"deletions": [deletion]}

        try:
            self.dns.changes().create(
                project=self.env.parent_project,
                managedZone=self.env.parent_zone,
                body=change_body
            ).execute()
        except HttpError as e:
            if self._http_status(e) == 404:
                return True
            self.logger.error(
                f"{self.class_name}:{record_name} - Error when trying to delete DNS: "
                f"{self._http_error_details(e)}"
            )
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
            if self._http_status(e) == 404:
                return True
            self.logger.error(
                f"{self.class_name}:{record_name} - Error when trying to delete DNS for "
                f"{self._http_error_details(e)}"
            )
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
        if not server_name:
            return False
        i = 0
        while i < self.MAX_ITERATIONS:
            try:
                new_instance = self.compute_instance.get(resource_name=server_name)
                ip_address = new_instance.network_interfaces[0].access_configs[0].nat_i_p
                if ip_address:
                    return ip_address
            except (KeyError, IndexError, AttributeError):
                self.logger.debug(f"{self.class_name}:{server_name} - Error: No IP address exists. "
                                  f"The server may still be building. Trying again in "
                                  f"{self.SLEEP_TIME} seconds.")
            time.sleep(self.SLEEP_TIME)
            i += 1
        return False

    @staticmethod
    def _fqdn(record_name: str) -> str:
        return record_name if record_name.endswith('.') else f'{record_name}.'

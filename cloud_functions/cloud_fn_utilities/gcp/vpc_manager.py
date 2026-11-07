import time
from typing import TypeVar, Type, Union

import googleapiclient.discovery
from googleapiclient.errors import HttpError

from common.constants.database import DATABASE_NAME, DatabaseTypes
from common.constants.google import OperationType
from common.document_database import DocumentDatabaseFactory
from common.exceptions import Conflict, NotFound
from common.models.agoge import NetworkModel, SubNetworkModel
from common.utilities.build_incidents import BuildIncidents, BuildQuotaHold
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import Logger, LoggerNames
from common.utilities.gcp.compute.base_compute_api import BaseComputeAPI
from common.utilities.gcp.compute.compute_networks import ComputeNetworksAPI
from common.utilities.gcp.compute.compute_subnetwork import ComputeSubnetworksAPI
from common.utilities.gcp.compute.resources.network_resource import NetworkResource
from common.utilities.gcp.compute.resources.subnetwork_resource import SubnetworkResource
from cloud_fn_utilities.build_execution import current_build_execution, ensure_current_build, tracked_compute_create

ComputeApiClient = TypeVar('ComputeApiClient', bound=BaseComputeAPI)


class VpcManager:
    def __init__(
        self,
        build_id: str,
        env_dict=None
    ) -> None:
        self.class_name = self.__class__.__name__
        self.log_name = LoggerNames.CLOUD_FN
        self.env = CloudEnv(env_dict=env_dict) if env_dict else CloudEnv()
        self.compute = googleapiclient.discovery.build('compute', 'v1', cache_discovery=False)
        self.networks_client = self._enable_compute_api(ComputeNetworksAPI)
        self.subnetworks_client = self._enable_compute_api(ComputeSubnetworksAPI)
        self.network_resource = NetworkResource(region=self.env.region, project=self.env.project)
        self.subnet_resource = SubnetworkResource(region=self.env.region, project=self.env.project)
        self.build_id = build_id
        self.logger = Logger(self.log_name, class_name=self.class_name)

    @staticmethod
    def _network_name(build_id, network: NetworkModel) -> str:
        return f"{build_id}-{network.name}"

    @staticmethod
    def _subnet_name(network_name: str, subnet: SubNetworkModel) -> str:
        return f'{network_name}-{subnet.name}'

    def _enable_compute_api(
        self,
        client_cls: Type[ComputeApiClient],
    ) -> ComputeApiClient:
        return client_cls(
            project=self.env.project,
            region=self.env.region,
            zone=self.env.zone,
            log_name=self.log_name
        )

    def build(
        self,
        network: NetworkModel
    ) -> None:
        network_name = self._network_name(self.build_id, network)
        self.logger.info(f"{self.class_name}:{network_name} - Building network")

        network_body = self.network_resource.new(name=network_name, auto_create_subnetworks=False)
        ensure_current_build()
        if execution := current_build_execution():
            db = execution.db
        else:
            db = DocumentDatabaseFactory.create_db_object(
                db_type=DatabaseTypes.firestore, database_name=DATABASE_NAME,
            )
        hold = BuildIncidents(db, self.env.project).active_hold()
        if hold:
            # An existing VPC consumes no additional network quota. Confirm
            # ownership by the deterministic resource name in this project.
            try:
                self.networks_client.get(resource=network_name)
            except NotFound as error:
                raise BuildQuotaHold(hold) from error
        else:
            self._create_and_confirm(
                self.networks_client, network_name, OperationType.GLOBAL, network_resource=network_body,
            )

        subnets = network.subnets or []
        for subnet in subnets:
            subnet_name = self._subnet_name(network_name, subnet)
            network_path = self.network_resource.network_path(network_name=network_name, project=self.env.project)
            self.logger.info(f"{self.class_name}:{network_name} - Building the subnetwork {subnet_name}")
            subnetwork_body = self.subnet_resource.new(
                name=subnet_name,
                network=network_path,
                ip_cidr_range=subnet.ip_subnet
            )
            self._create_and_confirm(
                self.subnetworks_client, subnet_name, OperationType.REGION, subnet_resource=subnetwork_body,
            )

    @staticmethod
    def _create_and_confirm(client, name, operation_type, **resource):
        ensure_current_build()
        try:
            if tracked_compute_create(client, name, operation_type, **resource):
                return
        except Conflict:
            # A prior delivery may have completed this idempotent creation.
            try:
                client.get(resource=name)
            except NotFound as error:
                raise ConnectionError(f'Creation of {name} has not been confirmed') from error
            return

        raise ConnectionError(f'Creation of {name} has not been confirmed')

    def delete(
        self,
        network: NetworkModel
    ) -> bool:
        network_name = self._network_name(self.build_id, network)
        subnets = network.subnets or []
        for subnet in subnets:
            subnet_name = self._subnet_name(network_name, subnet)
            self.logger.info(f"{self.class_name}:{network_name} - Deleting subnetwork {subnet_name}")
            try:
                deleted = self.subnetworks_client.delete(resource_name=subnet_name)
                if not deleted:
                    raise ConnectionError(
                        f'Timed out deleting subnetwork {subnet_name}'
                    )
            except NotFound:
                self.logger.info(
                    f"{self.class_name}:{network_name} - Error deleting subnetwork {subnet_name}. "
                    f"Resource does not exist! Ignoring ..."
                )
                pass

        self.logger.info(f"{self.class_name}:{network_name} - Deleting network")
        try:
            deleted = self.networks_client.delete(resource_name=network_name)
            if not deleted:
                raise ConnectionError(
                    f'Timed out deleting network {network_name}'
                )
            time.sleep(3)
        except NotFound:
            self.logger.info(
                f"{self.class_name}:{network_name} - Error deleting network: "
                f"resource does not exist! Ignoring ..."
            )
            pass
        return True

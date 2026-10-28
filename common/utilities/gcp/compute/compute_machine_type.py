from typing import Any, List, Union

from google.cloud.compute_v1 import (
    MachineType,
    MachineTypesClient,
    ListMachineTypesRequest,
    GetMachineTypeRequest
)
from googleapiclient.discovery import Resource

from common.constants.google import ResourceType, ClientType
from common.constants.nested import (
    NESTED_MACHINE_FAMILIES,
    NESTED_MACHINE_TYPES,
    NESTED_MAX_MACHINE_MEMORY_MB,
    STANDARD_MAX_MACHINE_MEMORY_MB
)
from common.models.google import MachineTypeModel
from common.utilities.gcp.cloud_logger import LoggerNames
from .base_compute_api import BaseComputeAPI


def is_allowed_machine_type(name: str, memory_mb: int, nested: bool = False) -> bool:
    """Whether a machine type may be offered for a server build.

    Standard servers may use N1, N2, or E2 types up to 17000 MB. Nested hosts
    need nested virtualization, so only N1, N2, and N4 types qualify, up to
    NESTED_MAX_MACHINE_MEMORY_MB.
    """
    family = name.split('-')[0]
    if nested:
        return family in NESTED_MACHINE_FAMILIES and memory_mb <= NESTED_MAX_MACHINE_MEMORY_MB
    return family in BaseComputeAPI.ALLOWED_GOOGLE_MACHINE_TYPES and memory_mb <= STANDARD_MAX_MACHINE_MEMORY_MB


def disk_type_for(machine_type: str) -> Union[str, None]:
    """The disk type a machine type's disks must use, or None for Compute Engine's default.

    N4 attaches only Hyperdisk, while the default (pd-standard) still suits every
    other series. Accepts a bare name or a machine type URL.
    """
    if isinstance(machine_type, str) and machine_type.rsplit('/', 1)[-1].startswith('n4-'):
        return 'hyperdisk-balanced'
    return None


class ComputeMachineTypesAPI(BaseComputeAPI):
    """Handles operations related to Compute Engine machine types in Google Cloud.

    This class extends the base ComputeAPI to provide methods for retrieving
    Compute Engine machine types.
    """

    def __init__(
        self,
        project: str,
        region: str,
        zone: str,
        log_name: str = LoggerNames.CLOUD_FN
    ) -> None:
        """Initializes the ComputeImageAPI.

        Args:
           log_name (str, optional): Name of the logger to use. Defaults to
                LoggerNames.CLOUD_FN.
        """
        super().__init__(project=project, region=region, zone=zone, log_name=log_name)
        self.resource_type = ResourceType.MACHINE_TYPE
        self.client_type = ClientType.MACHINE_TYPES_CLIENT

    def client(self) -> Union[Resource, MachineTypesClient]:
        if not self.machine_type_client:
            self.machine_type_client = MachineTypesClient()
        return self.machine_type_client

    def list(
        self,
        project: str = None,
        zone: str = None,
        nested: bool = False,
    ) -> List[MachineTypeModel]:
        """Retrieve list of allowed machine types in the project.

        If any error occurs during the list request, an empty list is returned
        instead of raising an exception.

        Args:
            project (str, optional): Name of project to get machine types
            zone (str, optional): Name of zone to get machine types
            nested (bool, optional): List the NESTED_MACHINE_TYPES offered for
                nested images instead of the standard list

        Returns:
            List(MachineTypeModel)
        """
        client = self.client()

        # Construct ListMachineTypesRequest object
        project = project or self.project
        zone = zone or self.zone
        list_request = ListMachineTypesRequest(project=project, zone=zone)

        m_types = self._make_request(
            client_request=client.list,
            resource=None,
            action='list',
            wait=False,
            request=list_request
        )

        valid_m_types = []
        for m_type in m_types:
            if nested and m_type.name not in NESTED_MACHINE_TYPES:
                continue
            if cleaned_m_type := self._machine_type_object(m_type, nested=nested):
                valid_m_types.append(cleaned_m_type)

        return valid_m_types

    def get(
        self,
        resource: str,
        project: str = None,
        zone: str = None,
        **kwargs
    ) -> Any:
        """Retrieves a Compute Engine machine type from a specific project.
        If the machine type is not allowed, method returns nothing. N1, N2, and N4
        types resolve up to the nested cap so nested hosts can use them; E2
        types keep the standard cap.

        Args:
            resource (str): The name of the machine type to retrieve.
            project (str, optional): The project ID from which the machine type is
                retrieved. If None, defaults to the project in the environment
                configuration.
            zone (str, optional): The zone ID for the machine type. If None, defaults to the zone
                in the environment configuration

        Returns:
            Any: A dictionary representing the machine type resource.

        Raises:
            NotFound: If the requested machine type could not be found.
        """
        m_type = self.get_resource(resource, project=project, zone=zone)
        if not m_type:
            return None
        return self._machine_type_object(m_type, nested=True) or self._machine_type_object(m_type)

    def get_resource(self, resource: str, project: str = None, zone: str = None) -> MachineType:
        """Read complete machine metadata without dropping its architecture."""
        client = self.client()

        if not project:
            project = self.project
        if not zone:
            zone = self.zone

        request = GetMachineTypeRequest(
            machine_type=resource,
            project=project,
            zone=zone
        )

        machine_type = self._make_request(
            client_request=client.get,
            resource=resource,
            action='get',
            wait=False,
            request=request
        )
        return machine_type

    def create(self, resource_name: str, wait: bool = True, **kwargs) -> bool:
        pass

    def delete(self, resource_name: str, wait: bool = True, **kwargs) -> bool:
        pass

    def update(self, resource_name: str, wait: bool = True, **kwargs) -> bool:
        pass

    def _machine_type_object(
        self,
        m_type: MachineType,
        nested: bool = False
    ) -> Union[MachineTypeModel, None]:
        name = m_type.name
        if is_allowed_machine_type(name, m_type.memory_mb, nested=nested):
            return MachineTypeModel(
                id=name,
                name=name,
                description=m_type.description,
                is_shared_core=m_type.is_shared_cpu,
                memory_mb=m_type.memory_mb,
                guest_cpus=m_type.guest_cpus
            )
        else:
            return

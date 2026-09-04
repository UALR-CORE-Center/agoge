from common.exceptions import Conflict, NotFound
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import Logger, LoggerNames
from common.utilities.gcp.compute.compute_address import ComputeAddressesAPI
from common.utilities.gcp.compute.resources.address_resource import AddressResource


class AddressManager:
    """Idempotently reserves and releases regional public IPv4 addresses."""

    def __init__(self, env_dict: dict = None) -> None:
        self.class_name = self.__class__.__name__
        self.env = CloudEnv(env_dict=env_dict) if env_dict else CloudEnv()
        self.logger = Logger(LoggerNames.CLOUD_FN, class_name=self.class_name)
        self.addresses_client = ComputeAddressesAPI(
            project=self.env.project,
            region=self.env.region,
            zone=self.env.zone,
            log_name=LoggerNames.CLOUD_FN,
        )

    def reserve(self, name: str, description: str = None) -> str:
        """Return the public IP for ``name``, creating it when necessary."""
        try:
            return self.addresses_client.get(resource=name).address
        except NotFound:
            address_resource = AddressResource.new(name=name, description=description)
            try:
                self.addresses_client.create(
                    resource_name=name,
                    address_resource=address_resource,
                    wait=True,
                )
            except Conflict:
                # Another idempotent worker reserved it between GET and INSERT.
                pass
            return self.addresses_client.get(resource=name).address

    def get(self, name: str) -> str | None:
        """Return an existing address without creating a missing reservation."""
        try:
            return self.addresses_client.get(resource=name).address
        except NotFound:
            return None

    def release(self, name: str) -> bool:
        """Release ``name``. A missing address is already in the desired state."""
        try:
            deleted = self.addresses_client.delete(resource_name=name, wait=True)
            if not deleted:
                raise ConnectionError(
                    f'Timed out releasing external address {name}'
                )
        except NotFound:
            self.logger.info(f"{self.class_name}:{name} - Address already deleted")
        return True

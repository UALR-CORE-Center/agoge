from typing import List
from google.cloud.compute_v1 import Instance
from google.cloud.compute_v1.types import Metadata, Items


class InstanceResource:
    """Builds and configures Compute Engine `Instance` resources.

    This class provides a helper for constructing an
    :class:`google.cloud.compute_v1.Instance` object with fields like
    machine type, disks, metadata, tags, network interfaces, etc.
    It does **not** itself create the instance in Google Cloud; rather,
    it returns an Instance proto message that you can pass to an
    InstancesClient method (e.g., `insert`) to actually create the VM.
    """

    def __init__(self, zone: str) -> None:
        """Initializes the InstanceResource with a default zone.

        Args:
            zone (str):
                The name of the zone in which to build the Instance resource.
                For example: "us-central1-a".
        """
        self.zone = zone

    def new(
        self,
        name: str,
        disks: List,
        machine_type: str,
        metadata: List,
        service_accounts: str,
        min_cpu_platform: str = None,
        tags: dict = None,
        advanced_machine_features: dict = None,
        description: str = None,
        network_interfaces: List = None,
        source_machine_image: str = None,
        can_ip_forward: bool = False,
    ) -> Instance:
        """Constructs an Instance proto message with specified configuration.

        This method sets up the core fields for an Instance—such as machine type,
        attached disks, metadata, and optional features like network interfaces
        and advanced machine settings.

        Args:
            name (str):
                The name for the instance. Must be unique within the project
                and zone.
            disks (List):
                A list of disk configurations (e.g., :class:`google.cloud.compute_v1.AttachedDisk`
                objects) to attach to the instance.
            machine_type (str):
                The machine type name (e.g., "n1-standard-1") without the full path.
                This method will prepend "zones/{self.zone}/machineTypes/" internally.
            metadata (List):
                The instance metadata, typically a list of key-value pairs or
                a :class:`google.cloud.compute_v1.Metadata` object.
            service_accounts (str):
                The service account configuration for the instance.
                Typically, a JSON or string describing the service account(s).
                (In practice, you might want to pass a list of
                :class:`google.cloud.compute_v1.ServiceAccount` objects.)
            min_cpu_platform (str, optional):
                Minimum CPU platform. For example, "Intel Haswell" or "Automatic".
            tags (dict, optional):
                Network tags to assign to the instance.
                For example: {"items": ["web-server", "internal"]}
            advanced_machine_features (dict, optional):
                Advanced machine features such as number of threads per core,
                etc. Typically, a dictionary that matches
                :class:`google.cloud.compute_v1.AdvancedMachineFeatures`.
            description (str, optional):
                A description of the instance.
            network_interfaces (List, optional):
                Configuration for network interfaces, typically a list of
                :class:`google.cloud.compute_v1.NetworkInterface` objects.
            source_machine_image (str, optional):
                A URL referencing an existing machine image from which to
                create the instance.
            can_ip_forward (bool, optional):
                If True, the instance can send and receive packets with
                non-matching destination or source IPs. Defaults to False.

        Returns:
            Instance:
                A configured :class:`google.cloud.compute_v1.Instance`
                message. This does not create the resource in GCP. You must
                pass it to something like ``InstancesClient.insert()`` to
                actually provision the VM.
        """
        instance_resource = Instance(
            name=name,
            disks=disks,
            machine_type=f"zones/{self.zone}/machineTypes/{machine_type}",
            metadata=metadata,
            can_ip_forward=can_ip_forward,
            service_accounts=service_accounts,
            zone=self.zone
        )

        # Set optional fields if provided.
        if min_cpu_platform:
            instance_resource.min_cpu_platform = min_cpu_platform
        if tags:
            instance_resource.tags = tags
        if advanced_machine_features:
            instance_resource.advanced_machine_features = advanced_machine_features
        if description:
            instance_resource.description = description
        if network_interfaces:
            instance_resource.network_interfaces = network_interfaces
        if source_machine_image:
            instance_resource.source_machine_image = source_machine_image

        return instance_resource

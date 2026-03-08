from google.cloud.compute_v1 import Disk

from common.constants.google import ImageSource


class DiskResource:
    """Creates and configures Disk resources for Google Cloud Compute Engine.

    This class abstracts the construction of a Disk proto message (using
    google.cloud.compute_v1.Disk) for various source types (e.g., disk, snapshot,
    or image). It can be used to set a name, size, description, and data source
    for the Disk resource.
    """

    def __init__(self, project: str, zone: str) -> None:
        """Initializes the DiskResource.

        Args:
            project (str):
                The Google Cloud project ID where the disk will be created.
            zone (str):
                The zone within the project where the disk will be created.
        """
        self.project = project
        self.zone = zone

    def new(
        self,
        name: str,
        size_gb: int = 50,
        source: str = None,
        source_type: ImageSource = ImageSource.IMAGE,
        description: str = None,
    ) -> Disk:
        """Constructs a Disk proto message with specified configuration.

        If a source is provided, the disk will be created from that source
        (disk, snapshot, or image). Otherwise, a new blank disk is created
        with a default disk type of pd-standard.

        Args:
            name (str):
                The name to assign to the disk resource.
            size_gb (int, optional):
                The size in gigabytes for the disk. Defaults to 50.
            source (str, optional):
                The source disk, snapshot, or image URL from which to create
                the disk. If None, a new blank disk is created. Defaults to None.
            source_type (ImageSource, optional):
                An enum indicating whether 'source' refers to a disk,
                snapshot, or image. Defaults to ImageSource.IMAGE.
            description (str, optional):
                A description for the disk. Defaults to None.

        Returns:
            Disk:
                A configured google.cloud.compute_v1.Disk instance, ready
                for insertion via the DisksClient or relevant methods.
        """
        # Create the base disk resource with name and size.
        disk_resource = Disk(
            name=name,
            size_gb=size_gb,
        )

        # Optionally set the disk description.
        if description:
            disk_resource.description = description

        # If source is provided, set the corresponding Disk field.
        if source:
            if source_type == ImageSource.DISK:
                disk_resource.source_disk = source
            elif source_type == ImageSource.SNAPSHOT:
                disk_resource.source_snapshot = source
            else:
                disk_resource.source_image = source
        else:
            # If no source is provided, use a default disk type of pd-standard.
            disk_resource.type_ = (
                f"projects/{self.project}/zones/{self.zone}/diskTypes/pd-standard"
            )

        return disk_resource

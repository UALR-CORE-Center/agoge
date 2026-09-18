from google.cloud.compute_v1 import AttachedDisk, AttachedDiskInitializeParams

from common.constants.google import ImageSource, AttachedDiskMode


class AttachedDiskResource:
    """A helper class for building AttachedDisk resources for Compute Engine.

    Provides methods to create and initialize :class:`google.cloud.compute_v1.AttachedDisk`
    objects as well as their initialization parameters.
    """

    def __init__(self, zone: str = None) -> None:
        """Initializes the AttachedDiskResource helper.

        Args:
            zone (str, optional):
                The zone in which the disk will be created, if relevant.
                Defaults to None. This may be used for constructing disk paths
                or resources in some use cases.
        """
        self.zone = zone

    def new(
        self,
        device_name: str = None,
        disk_size_gb: int = None,
        boot: bool = True,
        auto_delete: bool = True,
        source: str = None,
        initialize_params: AttachedDiskInitializeParams = None,
        mode: AttachedDiskMode = AttachedDiskMode.READ_WRITE,
    ) -> AttachedDisk:
        """Generates an AttachedDisk resource.

        Args:
            device_name (str, optional):
                The device name for this disk within the instance. Defaults to None.
            disk_size_gb (int, optional):
                The size of the disk in GB. Defaults to None.
            boot (bool, optional):
                Indicates whether this disk should be used as a boot disk.
                Defaults to True.
            auto_delete (bool, optional):
                If True, the disk is automatically deleted when the instance
                is deleted. Defaults to True.
            source (str, optional):
                URL of existing disk resource
            initialize_params (AttachedDiskInitializeParams, optional):
                Initialization parameters for the disk, such as the source image
                or snapshot, disk size, and disk name. Defaults to None.
            mode (AttachedDiskMode, optional):
                Specifies the mode in which to attach the disk. Use
                :attr:`AttachedDiskMode.READ_WRITE` or
                :attr:`AttachedDiskMode.READ_ONLY`. Defaults to
                :attr:`AttachedDiskMode.READ_WRITE`.

        Returns:
            AttachedDisk:
                A configured :class:`google.cloud.compute_v1.AttachedDisk` instance.
        """
        attached_disk = AttachedDisk(
            boot=boot,
            auto_delete=auto_delete,
            mode=mode.value,
        )
        if device_name:
            attached_disk.device_name = device_name
        if disk_size_gb:
            attached_disk.disk_size_gb = disk_size_gb
        if initialize_params:
            attached_disk.initialize_params = initialize_params
        if source:
            attached_disk.source = source

        return attached_disk

    def initialized_params(
        self,
        source: str,
        source_type: ImageSource = ImageSource.IMAGE,
        description: str = None,
        disk_name: str = None,
        disk_size_gb: int = None,
    ) -> AttachedDiskInitializeParams:
        """Generates initialization parameters for an AttachedDisk resource.

        This is typically used when you want to create a new disk from a snapshot
        or image during initial instance creation, and want to
        specify disk size, name, or description.

        Args:
            source (str):
                The URL of the source image or snapshot from which to
                initialize the disk.
            source_type (ImageSource, optional):
                Specifies whether the source refers to a disk image or
                a snapshot. Must be one of the enumeration values in
                :class:`ImageSource`. Defaults to :attr:`ImageSource.IMAGE`.
            description (str, optional):
                An optional description of the disk being created.
                Defaults to None.
            disk_name (str, optional):
                An optional name for the new disk. Defaults to None.
            disk_size_gb (int, optional):
                The size of the disk in GB. Defaults to None.

        Returns:
            AttachedDiskInitializeParams:
                A configured :class:`google.cloud.compute_v1.AttachedDiskInitializeParams`
                instance that can be attached to a new or existing
                :class:`google.cloud.compute_v1.AttachedDisk`.
        """
        if not isinstance(source, str) or not source.strip():
            raise ValueError('A non-empty image or snapshot source is required to initialize a disk.')
        source = source.strip()
        init_params = AttachedDiskInitializeParams()
        if source_type == ImageSource.SNAPSHOT:
            init_params.source_snapshot = source
        else:
            init_params.source_image = source

        if description:
            init_params.description = description
        if disk_size_gb:
            init_params.disk_size_gb = disk_size_gb
        if disk_name:
            init_params.disk_name = disk_name

        return init_params

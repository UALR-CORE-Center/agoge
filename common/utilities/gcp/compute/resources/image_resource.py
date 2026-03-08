from google.cloud.compute_v1 import Image

from common.constants.google import ImageSource


class ImageResource:
    """Builds and configures Compute Engine `Image` resources.

    This class provides a helper for constructing an
    :class:`google.cloud.compute_v1.Image` object with fields.
    It does **not** itself create the image in Google Cloud; rather,
    it returns an Image proto message that you can pass to an
    ImagesClient method (e.g., `insert`) to actually create the Image.
    """

    def __init__(self, zone: str) -> None:
        """Initializes the ImageResource with a default zone.

        Args:
            zone (str):
                The name of the zone in which to build the Image resource.
                For example: "us-central1-a".
        """
        self.zone = zone

    def new(
        self,
        name: str,
        description: str = None,
        disk_size_gb: int = None,
        source: str = None,
        source_type: ImageSource = ImageSource.IMAGE,
        zone: str = None,
    ) -> Image:
        """Constructs an Image proto message with specified configuration.

        This method sets up the core fields for an Image—such as source types,
         metadata, and optional features like description
        and advanced machine settings.

        Args:
            name (str):
                The name for the image. Must be unique within the project
                and zone.
            description (str, optional):
                A description of the image.
            source (str, optional):
                full or partial URL to cloud resource
            source_type (str, optional):
                Enum of expected source type (RAW, IMAGE, SNAPSHOT)
            disk_size_gb (int, optional):
                Size of image to use. If source_type is an IMAGE, defaults to source IMAGE size
            zone (str, optional):
                The name of the zone in which to build the Image resource. Defaults to project zone

        Returns:
            Image:
                A configured :class:`google.cloud.compute_v1.Image`
                message. This does not create the resource in GCP. You must
                pass it to something like ``ImagesClient.insert()`` to
                actually provision the Image.
        """
        image_resource = Image(name=name)

        # Set optional fields if provided.
        if description:
            image_resource.description = description
        if disk_size_gb:
            image_resource.disk_size_gb = int(disk_size_gb)
        if zone:
            image_resource.zone = zone
        else:
            image_resource.zone = self.zone

        if source:
            if source_type == ImageSource.IMAGE:
                image_resource.source_image = source
            elif source_type == ImageSource.SNAPSHOT:
                image_resource.source_snapshot = source
            elif source_type == ImageSource.DISK:
                image_resource.source_disk = source
            else:
                raise ValueError(
                    f"Unsupported source for image object {source}. Must be one of "
                    f"[{ImageSource.SNAPSHOT.name}, {ImageSource.IMAGE.name}, {ImageSource.DISK.name}"
                )

        return image_resource

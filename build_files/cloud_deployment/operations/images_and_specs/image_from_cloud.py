# WARNING: This is deprecated and is currently replaced by ComputerImageSync and CustomImageImportManager class
from enum import Enum
from typing import Tuple, Any

from base_image_to_cloud import BaseImageToCloud


class ImageExistsStates(Enum):
    SERVER = 0
    IMAGE = 1
    NOT_FOUND = 2


class ImageFromCloud(BaseImageToCloud):
    def __init__(self):
        super().__init__()
        self.message.warning(f'this class has been replaced with `CustomImageImportManager` and `ComputerImageSync`')

    def _additional_sync_tasks(self):
        self.server_name, self.image_name = self.get_image_name()

    def _import(self, image_url: str) -> bool:
        pass

    def _cleanup_tasks(self) -> None:
        if self.old_image:
            if self.message.confirm(f"Image copied from {self.server_name} to {self.image_name}."
                                    f" Would you like to delete the image under name ", self.server_name):
                self.delete_image(self.old_image)
            self.old_image = None

    def _image_exists(
        self,
        server_name: str,
        image_name: str
    ) -> Tuple[ImageExistsStates, Any]:
        # Prefer image lookup with image name
        image_from_image = self._get_image(image_name=image_name, retry=False)
        if image_from_image:
            return ImageExistsStates.IMAGE, image_from_image

        # Image not found. Perform lookup with server name instead
        image_from_server = self._get_image(image_name=server_name, retry=False)
        if image_from_server:
            return ImageExistsStates.SERVER, image_from_server

        # No image found
        return ImageExistsStates.NOT_FOUND, None

    def get_image_name(self) -> Tuple[str, str]:
        while True:
            name = str(input("Enter image name: "))

            if not self._validate_image_name(name):
                continue

            if name.startswith("image-"):
                image_name = name
                server_name = name.split('image-')[1]

                # Perform image lookup
                image_exists, image = self._image_exists(server_name, image_name)
            else:
                server_name = name
                image_name = f'image-{name}'

                # Ensure that prefixed name does not exceed cloud-defined limits
                if not self._validate_image_name(image_name):
                    continue

                # Perform image lookup
                image_exists, image = self._image_exists(server_name, image_name)

            if image_exists == ImageExistsStates.NOT_FOUND:
                self.message.warning("Could not find a compute image associated with given name.")
                continue

            if self.message.confirm("Set image to ", name):
                if image_exists == ImageExistsStates.SERVER:
                    self.message.warning(
                        f"Images not prefixed with `image-` will need to be copied first before continuing."
                    )
                    if self.message.confirm(f"Do you want to copy the image from {name} to ", image_name):
                        if self.copy_image(image, destination_name=image_name):
                            return server_name, image_name
                        else:
                            exit()
                elif image_exists == ImageExistsStates.IMAGE:
                    return server_name, image_name

    def get_image_os(self, image: Any) -> Tuple[str, str]:
        image_licences = image.licenses
        if image_licences:
            for image_license in image_licences:
                license_path = image_license.split("/")
                project = license_path[1]
                family = license_path[-1]
                if project not in [self.projects.WINDOWS, self.projects.SQL_SERVER]:
                    return self.generic_family.LINUX, family
                else:
                    return self.generic_family.WINDOWS, family
        else:
            self.message.warning(f"Could not find any licenses for selected image!")
            return self._get_image_os()

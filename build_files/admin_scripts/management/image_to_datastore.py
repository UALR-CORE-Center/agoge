import json
from dataclasses import dataclass
from typing import Optional

from cloud_fn_utilities.globals import ImageStates, ServerStates
from main_app.api import DataStoreManager
from main_app.api.utilities.globals import DatastoreKeyTypes
from main_app.api import CloudEnv


class ImageToDatastore:
    @dataclass
    class Image:
        image: str
        add_disk: int
        disks: list
        os: str
        human_interaction: dict
        description: str
        labels: list[str]
        tags: list[str]
        name: str
        machine_type: str
        self_link: str
        status: str = ImageStates.CHECKED_IN.value
        state: Optional[ServerStates] = ServerStates.START.value
        dns_record: Optional[str] = None
        base_family: Optional[str] = None

    def __init__(
        self,
        file: str
    ) -> None:
        self.images = {}
        self.existing_images = None
        self.file = file
        self.ds = DataStoreManager()
        self.entity_list = []
        self.env = CloudEnv()

    def run(self) -> None:
        self.existing_images = DataStoreManager(key_type=DatastoreKeyTypes.IMAGE).query()
        images_to_store = self._load_from_json()
        if len(images_to_store) > 0:
            self._convert_to_dict(images_to_store)
            self._put_in_datastore()

    def _convert_to_dict(
            self,
            images_to_store: list
    ) -> None:
        self.images = {}
        for image in images_to_store:
            new_image = {
                'name': image.name,
                'add_disk': image.add_disk,
                'disks': image.disks,
                'os': str(image.os).lower(),
                'human_interaction': image.human_interaction,
                'description': image.description,
                'services': image.services,
                'tags': image.tags,
                'machine_type': image.machine_type,
                'dns_record': image.dns_record,
                'image': image.image,
                'self_link': image.self_link,
                'in_use_by': None,
                'status': image.status,
                'state': image.state,
                "base_family": image.base_family
            }
            self.images[str(new_image['name'])] = new_image

    def _load_from_json(self) -> list:
        image = self.Image

        try:
            with open(self.file, 'r') as file:
                json_data = json.load(file)
                json_images = json_data.get('images', [])
        except FileNotFoundError:
            raise FileNotFoundError(f"Invalid or missing file: {self.file}")
        except ValueError:
            raise ValueError(f"JSON decoding failed. Does {self.file} contain valid JSON?")

        # Load JSON into Image dataclass
        for json_image in json_images:
            new_image = image(
                image=json_image['image'],
                add_disk=json_image['add_disk'],
                disks=json_image['disks'],
                os=json_image['os'],
                human_interaction=json_image['human_interaction'],
                description=json_image['description'],
                services=json_image['services'],
                tags=json_image['tags'],
                name=json_image['name'],
                machine_type=json_image['machineType'],
                dns_record="",
                status=ImageStates.CHECKED_IN.value,
                self_link=self._get_self_link(json_image),
                base_family=json_image['base_family'],
            )
            self.images[str(new_image.name)] = new_image

        self.images = self._cleaned_servers(self.images)
        return self.images

    def _put_in_datastore(self) -> None:
        for image_to_entity in self.images.values():
            server_name = image_to_entity['name']
            self.ds.set(key_type=DatastoreKeyTypes.IMAGE.value, key_id=str(server_name))
            image_entity = self.ds.entity(image_to_entity)
            self.entity_list.append(image_entity)
        self.ds.put_multi(self.entity_list)

    def _cleaned_servers(
            self,
            servers: dict
    ) -> list:
        """
        Removes any duplicate images from input servers

        Returns: List of safe servers to sync with Datastore
        """
        cleaned = []
        existing_images = {image['name']: image for image in self.existing_images}
        for key, val in servers.items():
            if key in existing_images:
                continue
            else:
                cleaned.append(val)
        return cleaned

    @staticmethod
    def _get_self_link(json_image) -> str:
        self_link = json_image.get('self_link')
        if not self_link:
            prefix = f"https://www.googleapis.com/compute/v1/"
            path = json_image['disks'][0]["initializeParams"]["sourceImage"]
            return f"{prefix}{path}"
        return self_link


if __name__ == '__main__':
    ids = ImageToDatastore("build_files/admin_scripts/management/image_objects/package.json")
    ids.run()

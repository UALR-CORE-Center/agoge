from google.api_core.exceptions import NotFound as GoogleNotFound

from cloud_fn_utilities.course_objects.compute.base_compute_manager import BaseComputeManager
from cloud_fn_utilities.gcp.dns_manager import DnsManager
from cloud_fn_utilities.server_specific.assessment_manager import AssessmentManager
from cloud_fn_utilities.state_managers import ServerStateManager
from common.constants.build_constants import BuildConstants
from common.constants.database import DbCollections, DatabaseTypes, DATABASE_NAME
from common.constants.pub_sub import PubSub
from common.document_database import DocumentDatabaseFactory
from common.exceptions import Conflict, NotFound, BadRequest, BaseAgogeException
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import Logger
from common.utilities.gcp.compute.resources.attached_disk_resource import AttachedDiskResource
from common.utilities.gcp.compute.resources.disks_resource import DiskResource
from common.utilities.gcp.compute.resources.network_interface_resource import NetworkInterfaceResource


class LabServerManager(BaseComputeManager):
    def __init__(self, env_dict: dict = None):
        super().__init__(env_dict=env_dict, images=True, disks=True)
        self.logger = Logger(self.log_name, class_name=self.class_name)
        self.env = CloudEnv(env_dict=env_dict) if env_dict else CloudEnv()
        self.env_dict = self.env.get_env()
        self.course_object = PubSub.CourseObjects.LAB_SERVER
        self.dns_manager = DnsManager(env_dict=self.env_dict)
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME
        )
        self.state_manager = ServerStateManager()
        self.collection = DbCollections.SERVER

    def load(
        self,
        server_name: str,
        network_prefix: str = None,
        **kwargs
    ) -> None:
        if 'server_spec' in kwargs:
            server_spec = kwargs['server_spec']
        else:
            server_spec = self.db.get(collection_name=self.collection, doc_id=server_name)

        if not server_spec:
            self.logger.error(f"{self.class_name}:{self.server_name} - No record exists for compute record!")
            raise LookupError

        self._load_lab_server(server_name, server_spec=server_spec, network_prefix=network_prefix)

        self.state_manager.set_build_record(server_name)
        self.assessment = AssessmentManager(
            build_id=self.parent_build_id,
            build_type=self.parent_build_type,
            env_dict=self.env_dict
        )

    def build(self) -> None:
        """Builds an individual server based on the server specifications."""
        self._build_server()

    def start(self) -> None:
        self._start_server()

    def stop(self) -> None:
        self._stop_server()

    def delete(
        self,
        delete_image: bool = False,
        state_transition: bool = True,
    ) -> bool:
        """
        Deletes a compute instance based on the specification in the database document
        with the name server_name.

        Args:
            delete_image (bool): Delete image and image records; Defaults to False
            state_transition (): Include state transition; Defaults to True

        Returns:

        """
        if state_transition:
            self.state_manager.state_transition(self.s.DELETING)

        self.logger.info(f'{self.class_name}:{self.server_name} - Deleting server')
        try:
            deleted = self.compute_instance.delete(resource_name=self.server_name, wait=True)
            if not deleted:
                if state_transition:
                    self.state_manager.state_transition(self.s.BROKEN)
                self.logger.error(
                    f'{self.class_name}:{self.server_name} - Server deletion timed out.'
                )
                return False
        except (NotFound, GoogleNotFound):
            # If the resource can't be found, it was either already deleted or never created
            self.logger.info(
                f'{self.class_name}:{self.server_name} - Server is already absent; '
                'continuing with the rebuild.'
            )
        except (BadRequest, BaseAgogeException):
            if state_transition:
                self.state_manager.state_transition(self.s.BROKEN)
            return False

        if state_transition:
            self.state_manager.state_transition(self.s.DELETED)

        # Check if a dns record exists for deletion
        if dns_record := self._dns_record():
            self.logger.info(f'{self.class_name}:{self.server_name} - Deleting DNS record for server, '
                             f'{self.parent_build_id}')
            self.dns_manager.delete_dns(record_name=dns_record)

        return True

    def nuke(self) -> None:
        """
        Deletes a server based on the specification in the database with the name server_name.
        Then rebuilds the server.
        """
        if not self.delete():
            raise RuntimeError(
                f"Cannot rebuild {self.server_name}: server deletion failed."
            )
        self.build()

    def _add_disks(self) -> None:
        disks = None
        if self.server_spec.build_type != BuildConstants.ServerBuildType.MACHINE_IMAGE:
            boot_disk = self._get_boot_disk()
            disks = [boot_disk]

            # Add any additional disks
            add_disk = self.server_spec.add_disk
            if add_disk != 0:
                # Create the AttachedDisk object
                attached_disk_resource = AttachedDiskResource()
                new_attached_disk = attached_disk_resource.new(boot=False, auto_delete=True)
                disks.append(new_attached_disk)

                try:
                    # Now build the disk, so it is ready to attach when the server is built.
                    disk_name = f'{self.server_name}-disk-1'
                    new_disk = DiskResource(project=self.env.project, zone=self.env.zone).new(
                        name=disk_name,
                        size_gb=add_disk
                    )
                    self.compute_disk.create(
                        resource_name=disk_name,
                        wait=True,
                        disk=new_disk
                    )
                except Conflict:
                    # Disk already exists. Ignore Disk.insert request
                    pass

        self.server_spec.disks = disks

    def _add_metadata(self):
        metadata = {'items': []}
        if self.server_spec.metadata:
            metadata['items'].append(self.server_spec.metadata)
        if self.server_spec.ssh_keys:
            metadata['items'].append({"key": "ssh-keys", "value": self._ssh_keys()})
        if self.server_spec.guacamole_startup_script:
            metadata['items'].append({"key": "startup-script", "value": self.server_spec.guacamole_startup_script})
        assessment_startup_script = self.assessment.get_startup_scripts(server_name=self.server_spec.name)
        if assessment_startup_script:
            metadata['items'].append(assessment_startup_script)
        self.server_spec.metadata = metadata

    def _add_nics(self) -> None:
        network_interface_resource = NetworkInterfaceResource(region=self.env.region, project=self.env.project)
        network_prefix = self.server_spec.network_prefix
        network_interfaces = []

        for network in self.server_spec.nics:
            access_configs = None
            internal_ip = None
            alias_ip_ranges = None

            if network.get("external_nat", None):
                access_configs = [
                    network_interface_resource.access_config(type_='ONE_TO_ONE_NAT', name='External NAT')
                ]

            if 'internal_ip' in network:
                internal_ip = network['internal_ip']

            if ip_aliases := network.get('ip_aliases', None):
                self.ip_aliases = True
                alias_ip_ranges = []
                for ipaddr in ip_aliases:
                    alias_ip_range = network_interface_resource.alias_ip_range(ip_cidr_range=f'{ipaddr}/32')
                    alias_ip_ranges.append(alias_ip_range)

            network_interface = network_interface_resource.new(
                network_name=f'{network_prefix}-{network["network"]}',
                subnetwork_name=f'{network_prefix}-{network["network"]}-{network["subnet_name"]}',
                access_configs=access_configs,
                alias_ip_ranges=alias_ip_ranges,
                internal_ip=internal_ip
            )
            network_interfaces.append(network_interface)
        self.server_spec.network_interfaces = network_interfaces

    def _dns_record(self) -> str | bool:
        return self._server_dns_record()

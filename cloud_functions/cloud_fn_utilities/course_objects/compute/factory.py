from typing import Union

from common.constants.pub_sub import PubSub
from common.utilities.gcp.cloud_logger import LoggerNames, Logger
from .image_template_manager import ImageTemplateManager
from .lab_server_manager import LabServerManager
from .snapshot_manager import SnapshotManager


class ComputeManagerFactory:
    @staticmethod
    def create_manager_object(
        manager_type: PubSub.CourseObjects = PubSub.CourseObjects.LAB_SERVER,
        log_name: str = LoggerNames.CLOUD_FN,
        env_dict: dict = None,
        debug: bool = False,
        **kwargs
    ) -> Union[ImageTemplateManager, LabServerManager, SnapshotManager]:
        """
        Args:
            manager_type (PubSub.CourseObjects): Enumerator declaring which type of manager class to use.
                    defaults to `PubSub.CourseObjects.LAB_SERVER`
            log_name (str, optional): Enumerator of log name to use. Defaults to `LoggerNames.CLOUD_FN`
            env_dict (dict, optional): Optional dictionary of cloud environment attributes
            kwargs (dict, optional): Additional arguments to pass to ImageTemplateManager. Including
                - user (str)
                - delete_previous (bool)
                - source_image_project (str)
                - debug (bool)
        """
        logger = Logger(log_name)
        logger.debug(f'ComputeManagerObject:create_manager_object - '
                     f'Creating compute manager instance of type: {manager_type.name}')
        if manager_type == PubSub.CourseObjects.TEMPLATE_SERVER:
            return ImageTemplateManager(env_dict=env_dict, debug=debug, **kwargs)
        elif manager_type == PubSub.CourseObjects.LAB_SERVER:
            return LabServerManager(env_dict=env_dict)
        elif manager_type == PubSub.CourseObjects.SNAPSHOT:
            server_type = PubSub.CourseObjects.LAB_SERVER
            if kwargs:
                if 'server_type' in kwargs:
                    server_type = kwargs['server_type']
            return SnapshotManager(env_dict=env_dict, server_type=server_type)
        raise ValueError(f'Unsupported compute manager type: {manager_type.value}')

# [ eof ]

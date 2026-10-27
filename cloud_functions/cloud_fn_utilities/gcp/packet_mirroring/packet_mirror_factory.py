from common.constants.build_constants import BuildConstants
from common.utilities.gcp.cloud_logger import Logger, LoggerNames

from .community_mirroring import CommunityBuildMirroring
from .solo_mirroring import SoloBuildMirroring


class NoPacketMirroring:
    """Lifecycle adapter for a specification with no mirrored resources.

    Keep disabled mirroring free of GCP clients and requests. In particular,
    starting a student session must not look for a collector that was never
    provisioned for its lab.
    """

    def create(self):
        pass

    def start(self):
        pass

    def stop(self):
        pass

    def delete(self):
        pass


class PacketMirrorFactory:
    cloud_log = Logger(LoggerNames.CLOUD_FN)

    @classmethod
    def create_packet_mirror_object(
        cls,
        build_id: str,
        build_type: str = BuildConstants.UnitType.SOLO.value,
        build: dict = None,
        env_dict: dict = None,
        debug: bool = False
    ) -> SoloBuildMirroring | CommunityBuildMirroring | NoPacketMirroring:
        """Load configured mirroring, or a cloud-free adapter when disabled.

        Args:
            build_id (str): The identifier for the build to be associated.
            build_type (str): Type of build associated with build_id.
                Defaults to BuildConstants.UnitType.SOLO
            build (dict, optional): Build object associated with build_id to help
                reduce database queries
            env_dict (dict, optional): Dictionary of environment variables. Defaults to None.
            debug (bool, optional): Enables debug mode if set to True. Defaults to False.

        Returns:
            A configured mirror manager or NoPacketMirroring.

        Raises:
            ValueError: If invalid class attr `build_type`
        """
        cls.cloud_log.class_name = cls.__name__
        if build_type not in (BuildConstants.UnitType.SOLO.value, BuildConstants.UnitType.COMMUNITY.value):
            cls.cloud_log.error(f'{cls.__name__}:{build_id} - Invalid build_type for '
                                f'packet mirroring, {build_type}')
            raise ValueError
        if isinstance(build, dict):
            mirrored_subnets = any(
                subnet.get('promiscuous_mode', False)
                for network in build.get('networks') or []
                for subnet in network.get('subnets') or []
            )
            mirrored_servers = any(
                server.get('promiscuous_mode', False)
                for server in build.get('servers') or []
            )
            if not mirrored_subnets and not mirrored_servers:
                return NoPacketMirroring()
        if build_type == BuildConstants.UnitType.SOLO.value:
            return SoloBuildMirroring(
                build_id=build_id,
                build=build,
                env_dict=env_dict,
                debug=debug
            )
        elif build_type == BuildConstants.UnitType.COMMUNITY.value:
            return CommunityBuildMirroring(
                build_id=build_id,
                build=build,
                env_dict=env_dict,
                debug=debug
            )

# [ eof ]

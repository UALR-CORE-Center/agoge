class Scopes:
    GLOBAL = 'global'
    REGION = 'region'
    ZONE = 'zone'


class MirroredResource:
    """Enum for different types of mirrored resources."""
    SUBNETWORK = 'subnetworks'
    INSTANCE = 'instances'
    TAGS = 'tags'


class StartupScripts:
    """Class for startup scripts."""
    UNIX = """#! /bin/bash
    echo "{BUILD_ID}"
    """
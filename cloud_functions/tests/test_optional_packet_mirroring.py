"""Disabled packet mirroring must never contact an unprovisioned collector."""
from unittest.mock import Mock, patch

import pytest

from cloud_fn_utilities.gcp.packet_mirroring import packet_mirror_factory as module


@pytest.mark.parametrize('build_type', ['solo', 'community'])
@pytest.mark.parametrize('build', [
    {},
    {'networks': None, 'servers': None},
    {'networks': [{'name': 'external', 'subnets': None}]},
    {'networks': [{'name': 'external', 'subnets': [
        {'name': 'default', 'promiscuous_mode': False}]}],
     'servers': [{'name': 'wireguard', 'wireguard_gateway': True,
                  'promiscuous_mode': False}]},
])
def test_unmirrored_build_lifecycle_never_constructs_a_cloud_mirror(build_type, build):
    with patch.object(module, 'SoloBuildMirroring') as solo, \
         patch.object(module, 'CommunityBuildMirroring') as community:
        mirror = module.PacketMirrorFactory.create_packet_mirror_object(
            'abcdefghij', build_type=build_type, build=build, env_dict={'project': 'test-dev-787001'})
        for operation in ('create', 'start', 'stop', 'delete'):
            getattr(mirror, operation)()

    assert isinstance(mirror, module.NoPacketMirroring)
    solo.assert_not_called()
    community.assert_not_called()


@pytest.mark.parametrize('build_type,selected', [('solo', 'SoloBuildMirroring'),
                                               ('community', 'CommunityBuildMirroring')])
@pytest.mark.parametrize('build', [
    {'networks': [{'subnets': [{'name': 'capture', 'promiscuous_mode': True}]}]},
    {'servers': [{'name': 'sensor', 'promiscuous_mode': True}]},
])
def test_configured_mirroring_selects_the_requested_manager_and_preserves_errors(build_type, selected, build):
    failure = RuntimeError('Configured packet mirror is unavailable')
    mirror = Mock()
    mirror.start.side_effect = failure
    with patch.object(module, selected, return_value=mirror) as constructor:
        result = module.PacketMirrorFactory.create_packet_mirror_object(
            'abcdefghij', build_type=build_type, build=build,
            env_dict={'project': 'test-project'}, debug=True)
        with pytest.raises(RuntimeError) as error:
            result.start()

    assert error.value is failure
    constructor.assert_called_once_with(
        build_id='abcdefghij', build=build, env_dict={'project': 'test-project'}, debug=True)


def test_unknown_specification_retains_manager_database_loading():
    with patch.object(module, 'CommunityBuildMirroring') as constructor:
        result = module.PacketMirrorFactory.create_packet_mirror_object(
            'abcdefghij', build_type='community', build=None)

    assert result is constructor.return_value
    constructor.assert_called_once_with(build_id='abcdefghij', build=None, env_dict=None, debug=False)


def test_disabled_specification_does_not_hide_an_invalid_manager_type():
    with pytest.raises(ValueError):
        module.PacketMirrorFactory.create_packet_mirror_object('abcdefghij', build_type='invalid', build={})

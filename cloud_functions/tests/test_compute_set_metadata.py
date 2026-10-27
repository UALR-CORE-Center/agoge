"""ComputeInstanceAPI.set_metadata merges under a fingerprint guard, with real Compute protos and no cloud calls."""

from types import SimpleNamespace
from unittest.mock import Mock

from google.api_core.exceptions import NotFound as GoogleNotFound
from google.api_core.exceptions import PreconditionFailed as GooglePreconditionFailed
from google.cloud.compute_v1 import Instance, Items, Metadata
import pytest

from common.exceptions import BaseAgogeException, NotFound, PreconditionFailed
from common.utilities.gcp.compute.compute_instance import ComputeInstanceAPI


def instance_with(fingerprint, **metadata):
    return Instance(
        name='vm-1',
        metadata=Metadata(
            fingerprint=fingerprint,
            items=[Items(key=key, value=value) for key, value in metadata.items()],
        ),
    )


@pytest.fixture
def api():
    # Bypass __init__ (it builds Logger and operations clients); keep the real _make_request so 412 mapping is exercised.
    api = object.__new__(ComputeInstanceAPI)
    api.class_name = 'ComputeInstanceAPI'
    api.project = 'test-project'
    api.zone = 'us-central1-a'
    api.resource_type = SimpleNamespace(name='INSTANCE')
    api.logger = Mock()
    api.instance_client = Mock()
    api.instance_client.set_metadata.return_value = SimpleNamespace(name='op-1')
    api.cloud_ops_mgr = Mock()
    api.cloud_ops_mgr.wait.return_value = True
    return api


def sent_metadata(api, call=-1):
    request = api.instance_client.set_metadata.call_args_list[call].kwargs['request']
    return request, {item.key: item.value for item in request.metadata_resource.items}


def test_merge_keeps_unrelated_keys_and_overwrites_named_ones(api):
    api.instance_client.get.return_value = instance_with(
        'fp-1', **{'startup-script': '#!/bin/bash', 'ssh-keys': 'k', 'agoge-ctf-plant': 'old'}
    )

    assert api.set_metadata('vm-1', {'agoge-ctf-plant': 'new', 'enable-guest-attributes': 'TRUE'}) is True

    request, items = sent_metadata(api)
    assert items == {
        'startup-script': '#!/bin/bash',
        'ssh-keys': 'k',
        'agoge-ctf-plant': 'new',
        'enable-guest-attributes': 'TRUE',
    }
    assert request.metadata_resource.fingerprint == 'fp-1'
    assert (request.instance, request.project, request.zone) == ('vm-1', 'test-project', 'us-central1-a')
    api.cloud_ops_mgr.wait.assert_called_once()


def test_remove_drops_only_named_keys_and_ignores_absent_ones(api):
    api.instance_client.get.return_value = instance_with(
        'fp-1', **{'startup-script': 's', 'agoge-ctf-plant': 'payload'}
    )

    api.set_metadata('vm-1', remove=['agoge-ctf-plant', 'never-set'])

    _, items = sent_metadata(api)
    assert items == {'startup-script': 's'}


def test_wait_false_returns_operation_without_polling(api):
    api.instance_client.get.return_value = instance_with('fp-1')

    assert api.set_metadata('vm-1', {'a': '1'}, wait=False).name == 'op-1'
    api.cloud_ops_mgr.wait.assert_not_called()


def test_stale_fingerprint_rereads_once_and_retries_with_fresh_state(api):
    # A concurrent writer added 'ssh-keys' between our read and write; the retry must keep it.
    api.instance_client.get.side_effect = [
        instance_with('fp-1', **{'startup-script': 's'}),
        instance_with('fp-2', **{'startup-script': 's', 'ssh-keys': 'k'}),
    ]
    api.instance_client.set_metadata.side_effect = [
        GooglePreconditionFailed('conditionNotMet'),
        SimpleNamespace(name='op-2'),
    ]

    assert api.set_metadata('vm-1', {'agoge-ctf-plant': 'p'}) is True

    assert api.instance_client.get.call_count == 2
    assert api.instance_client.set_metadata.call_count == 2
    request, items = sent_metadata(api)
    assert request.metadata_resource.fingerprint == 'fp-2'
    assert items == {'startup-script': 's', 'ssh-keys': 'k', 'agoge-ctf-plant': 'p'}


def test_second_stale_fingerprint_raises_without_a_third_attempt(api):
    api.instance_client.get.side_effect = [instance_with('fp-1'), instance_with('fp-2')]
    api.instance_client.set_metadata.side_effect = GooglePreconditionFailed('conditionNotMet')

    with pytest.raises(PreconditionFailed):
        api.set_metadata('vm-1', {'a': '1'})

    assert api.instance_client.set_metadata.call_count == 2


def test_precondition_failed_is_still_a_base_agoge_exception():
    # Before this mapping a 412 surfaced as BaseAgogeException; existing broad handlers must still catch it.
    assert issubclass(PreconditionFailed, BaseAgogeException)


def test_missing_instance_raises_not_found_without_writing(api):
    api.instance_client.get.side_effect = GoogleNotFound('gone')

    with pytest.raises(NotFound):
        api.set_metadata('vm-1', {'a': '1'})

    api.instance_client.set_metadata.assert_not_called()

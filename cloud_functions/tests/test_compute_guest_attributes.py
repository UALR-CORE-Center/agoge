"""ComputeInstanceAPI.get_guest_attributes returns {key: value}, with real Compute protos and no cloud calls."""

from types import SimpleNamespace
from unittest.mock import Mock

from google.api_core.exceptions import NotFound as GoogleNotFound
from google.api_core.exceptions import PermissionDenied as GooglePermissionDenied
from google.cloud.compute_v1 import GuestAttributes, GuestAttributesEntry, GuestAttributesValue, Instance
import pytest

from common.exceptions import BaseAgogeException, NotFound
from common.utilities.gcp.compute.compute_instance import ComputeInstanceAPI


@pytest.fixture
def api():
    # Bypass __init__ (it builds Logger and operations clients); keep the real _make_request so error mapping is exercised.
    api = object.__new__(ComputeInstanceAPI)
    api.class_name = 'ComputeInstanceAPI'
    api.project = 'test-project'
    api.zone = 'us-central1-a'
    api.resource_type = SimpleNamespace(name='INSTANCE')
    api.logger = Mock()
    api.instance_client = Mock()
    api.instance_client.get.return_value = Instance(name='vm-1')
    api.cloud_ops_mgr = Mock()
    return api


def guest_attributes(**entries):
    return GuestAttributes(
        query_path='agoge-ctf/',
        query_value=GuestAttributesValue(
            items=[GuestAttributesEntry(namespace='agoge-ctf', key=k, value=v) for k, v in entries.items()]
        ),
    )


def test_returns_key_value_dict_for_the_query_path(api):
    api.instance_client.get_guest_attributes.return_value = guest_attributes(
        **{'plant-result': 'ok:nonce-1', 'loader-version': '1'}
    )

    assert api.get_guest_attributes('vm-1', query_path='agoge-ctf/') == {
        'plant-result': 'ok:nonce-1',
        'loader-version': '1',
    }
    request = api.instance_client.get_guest_attributes.call_args.kwargs['request']
    assert (request.instance, request.project, request.zone, request.query_path) == (
        'vm-1', 'test-project', 'us-central1-a', 'agoge-ctf/'
    )
    api.instance_client.get.assert_not_called()


def test_project_and_zone_overrides_are_used(api):
    api.instance_client.get_guest_attributes.return_value = guest_attributes()

    api.get_guest_attributes('vm-1', query_path='agoge-ctf/', project='other', zone='europe-west1-b')

    request = api.instance_client.get_guest_attributes.call_args.kwargs['request']
    assert (request.project, request.zone) == ('other', 'europe-west1-b')


def test_response_without_entries_is_empty(api):
    api.instance_client.get_guest_attributes.return_value = GuestAttributes(query_path='agoge-ctf/')

    assert api.get_guest_attributes('vm-1', query_path='agoge-ctf/') == {}


def test_404_for_an_existing_instance_is_empty_and_logs_no_error(api):
    # GCE 404s a namespace the VM has not written to yet; that is "no answer yet", not a failure.
    api.instance_client.get_guest_attributes.side_effect = GoogleNotFound('guest attribute not found')

    assert api.get_guest_attributes('vm-1', query_path='agoge-ctf/') == {}
    api.instance_client.get.assert_called_once()
    api.logger.error.assert_not_called()


def test_404_for_a_missing_instance_raises_not_found(api):
    # A deleted VM must not look like an empty namespace to the 240 s plant poller.
    api.instance_client.get_guest_attributes.side_effect = GoogleNotFound('instance not found')
    api.instance_client.get.side_effect = GoogleNotFound('instance not found')

    with pytest.raises(NotFound):
        api.get_guest_attributes('vm-1', query_path='agoge-ctf/')


def test_other_api_errors_still_raise(api):
    api.instance_client.get_guest_attributes.side_effect = GooglePermissionDenied('denied')

    with pytest.raises(BaseAgogeException):
        api.get_guest_attributes('vm-1', query_path='agoge-ctf/')
    api.instance_client.get.assert_not_called()

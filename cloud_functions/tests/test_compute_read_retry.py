"""BaseComputeAPI resends reads whose pooled HTTPS connection dropped, and never resends writes, with no cloud calls."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import SSLError

from common.utilities.gcp.compute.compute_image import ComputeImageAPI

# What a check-in hit after the half-hour image insert: Google had closed the idle pooled connection
DROPPED = SSLError("SSLEOFError(8, '[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol')")


@pytest.fixture
def api():
    # Bypass __init__ (it builds Logger and operations clients); keep the real _make_request and _send.
    api = object.__new__(ComputeImageAPI)
    api.class_name = 'ComputeImageAPI'
    api.project = 'test-project'
    api.zone = 'us-central1-a'
    api.resource_type = SimpleNamespace(name='IMAGE')
    api.client_type = 'images'
    api.logger = Mock()
    api.cloud_ops_mgr = Mock()
    api.cloud_ops_mgr.wait.return_value = True
    return api


def test_get_resends_after_dropped_connection(api):
    image = SimpleNamespace(status='READY')
    client_request = Mock(side_effect=[DROPPED, image])

    result = api._make_request(client_request=client_request, action='get', resource='image-x', wait=False)

    assert result is image
    assert client_request.call_count == 2
    api.logger.warning.assert_called_once()


def test_guest_attributes_poll_resends_after_dropped_connection(api):
    client_request = Mock(side_effect=[DROPPED, None])

    api._make_request(client_request=client_request, action='get guest attributes', resource='vm-1', wait=False)

    assert client_request.call_count == 2


def test_image_get_survives_dropped_connection(api):
    image = SimpleNamespace(status='READY')
    client = Mock()
    client.get.side_effect = [DROPPED, image]
    api.client = Mock(return_value=client)

    assert api.get('image-x', project='test-project', fallback_to_shared=False) is image
    assert client.get.call_count == 2


def test_get_gives_up_after_retry_attempts(api):
    client_request = Mock(side_effect=DROPPED)

    with pytest.raises(SSLError):
        api._make_request(client_request=client_request, action='get', resource='image-x', wait=False)

    assert client_request.call_count == api.READ_RETRY_ATTEMPTS


@pytest.mark.parametrize('action', ['insert', 'delete', 'create'])
def test_write_is_never_resent(api, action):
    client_request = Mock(side_effect=RequestsConnectionError('reset'))

    with pytest.raises(RequestsConnectionError):
        api._make_request(client_request=client_request, action=action, resource='image-x', wait=False)

    client_request.assert_called_once()

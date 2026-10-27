"""Regressions for diagnosing cross-project image lookups without live GCP."""
from unittest.mock import Mock

import pytest
from google.api_core.exceptions import NotFound as GoogleNotFound

from common.constants.build_constants import BuildConstants
from common.constants.google import ClientType, ResourceType
from common.exceptions import NotFound
from common.utilities.gcp.compute.compute_image import ComputeImageAPI


@pytest.mark.parametrize('fallback_to_shared', [False, True])
def test_missing_image_reports_the_requested_project_for_every_attempt(fallback_to_shared):
    api = object.__new__(ComputeImageAPI)
    api.project = 'test-dev-787001'
    api.zone = 'us-central1-a'
    api.class_name = 'ComputeImageAPI'
    api.client_type = ClientType.IMAGE
    api.resource_type = ResourceType.IMAGE
    api.logger = Mock()
    client = Mock()
    client.get.side_effect = GoogleNotFound('private-sdk-error-body')
    api.client = Mock(return_value=client)

    with pytest.raises(NotFound) as error:
        api.get('image-csec3314-powershell', project='ualr-agoge', fallback_to_shared=fallback_to_shared)

    projects = ['ualr-agoge']
    if fallback_to_shared:
        projects.append(BuildConstants.SharedResourceProjects.MAIN_SHARED_RESOURCE_PROJECT)
    assert [call.kwargs['request'].project for call in client.get.call_args_list] == projects
    request_logs = [call for call in api.logger.error.call_args_list if 'project' in call.kwargs]
    assert [call.kwargs['project'] for call in request_logs] == projects
    for call, project in zip(request_logs, projects):
        assert f'in project {project}.' in call.args[0]
        assert api.project not in call.args[0]
    assert 'ualr-agoge' in str(error.value)
    assert 'private-sdk-error-body' not in str(error.value)
    assert 'private-sdk-error-body' not in str(api.logger.mock_calls)

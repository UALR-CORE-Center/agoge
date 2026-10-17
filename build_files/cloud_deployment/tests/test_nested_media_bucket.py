"""Configure Nested Image Media Bucket (PRD V15): bucket, CORS, incomplete-upload lifecycle, signing role."""
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest
from google.api_core.exceptions import NotFound

from common.constants.nested import NESTED_MEDIA_SIGNED_HEADERS

from cloud_deployment import setup_manager as setup_manager_module
from cloud_deployment.operations.images_and_specs import nested_media_bucket as module
from cloud_deployment.operations.images_and_specs.nested_media_bucket import NestedMediaBucket
from cloud_deployment.setup_manager import SetupManager
from cloud_deployment.utilities.menu_options import SetupCategories, SetupOptions, category_menu

PROJECT = 'selected-child'
SA = f'agoge-service@{PROJECT}.iam.gserviceaccount.com'
MEMBER = f'serviceAccount:{SA}'


class FakePolicy(dict):
    def __init__(self, bindings=None):
        super().__init__()
        self.bindings = bindings or []


def _bucket(policy=None):
    bucket = MagicMock()
    bucket.name = f'{PROJECT}_nested-media'
    bucket.get_iam_policy.return_value = policy if policy is not None else FakePolicy()
    return bucket


def _iam(policy):
    iam = MagicMock()
    accounts = iam.projects.return_value.serviceAccounts.return_value
    accounts.getIamPolicy.return_value.execute.return_value = policy
    return iam, accounts


@pytest.fixture
def env(monkeypatch):
    env = SimpleNamespace(project=PROJECT, region='us-central1', main_app_url='https://app.example.edu/child-path')
    monkeypatch.setattr(module, 'CloudEnv', Mock(return_value=env))
    return env


def test_creates_a_private_bucket_with_cors_lifecycle_and_both_roles(env, capsys):
    storage = MagicMock()
    storage.get_bucket.side_effect = NotFound('missing')
    bucket = _bucket()
    storage.create_bucket.return_value = bucket
    iam, accounts = _iam({'etag': 'e'})

    assert NestedMediaBucket(PROJECT, storage_client=storage, iam_client=iam).run() is True

    new_bucket = storage.bucket.return_value
    storage.bucket.assert_called_once_with(f'{PROJECT}_nested-media')
    assert new_bucket.iam_configuration.uniform_bucket_level_access_enabled is True
    assert new_bucket.iam_configuration.public_access_prevention == 'enforced'
    storage.create_bucket.assert_called_once_with(new_bucket, location='us-central1')
    [cors] = bucket.cors
    # CORS matches an origin, so the shared deployment's project path is dropped.
    assert cors['origin'] == ['https://app.example.edu', 'http://localhost:3000', 'http://127.0.0.1:3000']
    assert {'POST', 'PUT'} <= set(cors['method'])
    assert 'Location' in cors['responseHeader']
    assert bucket.lifecycle_rules == [{
        'action': {'type': 'Delete'},
        'condition': {'daysSinceCustomTime': 2, 'matchesPrefix': ['media/']},
    }]
    bucket.patch.assert_called_once_with()
    [binding] = bucket.get_iam_policy.return_value.bindings
    assert binding == {'role': 'roles/storage.objectAdmin', 'members': {MEMBER}}
    bucket.set_iam_policy.assert_called_once()
    accounts.getIamPolicy.assert_called_once_with(resource=f'projects/{PROJECT}/serviceAccounts/{SA}')
    body = accounts.setIamPolicy.call_args.kwargs['body']
    assert body['policy']['bindings'] == [{'role': 'roles/iam.serviceAccountTokenCreator', 'members': [MEMBER]}]
    assert body['policy']['etag'] == 'e'
    assert 'can sign upload URLs' in capsys.readouterr().out


def test_rerun_updates_an_existing_bucket_and_grants_nothing_twice(env):
    storage = MagicMock()
    bucket = _bucket(FakePolicy([{'role': 'roles/storage.objectAdmin', 'members': {MEMBER}}]))
    storage.get_bucket.return_value = bucket
    iam, accounts = _iam({'bindings': [{'role': 'roles/iam.serviceAccountTokenCreator', 'members': [MEMBER]}]})

    assert NestedMediaBucket(PROJECT, storage_client=storage, iam_client=iam).run() is True

    storage.create_bucket.assert_not_called()
    bucket.patch.assert_called_once_with()
    bucket.set_iam_policy.assert_not_called()
    accounts.setIamPolicy.assert_not_called()


def test_token_creator_member_is_added_to_an_existing_binding(env):
    storage = MagicMock()
    storage.get_bucket.return_value = _bucket()
    other = 'user:someone@example.edu'
    iam, accounts = _iam({'bindings': [{'role': 'roles/iam.serviceAccountTokenCreator', 'members': [other]}]})

    assert NestedMediaBucket(PROJECT, storage_client=storage, iam_client=iam).run() is True

    [binding] = accounts.setIamPolicy.call_args.kwargs['body']['policy']['bindings']
    assert binding['members'] == [other, MEMBER]


def test_failure_is_reported_and_returns_false(env, capsys):
    storage = MagicMock()
    storage.get_bucket.side_effect = RuntimeError('permission denied')

    assert NestedMediaBucket(PROJECT, storage_client=storage, iam_client=MagicMock()).run() is False
    assert 'permission denied' in capsys.readouterr().out


def test_mismatched_environment_stops_before_any_change(env):
    env.project = 'wrong-child'
    storage = MagicMock()

    assert NestedMediaBucket(PROJECT, storage_client=storage, iam_client=MagicMock()).run() is False
    storage.get_bucket.assert_not_called()


def test_menu_runs_the_operation(monkeypatch):
    op = MagicMock()
    monkeypatch.setattr(setup_manager_module, 'NestedMediaBucket', op)

    SetupManager(SetupOptions.NESTED_MEDIA_BUCKET, PROJECT).run()

    op.assert_called_once_with(project=PROJECT)
    op.return_value.run.assert_called_once_with()


def test_operation_is_listed_under_images_and_specs():
    options = [option for option, _ in category_menu[SetupCategories.IMAGES_AND_SPECS]['options']]
    assert SetupOptions.NESTED_MEDIA_BUCKET in options
    assert options[-1] == SetupOptions.BACK


def test_cors_allows_every_header_the_upload_url_signs():
    allowed = {header.lower() for header in module.CORS_RESPONSE_HEADERS}
    assert set(NESTED_MEDIA_SIGNED_HEADERS) <= allowed

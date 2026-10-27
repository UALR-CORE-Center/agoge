from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from googleapiclient.errors import HttpError
import pytest

from cloud_fn_utilities.server_specific.guacamole import community_proxy_bootstrap as module
from common.exceptions import BadRequest

UNIT = 'abcdefghij'
PROJECT = 'tenant-project'
SECRET = f'projects/{PROJECT}/secrets/agoge-guac-{UNIT}/versions/1'
EMAIL = f'agoge-guac-{UNIT}@{PROJECT}.iam.gserviceaccount.com'
ENV = {'project': PROJECT, 'parent_dns_suffix': '.tenant.example.test', 'dns_suffix': '.fallback.test'}


def iam_mock():
    iam = MagicMock()
    accounts = iam.projects.return_value.serviceAccounts.return_value
    accounts.get.return_value.execute.return_value = {'email': EMAIL}
    accounts.getIamPolicy.return_value.execute.return_value = {
        'etag': 'preserve-me', 'bindings': [{'role': 'roles/viewer', 'members': ['user:keep@example.test']}]}
    return iam, accounts


def test_proxy_identity_has_separate_name_and_grants_actas_only_on_itself():
    iam, accounts = iam_mock()
    identity = module.CommunityProxyIdentity(PROJECT, iam)
    assert identity.ensure(UNIT) == EMAIL
    request = accounts.setIamPolicy.call_args.kwargs
    assert request['resource'] == f'projects/{PROJECT}/serviceAccounts/{EMAIL}'
    assert request['body']['policy']['etag'] == 'preserve-me'
    assert request['body']['policy']['bindings'] == [
        {'role': 'roles/viewer', 'members': ['user:keep@example.test']},
        {'role': 'roles/iam.serviceAccountUser', 'members': [f'serviceAccount:agoge-service@{PROJECT}.iam.gserviceaccount.com']},
    ]


def test_identity_create_uses_dedicated_guac_account_id():
    iam, accounts = iam_mock()
    accounts.get.return_value.execute.side_effect = HttpError(SimpleNamespace(status=404, reason='Not found'), b'{}')
    accounts.create.return_value.execute.return_value = {'email': EMAIL}
    assert module.CommunityProxyIdentity(PROJECT, iam).ensure(UNIT) == EMAIL
    assert accounts.create.call_args.kwargs['body']['accountId'] == 'agoge-guac-' + UNIT


def test_disabled_identity_cannot_be_reused():
    iam, accounts = iam_mock()
    accounts.get.return_value.execute.return_value = {'disabled': True}
    with pytest.raises(BadRequest, match='disabled'):
        module.CommunityProxyIdentity(PROJECT, iam).ensure(UNIT)
    accounts.getIamPolicy.assert_not_called()


def test_bootstrap_uses_immutable_secret_reference_without_secret_metadata():
    iam, accounts = iam_mock()
    with patch.object(module, 'CommunityGuacamoleService') as store:
        store.return_value.ensure_key.return_value = SECRET
        fields = module.prepare_community_proxy(UNIT, ENV, iam=iam)
    store.return_value.grant_proxy_access.assert_called_once_with(UNIT, SECRET, EMAIL)
    assert fields['guacamole_secret_version_name'] == SECRET
    assert fields['service_accounts'] == fields['serviceAccounts'] == [
        {'email': EMAIL, 'scopes': ['https://www.googleapis.com/auth/cloud-platform']}]
    metadata = {item['key']: item['value'] for item in fields['metadata']['items']}
    assert metadata[module.SECRET_METADATA_KEY] == SECRET
    assert metadata['startup-script'].startswith('#!/bin/bash')
    assert UNIT + '-display.tenant.example.test' in metadata['startup-script']
    assert fields['guacamole_startup_script'] is None
    assert fields['no_service_account'] is False


def test_retry_reuses_supplied_reference_and_does_not_create_new_key():
    iam, accounts = iam_mock()
    with patch.object(module, 'CommunityGuacamoleService') as store:
        fields = module.prepare_community_proxy(UNIT, ENV, secret_version_name=SECRET, iam=iam)
    store.return_value.get_key.assert_called_once_with(UNIT, SECRET)
    store.return_value.ensure_key.assert_not_called()
    assert fields['guacamole_secret_version_name'] == SECRET


def test_cleanup_deletes_only_owned_secret_and_dedicated_proxy_identity():
    iam, accounts = iam_mock()
    with patch.object(module, 'CommunityGuacamoleService') as store:
        module.delete_community_proxy(UNIT, ENV, iam=iam)
    store.return_value.delete.assert_called_once_with(UNIT)
    accounts.delete.assert_called_once_with(name=f'projects/{PROJECT}/serviceAccounts/{EMAIL}')
    accounts.delete.return_value.execute.side_effect = HttpError(SimpleNamespace(status=404, reason='Not found'), b'{}')
    module.CommunityProxyIdentity(PROJECT, iam).delete(UNIT)

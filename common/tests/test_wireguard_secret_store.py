"""Secret access grants tolerate only new service-account visibility delays."""
from unittest.mock import Mock

from google.api_core.exceptions import InvalidArgument, PermissionDenied
from google.iam.v1 import iam_policy_pb2, policy_pb2
import pytest

from common.services import wireguard_provisioning as module


VERSION = 'projects/tenant-project/secrets/agoge-wg-abcdefghij/versions/latest'
RESOURCE = VERSION.split('/versions/')[0]
EMAIL = 'agoge-wg-abcdefghij@tenant-project.iam.gserviceaccount.com'
MEMBER = f'serviceAccount:{EMAIL}'
ROLE = 'roles/secretmanager.secretAccessor'


def policy(etag=b'first-etag', version=3):
    value = policy_pb2.Policy(version=version, etag=etag)
    value.bindings.add(role='roles/secretmanager.viewer', members=['user:reader@example.edu'])
    value.bindings.add(role=ROLE, members=['serviceAccount:other@tenant-project.iam.gserviceaccount.com'])
    conditional = value.bindings.add(role=ROLE, members=['user:conditional@example.edu'])
    conditional.condition.title = 'Keep this condition'
    conditional.condition.expression = 'request.time < timestamp("2030-01-01T00:00:00Z")'
    return value


@pytest.fixture
def grant(monkeypatch):
    client = Mock()
    client.get_iam_policy.side_effect = lambda **kwargs: policy()
    store = module.WireGuardSecretStore('tenant-project', client=client)
    store.logger = Mock()
    sleep = Mock()
    monkeypatch.setattr(module.time, 'sleep', sleep)
    return store, client, sleep


def test_configuration_staging_uses_a_new_secret_and_immutable_numeric_version(grant):
    store, client, _ = grant
    reference = 'projects/tenant-project/secrets/agoge-wg-abcdefghij-cfg-revision/versions/1'
    client.add_secret_version.return_value.name = reference
    assert store.stage_configuration('abcdefghij', 'revision', {'private_key': 'private-value'}) == reference
    assert client.create_secret.call_args.kwargs['request']['secret_id'] == 'agoge-wg-abcdefghij-cfg-revision'
    assert client.add_secret_version.call_args.kwargs['request']['parent'] == reference.split('/versions/')[0]
    client.access_secret_version.assert_not_called()
    assert 'private-value' not in repr(store.logger.mock_calls)


def test_failed_version_staging_cleans_unselected_new_secret(grant):
    store, client, _ = grant
    client.add_secret_version.side_effect = PermissionDenied('private response')
    with pytest.raises(PermissionDenied):
        store.stage_configuration('abcdefghij', 'revision', {'private_key': 'private-value'})
    client.delete_secret.assert_called_once_with(request={
        'name': 'projects/tenant-project/secrets/agoge-wg-abcdefghij-cfg-revision'})
    assert 'private-value' not in repr(store.logger.mock_calls)


def test_grant_preserves_real_policy_etag_version_and_conditional_bindings(grant):
    store, client, sleep = grant
    original = policy()
    conditional = policy_pb2.Binding()
    conditional.CopyFrom(original.bindings[2])
    client.get_iam_policy.side_effect = None
    client.get_iam_policy.return_value = original

    store.grant(VERSION, EMAIL)

    client.get_iam_policy.assert_called_once_with(request={
        'resource': RESOURCE, 'options': {'requested_policy_version': 3}})
    sdk_request = iam_policy_pb2.GetIamPolicyRequest(**client.get_iam_policy.call_args.kwargs['request'])
    assert sdk_request.options.requested_policy_version == 3
    request = client.set_iam_policy.call_args.kwargs['request']
    saved = request['policy']
    assert request['resource'] == RESOURCE
    assert saved.version == 3 and saved.etag == b'first-etag'
    assert saved.bindings[0].members == ['user:reader@example.edu']
    assert saved.bindings[2] == conditional
    assert set(saved.bindings[1].members) == {
        'serviceAccount:other@tenant-project.iam.gserviceaccount.com', MEMBER}
    assert len(saved.bindings) == 3
    sleep.assert_not_called()


def test_grant_adds_a_distinct_unconditional_binding_if_only_conditional_exists(grant):
    store, client, sleep = grant
    existing = policy_pb2.Policy(version=3, etag=b'conditional-etag')
    binding = existing.bindings.add(role=ROLE, members=[MEMBER])
    binding.condition.expression = 'resource.name == "private-condition-text"'
    binding.condition.title = 'Private condition title'
    original = existing.SerializeToString()
    client.get_iam_policy.side_effect = None
    client.get_iam_policy.return_value = existing

    store.grant(VERSION, EMAIL)

    saved = client.set_iam_policy.call_args.kwargs['request']['policy']
    assert saved.bindings[0].condition.expression == 'resource.name == "private-condition-text"'
    assert saved.bindings[1].role == ROLE and saved.bindings[1].members == [MEMBER]
    assert not saved.bindings[1].HasField('condition')
    assert saved.etag == b'conditional-etag' and saved.version == 3
    assert original != saved.SerializeToString()
    assert 'private-condition-text' not in repr(store.logger.mock_calls)
    sleep.assert_not_called()


def test_an_existing_exact_unconditional_grant_is_a_read_only_noop(grant):
    store, client, sleep = grant
    existing = policy_pb2.Policy(version=1, etag=b'already-granted')
    existing.bindings.add(role=ROLE, members=[MEMBER])
    original = existing.SerializeToString()
    client.get_iam_policy.side_effect = None
    client.get_iam_policy.return_value = existing

    store.grant(VERSION, EMAIL)

    assert existing.SerializeToString() == original
    client.set_iam_policy.assert_not_called()
    sleep.assert_not_called()


@pytest.mark.parametrize('message', [
    f'Service account {EMAIL} does not exist.',
    f'Service account "{EMAIL}" was not found.',
    f'Unknown service account: {EMAIL}',
    f'Unknown service account: {EMAIL}.',
    f'Service account not found: {EMAIL}',
    f'Principal {EMAIL} does not exist.',
    f'The member serviceAccount:{EMAIL} does not exist.',
])
def test_missing_exact_new_identity_retries_with_the_latest_policy(grant, message):
    store, client, sleep = grant
    first, second = policy(), policy(etag=b'new-etag')
    second.bindings.add(role='roles/secretmanager.admin', members=['user:concurrent@example.edu'])
    client.get_iam_policy.side_effect = [first, second]
    client.set_iam_policy.side_effect = [InvalidArgument(message), None]

    store.grant(VERSION, EMAIL)

    assert client.get_iam_policy.call_count == client.set_iam_policy.call_count == 2
    sleep.assert_called_once_with(1)
    saved = client.set_iam_policy.call_args.kwargs['request']['policy']
    assert saved.etag == b'new-etag'
    assert saved.bindings[3].members == ['user:concurrent@example.edu']
    assert list(saved.bindings[1].members).count(MEMBER) == 1
    log = repr(store.logger.mock_calls)
    assert 'secretmanager.set_iam_policy' in log and 'retry_delay_seconds=1' in log
    assert message not in log and EMAIL not in log


@pytest.mark.parametrize('message', [
    'Request contains an invalid argument.',
    f'Malformed policy for {EMAIL}.',
    f'Role roles/private-does-not-exist does not exist; requested member {EMAIL}.',
    f'Service account prefix-{EMAIL} does not exist.',
    f'Service account {EMAIL}.evil.example does not exist.',
    'Service account different@tenant-project.iam.gserviceaccount.com does not exist.',
    f'Unknown member type: {EMAIL}',
])
def test_unknown_or_unrelated_invalid_arguments_fail_without_retry(grant, message):
    store, client, sleep = grant
    error = InvalidArgument(message)
    client.set_iam_policy.side_effect = error
    with pytest.raises(InvalidArgument) as raised:
        store.grant(VERSION, EMAIL)
    assert raised.value is error
    assert client.get_iam_policy.call_count == client.set_iam_policy.call_count == 1
    sleep.assert_not_called()
    store.logger.warning.assert_not_called()
    fields = store.logger.error.call_args.kwargs
    assert fields['operation'] == 'secretmanager.set_iam_policy'
    assert fields['error_type'] == 'InvalidArgument' and fields['attempt'] == 1
    assert message not in repr(store.logger.mock_calls)


def test_retry_exhaustion_is_bounded_and_raises_the_original_api_error(grant):
    store, client, sleep = grant
    error = InvalidArgument(f'Service account {EMAIL} does not exist. private-response-tail')
    client.set_iam_policy.side_effect = error

    with pytest.raises(InvalidArgument) as raised:
        store.grant(VERSION, EMAIL)

    assert raised.value is error
    assert client.get_iam_policy.call_count == client.set_iam_policy.call_count == 8
    assert [call.args[0] for call in sleep.call_args_list] == [1, 2, 4, 8, 16, 32, 32]
    assert sum(call.args[0] for call in sleep.call_args_list) == 95
    fields = store.logger.error.call_args.kwargs
    assert fields['attempt'] == fields['max_attempts'] == 8
    assert fields['operation'] == 'secretmanager.set_iam_policy'
    assert store.logger.warning.call_count == 7
    assert 'private-response-tail' not in repr(store.logger.mock_calls)


@pytest.mark.parametrize('operation', ['get_iam_policy', 'set_iam_policy'])
def test_permission_denied_never_retries_and_names_the_failing_operation(grant, operation):
    store, client, sleep = grant
    getattr(client, operation).side_effect = PermissionDenied(
        f'Service account {EMAIL} does not exist. private-denial-body')

    with pytest.raises(PermissionDenied):
        store.grant(VERSION, EMAIL)

    sleep.assert_not_called()
    assert client.get_iam_policy.call_count == 1
    assert client.set_iam_policy.call_count == (operation == 'set_iam_policy')
    fields = store.logger.error.call_args.kwargs
    assert fields['operation'] == f'secretmanager.{operation}'
    assert fields['error_type'] == 'PermissionDenied' and fields['attempt'] == 1
    assert 'private-denial-body' not in repr(store.logger.mock_calls)


def test_invalid_policy_read_fails_fast_without_granting_access(grant):
    store, client, sleep = grant
    client.get_iam_policy.side_effect = InvalidArgument('private invalid resource response')
    with pytest.raises(InvalidArgument):
        store.grant(VERSION, EMAIL)
    client.set_iam_policy.assert_not_called()
    sleep.assert_not_called()
    assert store.logger.error.call_args.kwargs['operation'] == 'secretmanager.get_iam_policy'
    assert 'private invalid resource response' not in repr(store.logger.mock_calls)

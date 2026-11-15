from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock
from zoneinfo import ZoneInfo

from google.api_core.exceptions import InvalidArgument, PreconditionFailed
from google.cloud import secretmanager
from googleapiclient.errors import HttpError
from google.iam.v1 import policy_pb2
import pytest

from cloud_deployment.operations.guacamole_image_management import shared_tls_setup as setup
from cloud_fn_utilities.periodic_maintenance.maintenance_schedule import is_daily_maintenance_time
from common.exceptions import AgogeValidationError


def _jobs(monkeypatch):
    jobs = Mock()
    monkeypatch.setattr(setup, 'build', lambda *_args, **_kwargs: Mock(
        **{'projects.return_value.locations.return_value.jobs.return_value': jobs},
    ))
    return jobs


def _missing():
    return HttpError(SimpleNamespace(status=404, reason='Not found'), b'{}')


def test_reuses_only_matching_shared_maintenance(monkeypatch):
    jobs = _jobs(monkeypatch)
    topic = 'projects/shared-project/topics/agoge'
    jobs.get.return_value.execute.side_effect = [_missing(), {
        'schedule': '*/15 * * * *',
        'state': 'ENABLED',
        'timeZone': 'America/Chicago',
        'pubsubTarget': {'topicName': topic, 'attributes': {'handler': 'MAINTENANCE'}},
    }]

    assert setup._maintenance_source('shared-project', 'us-central1', 'issuer')[2:] == (
        topic, 'America/Chicago', False,
    )
    midnight = datetime(2026, 11, 15, 0, 0, 2, tzinfo=ZoneInfo('America/Chicago'))
    assert is_daily_maintenance_time(midnight)
    assert not is_daily_maintenance_time(midnight.replace(hour=12))


def test_ignores_other_project_and_staging_uses_own_trigger(monkeypatch):
    jobs = _jobs(monkeypatch)
    jobs.get.return_value.execute.side_effect = [_missing(), {
        'schedule': '*/15 * * * *',
        'state': 'ENABLED',
        'pubsubTarget': {
            'topicName': 'projects/tenant-project/topics/agoge',
            'attributes': {'handler': 'MAINTENANCE'},
        },
    }]

    assert setup._maintenance_source('shared-project', 'us-central1', 'issuer')[2:] == (
        'projects/shared-project/topics/issuer', '', True,
    )
    jobs.get.return_value.execute.side_effect = [_missing()]
    assert setup._maintenance_source(
        'shared-project', 'us-central1', 'issuer-staging', reuse_shared=False,
    )[2:] == ('projects/shared-project/topics/issuer-staging', '', True)


def test_cert_secret_reconcile_is_idempotent_and_preserves_other_iam():
    client = Mock()
    policy = policy_pb2.Policy(version=3, etag=b'if-match', bindings=[
        policy_pb2.Binding(
            role=setup.ACCESSOR_ROLE, members=['user:other@example.com'],
            condition={'expression': 'true', 'title': 'Existing condition'},
        ),
    ])
    client.get_iam_policy.return_value = policy
    secret = 'projects/shared-project/secrets/guacamole-tls-example-com'
    email = 'agoge-guac-tls@tenant-project.iam.gserviceaccount.com'

    setup._set_secret_membership(client, secret, setup.ACCESSOR_ROLE, email)
    setup._set_secret_membership(client, secret, setup.ACCESSOR_ROLE, email)
    assert client.set_iam_policy.call_count == 1
    assert set(policy.bindings[1].members) == {f'serviceAccount:{email}'}
    setup._set_secret_membership(client, secret, setup.ACCESSOR_ROLE, email, present=False)
    assert len(policy.bindings) == 1
    assert policy.bindings[0].condition.expression == 'true'
    assert policy.etag == b'if-match'


def test_tenant_enrollment_requires_enabled_production_alias(monkeypatch):
    client = Mock()
    client.get_secret.return_value = secretmanager.Secret(version_aliases={'active': 4})
    client.get_secret_version.return_value = secretmanager.SecretVersion(
        state=secretmanager.SecretVersion.State.DISABLED,
    )
    monkeypatch.setattr(setup.secretmanager, 'SecretManagerServiceClient', lambda: client)
    args = SimpleNamespace(project='shared-project', domain='example.com', allow=['a'], remove=[])

    with pytest.raises(AgogeValidationError, match='active production certificate'):
        setup.reconcile_tenants(args)
    client.set_iam_policy.assert_not_called()


def test_permission_retry_refreshes_etag_after_principal_propagates(monkeypatch):
    client = Mock()
    client.get_iam_policy.side_effect = [policy_pb2.Policy(etag=etag) for etag in (b'1', b'2', b'3')]
    email = 'agoge-guac-tls@tenant-project.iam.gserviceaccount.com'
    client.set_iam_policy.side_effect = [
        InvalidArgument(f'Service account {email} does not exist.'),
        PreconditionFailed('etag changed'),
        None,
    ]
    monkeypatch.setattr(setup.time, 'sleep', Mock())

    setup._set_secret_membership(
        client, 'projects/shared-project/secrets/tls', setup.ACCESSOR_ROLE, email,
    )

    assert client.get_iam_policy.call_count == 3
    assert client.set_iam_policy.call_args.kwargs['request']['policy'].etag == b'3'


def test_tenant_config_accepts_recorded_dns_project_as_parent(monkeypatch):
    database = Mock()
    settings = {
        'project': 'tenant-project',
        'parent_project': 'dns-project',
        'parent_dns_suffix': '.example.com',
    }
    database.collection.return_value.document.return_value.get.return_value.to_dict.return_value = settings
    monkeypatch.setattr(setup.firestore, 'Client', Mock(return_value=database))

    assert setup._tenant_config('tenant-project', 'shared-project', 'example.com', 'dns-project')[-1] == settings
    with pytest.raises(AgogeValidationError, match='parent'):
        setup._tenant_config('tenant-project', 'shared-project', 'example.com', 'different-project')

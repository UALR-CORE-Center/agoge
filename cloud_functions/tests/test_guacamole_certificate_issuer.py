from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from google.api_core.exceptions import NotFound, PreconditionFailed

from cloud_fn_utilities.periodic_maintenance import guacamole_certificate_issuer as issuer


DOMAIN = 'agoge-labs.example'


@pytest.fixture
def config():
    return issuer.IssuerConfig('shared-project', DOMAIN, 'dns-project', 'state-bucket',
                               'agoge-guacamole-tls', 'operations@example.test', False)


def _issue(days=90, domains=(DOMAIN, '*.' + DOMAIN)):
    now = datetime.now(UTC)
    key = ec.generate_private_key(ec.SECP256R1())
    ca_key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, DOMAIN)])
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Test issuer')])
    ca = (x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name)
          .public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
          .not_valid_before(now - timedelta(days=2)).not_valid_after(now + timedelta(days=365))
          .sign(ca_key, hashes.SHA256()))
    leaf = (x509.CertificateBuilder().subject_name(name).issuer_name(ca_name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=days))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName(domain) for domain in domains]), critical=False)
            .sign(ca_key, hashes.SHA256()))
    chain = leaf.public_bytes(serialization.Encoding.PEM) + ca.public_bytes(serialization.Encoding.PEM)
    private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption())
    return issuer.CertificateBundle(chain.decode(), private.decode())


def _version(config, version, bundle):
    return SimpleNamespace(name=f'{config.secret_path}/versions/{version}',
                           payload=SimpleNamespace(data=bundle.payload()))


def test_reads_publish_time_in_configured_maintenance_timezone(monkeypatch):
    monkeypatch.setenv('AGOGE_TLS_SCHEDULE_TIMEZONE', 'America/Chicago')
    event = Mock()
    event.data = {'message': {'attributes': {'handler': 'MAINTENANCE'}, 'publishTime': '2026-11-15T06:00:02Z'}}
    assert issuer._scheduled_tick(event)
    event.data['message']['publishTime'] = '2026-11-15T06:30:00Z'
    assert not issuer._scheduled_tick(event)
    monkeypatch.delenv('AGOGE_TLS_SCHEDULE_TIMEZONE')
    assert issuer._scheduled_tick(event)
    event.data['message']['attributes']['handler'] = 'BUILD'
    assert not issuer._scheduled_tick(event)


def test_bundle_validation_rejects_wrong_identity_and_key():
    bundle = _issue()
    assert bundle.certificate(DOMAIN, datetime.now(UTC)).not_valid_after_utc > datetime.now(UTC)
    wrong_names = _issue(domains=(DOMAIN,))
    wrong_key = issuer.CertificateBundle(bundle.fullchain, wrong_names.privkey)
    for invalid in (wrong_names, wrong_key, _issue(days=-1)):
        with pytest.raises(issuer.IssuerError):
            invalid.certificate(DOMAIN, datetime.now(UTC))


def test_issuer_staging_requires_isolated_secret_and_storage(monkeypatch, config):
    for key, value in {'PROJECT': config.project, 'DOMAIN': DOMAIN, 'DNS_PROJECT': config.dns_project,
                       'STATE_BUCKET': config.bucket, 'SECRET': config.secret, 'EMAIL': config.email,
                       'STAGING': 'true'}.items():
        monkeypatch.setenv('AGOGE_TLS_' + key, value)
    with pytest.raises(issuer.IssuerError, match='-staging secret'):
        issuer.IssuerConfig.from_environment()
    monkeypatch.setenv('AGOGE_TLS_SECRET', config.secret + '-staging')
    staging_config = issuer.IssuerConfig.from_environment()
    assert staging_config.staging
    assert staging_config.state_prefix != config.state_prefix


def test_publisher_reuses_version_staged_before_failed_alias_update(config):
    client = Mock()
    secret = SimpleNamespace(etag='old-etag', version_aliases={'active': 3, 'unrelated': 2})
    client.get_secret.return_value = secret
    old, renewed = _issue(days=10), _issue()
    client.access_secret_version.side_effect = [_version(config, 3, old), _version(config, 4, renewed)]
    publisher = issuer.CertificatePublisher(client, config)
    stored, active = publisher.inspect()
    cert = renewed.certificate(DOMAIN, datetime.now(UTC))
    lease = Mock()
    publisher.publish(renewed, cert, stored, active, lease)
    client.add_secret_version.assert_not_called()
    client.update_secret.assert_called_once_with(request={
        'secret': {'name': config.secret_path, 'etag': 'old-etag',
                   'version_aliases': {'active': 4, 'previous': 3, 'unrelated': 2}},
        'update_mask': {'paths': ['version_aliases']},
    }, timeout=issuer.API_TIMEOUT)
    assert lease.call_count == 2


def test_publisher_leaves_matching_active_version_untouched(config):
    client = Mock()
    secret = SimpleNamespace(etag='etag', version_aliases={'active': 3})
    bundle = _issue()
    cert = bundle.certificate(DOMAIN, datetime.now(UTC))
    issuer.CertificatePublisher(client, config).publish(bundle, cert, secret, cert, Mock())
    client.access_secret_version.assert_not_called()
    client.add_secret_version.assert_not_called()
    client.update_secret.assert_not_called()


def test_publisher_can_seed_empty_secret(config):
    client = Mock()
    secret = SimpleNamespace(etag='new-etag', version_aliases={})
    client.access_secret_version.side_effect = NotFound('empty')
    bundle = _issue()
    client.add_secret_version.return_value = _version(config, 1, bundle)
    cert = bundle.certificate(DOMAIN, datetime.now(UTC))
    issuer.CertificatePublisher(client, config).publish(bundle, cert, secret, None, Mock())
    client.add_secret_version.assert_called_once()
    assert client.update_secret.call_args.kwargs['request']['secret']['version_aliases'] == {'active': 1}


def test_persists_fresh_lineage_before_attempting_activation(monkeypatch, tmp_path, config):
    state, publisher = Mock(), Mock()
    publisher.inspect.return_value = (object(), None)
    state.restore.return_value = 0
    state.acquire.return_value = True
    root = tmp_path / 'issuer'
    monkeypatch.setattr(issuer, 'ACME_ROOT', root)
    renewed = _issue()
    monkeypatch.setattr(issuer, '_certbot', Mock())
    monkeypatch.setattr(issuer, '_read_local_bundle', Mock(side_effect=[None, renewed]))

    def fail_publication(*args):
        state.save.assert_called_once_with(root / 'config', 0)
        raise PreconditionFailed('concurrent alias change')

    publisher.publish.side_effect = fail_publication
    with pytest.raises(PreconditionFailed):
        issuer._renew(config, state, publisher)
    state.release.assert_called_once()
    assert not root.exists()


def test_unchanged_lineage_stays_unwritten_and_can_resume_publication(monkeypatch, tmp_path, config):
    state, publisher = Mock(), Mock()
    state.restore.return_value = 5
    state.acquire.return_value = True
    publisher.inspect.return_value = (object(), None)
    monkeypatch.setattr(issuer, 'ACME_ROOT', tmp_path / 'issuer')
    bundle = _issue()
    monkeypatch.setattr(issuer, '_certbot', Mock())
    monkeypatch.setattr(issuer, '_read_local_bundle', Mock(return_value=bundle))

    issuer._renew(config, state, publisher)

    state.save.assert_not_called()
    assert publisher.publish.call_args.args[0] == bundle


def test_acme_archive_preserves_certbot_lineage_symlinks(tmp_path, config):
    directory = tmp_path / 'config'
    archive = directory / 'archive' / DOMAIN
    archive.mkdir(parents=True)
    (archive / 'privkey1.pem').write_text('fake-archive-key')
    lineage = directory / 'live' / DOMAIN
    lineage.mkdir(parents=True)
    (lineage / 'privkey.pem').symlink_to(f'../../archive/{DOMAIN}/privkey1.pem')
    bucket = Mock()
    state = issuer.AcmeState(bucket, config.state_prefix)
    state.check_lease = Mock()
    state.save(directory, 0)
    stored = bucket.blob.return_value.upload_from_string.call_args.args[0]
    state_object = bucket.get_blob.return_value
    state_object.size = len(stored)
    state_object.generation = 7
    state_object.download_as_bytes.return_value = stored

    restored = tmp_path / 'restored'
    restored.mkdir()
    assert state.restore(restored) == 7
    link = restored / 'live' / DOMAIN / 'privkey.pem'
    assert link.is_symlink()
    assert link.read_text() == 'fake-archive-key'


def test_lease_replaces_only_the_stale_generation(config):
    bucket = Mock()
    lock = bucket.blob.return_value
    lock.generation = 9
    lock.upload_from_string.side_effect = [PreconditionFailed('existing lease'), None]
    bucket.get_blob.return_value = SimpleNamespace(generation=8, updated=datetime.now(UTC) - issuer.LEASE_TTL)
    state = issuer.AcmeState(bucket, config.state_prefix)
    assert state.acquire()
    assert [call.kwargs['if_generation_match'] for call in lock.upload_from_string.call_args_list] == [0, 8]
    state.release()
    assert lock.delete.call_args.kwargs['if_generation_match'] == 9

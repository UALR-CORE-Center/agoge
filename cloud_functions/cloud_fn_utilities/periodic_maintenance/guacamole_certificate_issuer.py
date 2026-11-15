"""Issue the shared Guacamole certificate from a dedicated scheduled function."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import io
import json
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
from zoneinfo import ZoneInfo

import functions_framework
from cryptography import x509
from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from google.api_core.exceptions import FailedPrecondition, NotFound, PreconditionFailed
from google.cloud import secretmanager, storage

if __package__:
    from .maintenance_schedule import is_daily_maintenance_time
else:  # Cloud Functions stages this file as main.py.
    from maintenance_schedule import is_daily_maintenance_time


class CloudLogFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({'severity': record.levelname, 'message': record.getMessage()})


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)
LOGGER.propagate = False
_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(CloudLogFormatter())
LOGGER.addHandler(_handler)
ACME_ROOT = Path('/tmp/agoge-guacamole-acme')
LEASE_TTL = timedelta(minutes=15)
BOOTSTRAP_RENEWAL_WINDOW = timedelta(days=30)
EXPIRY_ALERT_WINDOW = timedelta(days=14)
MAX_STATE_BYTES = 8 * 1024 * 1024
API_TIMEOUT = 15


class IssuerError(RuntimeError):
    """An operational error with a message safe to log."""


@dataclass(frozen=True)
class IssuerConfig:
    project: str
    domain: str
    dns_project: str
    bucket: str
    secret: str
    email: str
    staging: bool

    @classmethod
    def from_environment(cls):
        def required(name):
            value = os.environ.get(f'AGOGE_TLS_{name}', '').strip()
            if not value:
                raise IssuerError(f'AGOGE_TLS_{name} is required')
            return value

        domain = required('DOMAIN').lower().strip('.')
        label = r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?'
        if len(domain) > 253 or not re.fullmatch(rf'{label}(?:\.{label})+', domain):
            raise IssuerError('Invalid Guacamole TLS domain')
        secret = required('SECRET')
        staging = os.environ.get('AGOGE_TLS_STAGING', 'false').lower()
        if staging not in ('true', 'false') or (staging == 'true') != secret.endswith('-staging'):
            raise IssuerError('Set AGOGE_TLS_STAGING=true only with a separate -staging secret')
        return cls(required('PROJECT'), domain, required('DNS_PROJECT'), required('STATE_BUCKET'),
                   secret, required('EMAIL'), staging == 'true')

    @property
    def secret_path(self):
        return f'projects/{self.project}/secrets/{self.secret}'

    @property
    def state_prefix(self):
        environment = 'staging' if self.staging else 'production'
        return f'guacamole-acme/{environment}/{self.domain}'


@dataclass(frozen=True)
class CertificateBundle:
    fullchain: str
    privkey: str

    def certificate(self, domain, now):
        try:
            chain = x509.load_pem_x509_certificates(self.fullchain.encode('ascii'))
            cert = chain[0]
            key = serialization.load_pem_private_key(self.privkey.encode('ascii'), password=None)
            names = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
            names = set(names.value.get_values_for_type(x509.DNSName))
            encoding = serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
            valid = (len(chain) >= 2 and names == {domain, '*.' + domain}
                     and cert.not_valid_before_utc <= now < cert.not_valid_after_utc
                     and cert.public_key().public_bytes(*encoding) == key.public_key().public_bytes(*encoding))
            for certificate, issuer in zip(chain, chain[1:]):
                certificate.verify_directly_issued_by(issuer)
        except (IndexError, TypeError, ValueError, x509.ExtensionNotFound, InvalidSignature, UnsupportedAlgorithm):
            raise IssuerError('Invalid Guacamole certificate bundle') from None
        if not valid:
            raise IssuerError('Guacamole certificate has an invalid chain, lifetime, name, or key')
        return cert

    def payload(self):
        return json.dumps({'fullchain': self.fullchain, 'privkey': self.privkey}).encode('ascii')

    @classmethod
    def from_payload(cls, payload):
        try:
            obj = json.loads(payload)
            fullchain, privkey = obj['fullchain'], obj['privkey']
            if not isinstance(fullchain, str) or not isinstance(privkey, str):
                raise ValueError
            return cls(fullchain, privkey)
        except (KeyError, TypeError, ValueError):
            raise IssuerError('Invalid Guacamole TLS secret payload') from None


class AcmeState:
    def __init__(self, bucket, prefix):
        self.bucket = bucket
        self.lock_name = f'{prefix}/issuer.lock'
        self.state_name = f'{prefix}/lineage.tar.gz'
        self.lock_generation = None

    def acquire(self):
        lock = self.bucket.blob(self.lock_name)
        try:
            lock.upload_from_string(b'', if_generation_match=0, timeout=API_TIMEOUT)
        except PreconditionFailed:
            current = self.bucket.get_blob(self.lock_name, timeout=API_TIMEOUT)
            if not current or not current.updated or datetime.now(UTC) - current.updated < LEASE_TTL:
                return False
            try:
                lock.upload_from_string(b'', if_generation_match=current.generation, timeout=API_TIMEOUT)
            except PreconditionFailed:
                return False
        self.lock_generation = lock.generation
        return True

    def check_lease(self):
        lock = self.bucket.get_blob(self.lock_name, timeout=API_TIMEOUT)
        if (not lock or lock.generation != self.lock_generation or not lock.updated
                or datetime.now(UTC) - lock.updated >= LEASE_TTL):
            raise IssuerError('Guacamole issuer lost its Cloud Storage lease')

    def release(self):
        try:
            self.bucket.blob(self.lock_name).delete(if_generation_match=self.lock_generation, timeout=API_TIMEOUT)
        except (NotFound, PreconditionFailed):
            pass

    def restore(self, directory):
        state = self.bucket.get_blob(self.state_name, timeout=API_TIMEOUT)
        if state is None:
            return 0
        if state.size is None or state.size > MAX_STATE_BYTES:
            raise IssuerError('The persisted Guacamole ACME archive exceeds its size limit')
        data = state.download_as_bytes(if_generation_match=state.generation, timeout=API_TIMEOUT)
        with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
            entries = []
            remaining = MAX_STATE_BYTES
            for entry in archive:
                if len(entries) >= 8_192 or not 0 <= entry.size <= remaining:
                    raise IssuerError('The restored Guacamole ACME archive exceeds its size limit')
                remaining -= entry.size
                entries.append(entry)
            archive.extractall(directory, members=entries, filter='data')
        return state.generation

    def save(self, directory, generation):
        output = io.BytesIO()
        with tarfile.open(fileobj=output, mode='w:gz') as archive:
            archive.add(directory, arcname='.')
        data = output.getvalue()
        if len(data) > MAX_STATE_BYTES:
            raise IssuerError('The new Guacamole ACME archive exceeds its size limit')
        self.check_lease()
        self.bucket.blob(self.state_name).upload_from_string(
            data, content_type='application/gzip', if_generation_match=generation, timeout=API_TIMEOUT,
        )


def _read_local_bundle(config_dir, domain):
    lineage = config_dir / 'live' / domain
    try:
        return CertificateBundle((lineage / 'fullchain.pem').read_text(), (lineage / 'privkey.pem').read_text())
    except FileNotFoundError:
        return None


def _certbot(config, root):
    command = [
        sys.executable, '-c', 'from certbot.main import main; raise SystemExit(main())',
        'certonly', '--non-interactive', '--agree-tos',
        '--keep-until-expiring', '--email', config.email, '--cert-name', config.domain,
        '--dns-google', '--dns-google-project', config.dns_project,
        '--dns-google-propagation-seconds', '60', '-d', config.domain, '-d', '*.' + config.domain,
        '--config-dir', str(root / 'config'), '--work-dir', str(root / 'work'),
        '--logs-dir', str(root / 'logs'),
    ]
    if config.staging:
        command.append('--staging')
    try:
        result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=360, check=False)
    except subprocess.TimeoutExpired:
        raise IssuerError('Certbot exceeded the Guacamole renewal time limit') from None
    if result.returncode:
        diagnostics = result.stderr.lower()
        hint = 'check the issuer identity, DNS project, and ACME availability'
        if b'rate limit' in diagnostics or b'too many certificates' in diagnostics:
            hint = 'the ACME provider rate limited issuance'
        elif b'permission' in diagnostics or b'forbidden' in diagnostics:
            hint = 'the issuer lacks access to the configured Cloud DNS zone'
        raise IssuerError(f'Certbot exited with status {result.returncode}. {hint}')


class CertificatePublisher:
    def __init__(self, client, config):
        self.client = client
        self.config = config

    def _access(self, version):
        return self.client.access_secret_version(
            request={'name': f'{self.config.secret_path}/versions/{version}'}, timeout=API_TIMEOUT,
        )

    def inspect(self):
        secret = self.client.get_secret(request={'name': self.config.secret_path}, timeout=API_TIMEOUT)
        version = secret.version_aliases.get('active')
        if not version:
            return secret, None
        try:
            active = CertificateBundle.from_payload(self._access(version).payload.data)
            return secret, active.certificate(self.config.domain, datetime.now(UTC))
        except (IssuerError, NotFound, FailedPrecondition):
            LOGGER.warning('Guacamole TLS active version %s is unavailable or invalid', version)
            return secret, None

    def publish(self, bundle, cert, secret, active_cert, check_lease):
        aliases = dict(secret.version_aliases)
        old_version = aliases.get('active')
        if active_cert and active_cert.not_valid_after_utc >= cert.not_valid_after_utc:
            LOGGER.info('Guacamole TLS active version %s remains current until %s',
                        old_version, active_cert.not_valid_after_utc.isoformat())
            return

        payload = bundle.payload()
        try:
            latest = self._access('latest')
        except (NotFound, FailedPrecondition):
            latest = None
        check_lease()
        if latest is not None and latest.payload.data == payload:
            version = latest
        else:
            version = self.client.add_secret_version(
                request={'parent': self.config.secret_path, 'payload': {'data': payload}},
                retry=None, timeout=API_TIMEOUT,
            )
        new_version = int(version.name.rsplit('/', 1)[-1])
        if old_version:
            aliases['previous'] = old_version
        aliases['active'] = new_version
        check_lease()
        self.client.update_secret(request={
            'secret': {'name': self.config.secret_path, 'etag': secret.etag, 'version_aliases': aliases},
            'update_mask': {'paths': ['version_aliases']},
        }, timeout=API_TIMEOUT)
        LOGGER.info('Published Guacamole TLS active version %s for %s, expiring %s', new_version,
                    self.config.domain, cert.not_valid_after_utc.isoformat())


def _renew(config, state, publisher):
    if not state.acquire():
        LOGGER.info('Guacamole TLS renewal already holds the issuer lease for %s', config.domain)
        return
    try:
        # Certbot renewal files contain absolute paths. Keep the same path in all invocations.
        shutil.rmtree(ACME_ROOT, ignore_errors=True)
        ACME_ROOT.mkdir(mode=0o700)
        directory = ACME_ROOT / 'config'
        directory.mkdir(mode=0o700)
        generation = state.restore(directory)
        secret, active_cert = publisher.inspect()
        if not generation and active_cert and active_cert.not_valid_after_utc - datetime.now(UTC) > BOOTSTRAP_RENEWAL_WINDOW:
            LOGGER.info('Guacamole TLS active certificate remains current until %s',
                        active_cert.not_valid_after_utc.isoformat())
            return
        before = _read_local_bundle(directory, config.domain)
        _certbot(config, ACME_ROOT)
        bundle = _read_local_bundle(directory, config.domain)
        if bundle is None:
            raise IssuerError('Certbot did not leave a Guacamole certificate and key')
        cert = bundle.certificate(config.domain, datetime.now(UTC))
        if bundle != before:
            state.save(directory, generation)
        publisher.publish(bundle, cert, secret, active_cert, state.check_lease)
        expiry = cert.not_valid_after_utc
        if active_cert:
            expiry = max(expiry, active_cert.not_valid_after_utc)
        if expiry - datetime.now(UTC) <= EXPIRY_ALERT_WINDOW:
            LOGGER.error('Guacamole TLS certificate for %s approaches expiry at %s', config.domain, expiry.isoformat())
    finally:
        shutil.rmtree(ACME_ROOT, ignore_errors=True)
        state.release()


def _scheduled_tick(cloud_event):
    message = cloud_event.data.get('message', {})
    if message.get('attributes', {}).get('handler') != 'MAINTENANCE':
        return False
    timezone = os.environ.get('AGOGE_TLS_SCHEDULE_TIMEZONE')
    if not timezone:
        return True
    timestamp = message.get('publishTime') or cloud_event.get_attributes().get('time')
    if not timestamp:
        raise IssuerError('Guacamole maintenance event is missing its publish time')
    scheduled_at = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    if scheduled_at.tzinfo is None:
        raise IssuerError('Guacamole maintenance event publish time is missing its time zone')
    return is_daily_maintenance_time(scheduled_at.astimezone(ZoneInfo(timezone)))


@functions_framework.cloud_event
def renew_guacamole_certificate(cloud_event):
    """Consume only shared-project scheduled maintenance events."""
    try:
        if not _scheduled_tick(cloud_event):
            return
        config = IssuerConfig.from_environment()
        bucket = storage.Client(project=config.project).bucket(config.bucket)
        state = AcmeState(bucket, config.state_prefix)
        publisher = CertificatePublisher(secretmanager.SecretManagerServiceClient(), config)
        _renew(config, state, publisher)
    except IssuerError as error:
        LOGGER.error('Guacamole TLS renewal failed: %s', error)
        raise
    except Exception as error:
        # Transport messages, Certbot output, and parse errors can contain secrets.
        reason = type(error).__name__
        LOGGER.error('Guacamole TLS renewal failed (%s)', reason)
        raise IssuerError(f'Guacamole TLS renewal failed ({reason})') from None

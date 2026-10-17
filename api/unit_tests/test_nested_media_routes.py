"""/compute/images/nested/media/ — signed resumable uploads, completion size check, list, delete (PRD V15)."""
import copy
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from google.api_core.exceptions import Forbidden as GcsForbidden, NotFound as GcsNotFound

import dependencies
from common.constants.database import DbCollections
from common.constants.nested import (NESTED_MEDIA_KEEP_CUSTOM_TIME, NESTED_MEDIA_MAX_BYTES, NESTED_MEDIA_SIGNED_HEADERS,
                                     NESTED_UPLOAD_URL_TTL_SECONDS)
from core.compute.nested import media as media_module
from core.compute.nested.media import media_format
from routers import compute_image as compute_image_module
from test_nested_host_validator import CATALOG

TEACHER = SimpleNamespace(uid='teacher', email='teacher@example.edu', is_authorized=True, is_admin=False)
OTHER = SimpleNamespace(uid='other', email='other@example.edu', is_authorized=True, is_admin=False)
ADMIN = SimpleNamespace(uid='admin', email='admin@example.edu', is_authorized=True, is_admin=True)
STUDENT = SimpleNamespace(uid='student', email='student@example.edu', is_authorized=False, is_admin=False)
BUCKET = 'test-dev-787001_nested-media'


def _medium(media_id, uploaded_by='teacher@example.edu', complete=False, size=1000, uploaded_at='2026-10-17T00:00:00Z'):
    return {'id': media_id, 'filename': 'fw.iso', 'format': 'iso', 'size_bytes': size,
            'gcs_path': f'gs://{BUCKET}/media/{media_id}/fw.iso', 'uploaded_by': uploaded_by,
            'uploaded_at': uploaded_at, 'complete': complete}


class FakeDb:
    def __init__(self):
        self.collections = {DbCollections.NESTED_MEDIA: {}, DbCollections.NESTED_OS_CATALOG: copy.deepcopy(CATALOG)}

    def insert(self, collection_name, data, id_field='id', use_transaction=False):
        self.collections[collection_name][data[id_field]] = copy.deepcopy(data)
        return data[id_field]

    def get(self, collection_name, doc_id, use_transaction=False):
        return copy.deepcopy(self.collections[collection_name].get(doc_id))

    def update(self, collection_name, doc_id, data, use_transaction=False):
        self.collections[collection_name][doc_id].update(data)

    def delete(self, collection_name, doc_id, use_transaction=False):
        self.collections[collection_name].pop(doc_id, None)

    def query(self, collection_name, filters=None, limit=None):
        return copy.deepcopy(list(self.collections[collection_name].values()))

    @property
    def media(self):
        return self.collections[DbCollections.NESTED_MEDIA]


class FakeStorage:
    """bucket(name).blob(object) signs and deletes; bucket(name).get_blob(object) returns uploaded objects."""

    def __init__(self):
        self.objects = {}
        self.blobs = {}
        self.sign_error = None

    def bucket(self, name):
        assert name == BUCKET
        return SimpleNamespace(blob=self._blob, get_blob=lambda object_name: self.objects.get(object_name))

    def _blob(self, object_name):
        blob = MagicMock(name=object_name)
        if self.sign_error:
            blob.generate_signed_url.side_effect = self.sign_error
        else:
            blob.generate_signed_url.return_value = f'https://storage.googleapis.com/{BUCKET}/{object_name}?X-Goog-Signature=sig'
        blob.delete.side_effect = lambda: self._delete(object_name)
        self.blobs[object_name] = blob
        return blob

    def _delete(self, object_name):
        if object_name not in self.objects:
            raise GcsNotFound('gone')
        del self.objects[object_name]

    def upload(self, media_id, size):
        blob = MagicMock(size=size, custom_time=None)
        self.objects[f'media/{media_id}/fw.iso'] = blob
        return blob


@pytest.fixture
def world(monkeypatch):
    db, gcs = FakeDb(), FakeStorage()
    env = SimpleNamespace(project='test-dev-787001', get_env=lambda: {})
    monkeypatch.setattr(media_module, 'CloudEnv', lambda **kwargs: env)
    monkeypatch.setattr(media_module.DocumentDatabaseFactory, 'create_db_object', lambda *args, **kwargs: db)
    monkeypatch.setattr(media_module.storage, 'Client', lambda **kwargs: gcs)
    # Signing goes through IAM signBlob on Cloud Run; here the credentials only need to reach the call.
    monkeypatch.setattr(media_module.NestedMedia, '_signing_kwargs', staticmethod(lambda: {'credentials': 'creds'}))
    return SimpleNamespace(db=db, gcs=gcs)


def _client(user):
    app = FastAPI()
    app.include_router(compute_image_module.compute_image_router)
    app.dependency_overrides[dependencies.get_cloud_env] = lambda: {}
    app.dependency_overrides[dependencies.get_current_user] = lambda: user
    return TestClient(app)


def _create(world, user=TEACHER, **body):
    return _client(user).post('/compute/images/nested/media/',
                              json={'filename': 'fw.iso', 'size_bytes': 1000, **body})


# ---------------------------------------------------------------- create

def test_create_records_an_incomplete_medium_and_returns_a_signed_resumable_url(world):
    response = _create(world, os_id=None)

    assert response.status_code == 200
    data = response.json()['data']
    media_id = data['media_id']
    assert data['upload_url'].startswith(f'https://storage.googleapis.com/{BUCKET}/media/{media_id}/fw.iso?')
    assert data['expires_in'] == NESTED_UPLOAD_URL_TTL_SECONDS
    record = world.db.media[media_id]
    assert record['complete'] is False
    assert record['format'] == 'iso'
    assert record['size_bytes'] == 1000
    assert record['uploaded_by'] == TEACHER.email
    assert record['gcs_path'] == f'gs://{BUCKET}/media/{media_id}/fw.iso'
    kwargs = world.gcs.blobs[f'media/{media_id}/fw.iso'].generate_signed_url.call_args.kwargs
    assert kwargs['version'] == 'v4'
    assert kwargs['method'] == 'POST'
    assert kwargs['expiration'].total_seconds() == NESTED_UPLOAD_URL_TTL_SECONDS
    assert kwargs['credentials'] == 'creds'
    headers = kwargs['headers']
    assert headers['x-goog-resumable'] == 'start'
    assert headers['x-goog-content-length-range'] == f'0,{NESTED_MEDIA_MAX_BYTES}'
    # Custom-Time starts the lifecycle clock and matches the record, so the browser gets the signed headers back.
    assert headers['x-goog-custom-time'] == record['uploaded_at']
    assert data['upload_headers'] == headers
    # The bucket's CORS list is built from the same names (setup: Nested Media Bucket).
    assert tuple(headers) == NESTED_MEDIA_SIGNED_HEADERS


def test_unsupported_extension_is_400_and_writes_nothing(world):
    response = _create(world, filename='setup.exe')

    assert response.status_code == 400
    assert 'Unsupported file type' in response.json()['detail']
    assert world.db.media == {}


def test_oversize_request_is_413_and_writes_nothing(world):
    response = _create(world, size_bytes=NESTED_MEDIA_MAX_BYTES + 1)

    assert response.status_code == 413
    assert world.db.media == {}
    assert world.gcs.blobs == {}


def test_exactly_the_limit_is_accepted(world):
    assert _create(world, size_bytes=NESTED_MEDIA_MAX_BYTES).status_code == 200


@pytest.mark.parametrize('filename', ['../etc/passwd.iso', 'dir/fw.iso', '.hidden.iso', ''])
def test_filename_with_a_path_is_rejected(world, filename):
    assert _create(world, filename=filename).status_code == 422
    assert world.db.media == {}


@pytest.mark.parametrize('size', [0, -1])
def test_non_positive_size_is_rejected(world, size):
    assert _create(world, size_bytes=size).status_code == 422


def test_format_the_catalog_entry_does_not_accept_is_400(world):
    response = _create(world, os_id='debian-12', filename='debian.iso')

    assert response.status_code == 400
    assert 'accepts qcow2' in response.json()['detail']
    assert world.db.media == {}


def test_unknown_os_id_is_400(world):
    assert _create(world, os_id='no-such-os').status_code == 400


def test_matching_os_id_is_recorded(world):
    response = _create(world, os_id='debian-12', filename='Debian 12.QCOW2')

    record = world.db.media[response.json()['data']['media_id']]
    assert (record['os_id'], record['format']) == ('debian-12', 'qcow2')


def test_signing_failure_is_503_and_leaves_no_record(world):
    world.gcs.sign_error = RuntimeError('iam.serviceAccounts.signBlob denied')

    response = _create(world)

    assert response.status_code == 503
    assert 'serviceAccountTokenCreator' in response.json()['detail']
    assert world.db.media == {}


def test_student_cannot_create(world):
    assert _create(world, user=STUDENT).status_code == 403


@pytest.mark.parametrize('filename, fmt', [
    ('kali.img.xz', 'img.xz'), ('ova.tar.xz', 'tar.xz'), ('disk.vhdx', 'vhdx'), ('disk.vhd', 'vhd'),
    ('WIN.ISO', 'iso'), ('a.7z', '7z'), ('a.xz', None), ('a.exe', None), ('iso', None),
])
def test_media_format_from_extension(filename, fmt):
    assert media_format(filename) == fmt


# ---------------------------------------------------------------- complete

def test_complete_marks_the_medium_after_checking_the_object_size(world):
    world.db.media['m1'] = _medium('m1')
    blob = world.gcs.upload('m1', 1000)

    response = _client(TEACHER).put('/compute/images/nested/media/m1/')

    assert response.status_code == 200
    assert response.json()['data']['complete'] is True
    assert world.db.media['m1']['complete'] is True
    # Moving Custom-Time to the far future keeps the lifecycle rule off a completed medium.
    assert blob.custom_time.isoformat() == NESTED_MEDIA_KEEP_CUSTOM_TIME.replace('Z', '+00:00')
    blob.patch.assert_called_once_with()


def test_complete_fails_when_the_object_is_missing(world):
    world.db.media['m1'] = _medium('m1')

    response = _client(TEACHER).put('/compute/images/nested/media/m1/')

    assert response.status_code == 400
    assert 'has not been uploaded' in response.json()['detail']
    assert world.db.media['m1']['complete'] is False


@pytest.mark.parametrize('size', [999, 1001])
def test_complete_fails_when_the_object_is_the_wrong_size(world, size):
    world.db.media['m1'] = _medium('m1')
    blob = world.gcs.upload('m1', size)

    response = _client(TEACHER).put('/compute/images/nested/media/m1/')

    assert response.status_code == 400
    assert f'{size} bytes in storage; 1000 were declared' in response.json()['detail']
    assert world.db.media['m1']['complete'] is False
    blob.patch.assert_not_called()


def test_complete_is_503_and_stays_incomplete_when_the_object_cannot_be_kept(world):
    world.db.media['m1'] = _medium('m1')
    world.gcs.upload('m1', 1000).patch.side_effect = GcsForbidden('denied')

    response = _client(TEACHER).put('/compute/images/nested/media/m1/')

    assert response.status_code == 503
    assert world.db.media['m1']['complete'] is False


def test_complete_unknown_media_is_404(world):
    assert _client(TEACHER).put('/compute/images/nested/media/nope/').status_code == 404


def test_complete_by_another_instructor_is_403(world):
    world.db.media['m1'] = _medium('m1')
    world.gcs.upload('m1', 1000)

    assert _client(OTHER).put('/compute/images/nested/media/m1/').status_code == 403
    assert world.db.media['m1']['complete'] is False


def test_complete_of_a_completed_medium_is_idempotent(world):
    world.db.media['m1'] = _medium('m1', complete=True)

    response = _client(TEACHER).put('/compute/images/nested/media/m1/')

    assert response.status_code == 200
    assert response.json()['data']['complete'] is True


# ---------------------------------------------------------------- list

def test_list_shows_completed_media_and_only_the_callers_incomplete_uploads(world):
    world.db.media.update({
        'mine-done': _medium('mine-done', complete=True, uploaded_at='2026-10-15T00:00:00Z'),
        'mine-partial': _medium('mine-partial', uploaded_at='2026-10-17T00:00:00Z'),
        'other-done': _medium('other-done', uploaded_by=OTHER.email, complete=True, uploaded_at='2026-10-16T00:00:00Z'),
        'other-partial': _medium('other-partial', uploaded_by=OTHER.email),
        'broken': {'id': 'broken'},
    })

    response = _client(TEACHER).get('/compute/images/nested/media/')

    assert response.status_code == 200
    # Newest first; a malformed record is skipped rather than failing the list.
    assert [m['id'] for m in response.json()['data']['items']] == ['mine-partial', 'other-done', 'mine-done']


def test_admin_list_includes_every_incomplete_upload(world):
    world.db.media.update({'a': _medium('a'), 'b': _medium('b', uploaded_by=OTHER.email)})

    items = _client(ADMIN).get('/compute/images/nested/media/').json()['data']['items']

    assert {m['id'] for m in items} == {'a', 'b'}


def test_student_cannot_list(world):
    assert _client(STUDENT).get('/compute/images/nested/media/').status_code == 403


# ---------------------------------------------------------------- delete

def test_uploader_deletes_the_object_and_the_record(world):
    world.db.media['m1'] = _medium('m1', complete=True)
    world.gcs.upload('m1', 1000)

    response = _client(TEACHER).delete('/compute/images/nested/media/m1/')

    assert response.status_code == 200
    assert 'm1' not in world.db.media
    assert world.gcs.objects == {}


def test_admin_deletes_another_users_media(world):
    world.db.media['m1'] = _medium('m1', uploaded_by=OTHER.email)
    world.gcs.upload('m1', 1000)

    assert _client(ADMIN).delete('/compute/images/nested/media/m1/').status_code == 200
    assert 'm1' not in world.db.media


def test_delete_of_a_never_uploaded_object_still_removes_the_record(world):
    world.db.media['m1'] = _medium('m1')

    assert _client(TEACHER).delete('/compute/images/nested/media/m1/').status_code == 200
    assert 'm1' not in world.db.media


def test_another_instructor_cannot_delete(world):
    world.db.media['m1'] = _medium('m1')
    world.gcs.upload('m1', 1000)

    assert _client(OTHER).delete('/compute/images/nested/media/m1/').status_code == 403
    assert 'm1' in world.db.media
    assert world.gcs.objects


def test_delete_unknown_media_is_404(world):
    assert _client(TEACHER).delete('/compute/images/nested/media/nope/').status_code == 404


# ---------------------------------------------------------------- signing

def test_metadata_credentials_sign_through_iam_with_their_own_token(monkeypatch):
    credentials = MagicMock(spec=['refresh', 'service_account_email', 'token'],
                            service_account_email='agoge-service@p.iam.gserviceaccount.com', token='tok')
    monkeypatch.setattr(media_module.google.auth, 'default', lambda scopes: (credentials, 'p'))

    kwargs = media_module.NestedMedia._signing_kwargs()

    credentials.refresh.assert_called_once()
    assert kwargs == {'service_account_email': 'agoge-service@p.iam.gserviceaccount.com', 'access_token': 'tok'}


def test_credentials_that_can_sign_are_used_directly(monkeypatch):
    credentials = MagicMock(spec=media_module.Signing)
    monkeypatch.setattr(media_module.google.auth, 'default', lambda scopes: (credentials, 'p'))

    assert media_module.NestedMedia._signing_kwargs() == {'credentials': credentials}

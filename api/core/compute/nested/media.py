"""Instructor media uploads for nested guests (PRD V15): signed resumable uploads into <project>_nested-media."""
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple, get_args

import google.auth
from google.api_core.exceptions import GoogleAPIError, NotFound as GcsNotFound
from google.auth.credentials import Signing
from google.auth.transport.requests import Request as AuthRequest
from google.cloud import storage

from common.constants.database import DATABASE_NAME, DatabaseTypes, DbCollections
from common.constants.nested import (NESTED_MEDIA_BUCKET_SUFFIX, NESTED_MEDIA_KEEP_CUSTOM_TIME, NESTED_MEDIA_MAX_BYTES,
                                     NESTED_UPLOAD_URL_TTL_SECONDS)
from common.document_database.factory import DocumentDatabaseFactory
from common.exceptions import BadRequest, ContentTooLarge, Forbidden, NotFound, ServiceUnavailable
from common.models.agoge import (NestedMediaCreateRequest, NestedMediaFormat, NestedMediaModel,
                                 NestedMediaUploadResponse, NestedOsCatalogModel)
from common.models.model_validators.model_validator import ModelValidator
from common.models.users import AgogeUser
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import Logger, LoggerNames
from common.utilities.id_generator import IdGenerator

# Longest first, so "disk.img.xz" is img.xz rather than an unknown "xz".
MEDIA_FORMATS: Tuple[str, ...] = tuple(sorted(get_args(NestedMediaFormat), key=len, reverse=True))


def media_format(filename: str) -> Optional[str]:
    lower = filename.lower()
    return next((fmt for fmt in MEDIA_FORMATS if lower.endswith(f'.{fmt}')), None)


class NestedMedia:
    def __init__(self, env_dict: dict, storage_client: storage.Client = None, db=None) -> None:
        self.class_name = self.__class__.__name__
        self.env = CloudEnv(log_name=LoggerNames.API, env_dict=env_dict)
        self.logger = Logger(LoggerNames.API, class_name=self.class_name)
        self.db = db or DocumentDatabaseFactory.create_db_object(
            DatabaseTypes.firestore, database_name=DATABASE_NAME, log_name=LoggerNames.API
        )
        self._storage = storage_client
        self.bucket_name = f'{self.env.project}_{NESTED_MEDIA_BUCKET_SUFFIX}'
        self.validator = ModelValidator(model=NestedMediaModel)
        self.catalog_validator = ModelValidator(model=NestedOsCatalogModel)

    @property
    def storage(self) -> storage.Client:
        if self._storage is None:
            self._storage = storage.Client(project=self.env.project)
        return self._storage

    def create_upload(self, user: AgogeUser, request: NestedMediaCreateRequest) -> NestedMediaUploadResponse:
        """Record an incomplete medium and return a signed URL that starts its resumable upload.

        Raises:
            BadRequest: Unsupported extension, or a format the catalog entry does not accept
            ContentTooLarge: size_bytes is over NESTED_MEDIA_MAX_BYTES
            ServiceUnavailable: The API service account could not sign the URL
        """
        fmt = media_format(request.filename)
        if fmt is None:
            raise BadRequest(f'Unsupported file type for {request.filename}. Use one of: {", ".join(sorted(MEDIA_FORMATS))}.')
        if request.size_bytes > NESTED_MEDIA_MAX_BYTES:
            raise ContentTooLarge(f'{request.filename} is {request.size_bytes} bytes; the limit is {NESTED_MEDIA_MAX_BYTES} (20 GiB).')
        if request.os_id:
            entry = self._catalog_entry(request.os_id)
            if fmt not in entry.media_formats:
                raise BadRequest(f'{entry.display_name} accepts {", ".join(entry.media_formats)} media, not {fmt}.')

        media_id = IdGenerator.uuid()
        object_name = f'media/{media_id}/{request.filename}'
        started = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        # The signature covers these headers, so the browser must send them unchanged. The range caps the object;
        # Custom-Time starts the bucket's two-day clock for an upload that is never completed.
        headers = {
            'x-goog-resumable': 'start',
            'x-goog-content-length-range': f'0,{NESTED_MEDIA_MAX_BYTES}',
            'x-goog-custom-time': started,
        }
        try:
            upload_url = self.storage.bucket(self.bucket_name).blob(object_name).generate_signed_url(
                version='v4', method='POST', expiration=timedelta(seconds=NESTED_UPLOAD_URL_TTL_SECONDS),
                headers=headers, **self._signing_kwargs(),
            )
        except Exception as e:
            self.logger.error(f'{self.class_name}:{media_id} - Could not sign the upload URL: {e}', user=user.uid)
            raise ServiceUnavailable('Could not sign the upload URL. The API service account needs '
                                     'roles/iam.serviceAccountTokenCreator on itself (setup: Nested Media Bucket).')

        medium = NestedMediaModel(
            id=media_id, filename=request.filename, format=fmt, size_bytes=request.size_bytes,
            gcs_path=f'gs://{self.bucket_name}/{object_name}', os_id=request.os_id,
            uploaded_by=user.email, uploaded_at=started,
        )
        # Written after signing, so a signing failure leaves no orphan record.
        self.db.insert(collection_name=DbCollections.NESTED_MEDIA, data=medium.model_dump(), id_field='id')
        self.logger.info(f'{self.class_name}:{media_id} - Upload started', user=user.uid,
                         filename=request.filename, size_bytes=request.size_bytes)
        return NestedMediaUploadResponse(media_id=media_id, upload_url=upload_url, upload_headers=headers,
                                         expires_in=NESTED_UPLOAD_URL_TTL_SECONDS)

    def complete(self, user: AgogeUser, media_id: str) -> NestedMediaModel:
        """Mark a medium complete once its object exists with the declared size.

        Raises:
            NotFound: No medium has this id
            Forbidden: The caller is neither the uploader nor an admin
            BadRequest: The object is missing or its size differs from size_bytes
            ServiceUnavailable: The object's Custom-Time could not be moved, so the lifecycle rule would delete it
        """
        medium = self._owned(user, media_id)
        if medium.complete:
            return medium
        blob = self.storage.bucket(self.bucket_name).get_blob(self._object_name(medium))
        if blob is None:
            raise BadRequest(f'{medium.filename} has not been uploaded yet.')
        if blob.size != medium.size_bytes:
            raise BadRequest(f'{medium.filename} is {blob.size} bytes in storage; {medium.size_bytes} were declared. '
                             'Delete it and upload again.')
        try:
            blob.custom_time = datetime.fromisoformat(NESTED_MEDIA_KEEP_CUSTOM_TIME)
            blob.patch()
        except GoogleAPIError as e:
            self.logger.error(f'{self.class_name}:{media_id} - Could not keep the object: {e}', user=user.uid)
            raise ServiceUnavailable(f'Could not mark {medium.filename} as kept; try again.')
        self.db.update(collection_name=DbCollections.NESTED_MEDIA, doc_id=media_id, data={'complete': True})
        self.logger.info(f'{self.class_name}:{media_id} - Upload complete', user=user.uid)
        return medium.model_copy(update={'complete': True})

    def list(self, user: AgogeUser) -> List[NestedMediaModel]:
        """Completed media are a shared library; incomplete uploads are shown only to their uploader (or an admin)."""
        records = self.db.query(collection_name=DbCollections.NESTED_MEDIA) or []
        media = [medium for medium in (self.validator.load(records, halt_on_error=False) or []) if medium]
        visible = [medium for medium in media if medium.complete or user.is_admin or medium.uploaded_by == user.email]
        return sorted(visible, key=lambda medium: medium.uploaded_at, reverse=True)

    def delete(self, user: AgogeUser, media_id: str) -> None:
        """Remove the object and the record.

        Raises:
            NotFound: No medium has this id
            Forbidden: The caller is neither the uploader nor an admin
        """
        medium = self._owned(user, media_id)
        try:
            self.storage.bucket(self.bucket_name).blob(self._object_name(medium)).delete()
        except GcsNotFound:
            # Never uploaded, or already removed by the incomplete-upload lifecycle rule.
            pass
        self.db.delete(collection_name=DbCollections.NESTED_MEDIA, doc_id=media_id)
        self.logger.info(f'{self.class_name}:{media_id} - Deleted', user=user.uid)

    def _owned(self, user: AgogeUser, media_id: str) -> NestedMediaModel:
        record = self.db.get(collection_name=DbCollections.NESTED_MEDIA, doc_id=media_id)
        medium = self.validator.load(record, halt_on_error=False) if record else None
        if not medium:
            raise NotFound(message=f'No media found for ID: {media_id}')
        if not (user.is_admin or medium.uploaded_by == user.email):
            raise Forbidden('Only the uploader or an admin can change this media.')
        return medium

    def _object_name(self, medium: NestedMediaModel) -> str:
        return medium.gcs_path.removeprefix(f'gs://{self.bucket_name}/')

    def _catalog_entry(self, os_id: str) -> NestedOsCatalogModel:
        record = self.db.get(collection_name=DbCollections.NESTED_OS_CATALOG, doc_id=os_id)
        entry = self.catalog_validator.load(record, halt_on_error=False) if record else None
        if not entry or not entry.is_enabled:
            raise BadRequest(f'os_id {os_id} is not an enabled catalog entry.')
        return entry

    @staticmethod
    def _signing_kwargs() -> dict:
        # Cloud Run's metadata credentials hold no private key, so the URL is signed through IAM signBlob with the
        # service account's own token; that call is what needs serviceAccountTokenCreator on itself.
        credentials, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
        if isinstance(credentials, Signing):
            return {'credentials': credentials}
        credentials.refresh(AuthRequest())
        return {'service_account_email': credentials.service_account_email, 'access_token': credentials.token}

from datetime import datetime, timedelta, timezone
from io import BytesIO
from mimetypes import guess_type
import json

from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from google.cloud import secretmanager, storage
from jwcrypto import jwk, jwt

from common.constants.database import DbCollections, DatabaseTypes, DATABASE_NAME
from common.document_database import DocumentDatabaseFactory
from common.exceptions import BadRequest, AgogeValidationError, NotFound
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import Logger, LoggerNames

class WebGL:
    def __init__(
            self,
            env_dict: dict,
    ) -> None:
        self.class_name = self.__class__.__name__
        self.log_name = LoggerNames.API
        self.collection = DbCollections.WEBXR
        self.env = CloudEnv(log_name=self.log_name, env_dict=env_dict)
        self.env_dict = self.env.get_env()
        self.logger = Logger(log_name=self.log_name, class_name=self.class_name)
        self.db = DocumentDatabaseFactory.create_db_object(
            DatabaseTypes.firestore,
            database_name=DATABASE_NAME,
            log_name=self.log_name,
        )

    def generate_jwt_token(self, buildId:str) -> str:
        if not self.db.get(collection_name=DbCollections.WORKOUT, doc_id=buildId):
            raise NotFound(f"Build ID '{buildId}' not found.")
        # Fetch secret from gcloud
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{self.env.project}/secrets/jwt_private_key/versions/latest"
        response = client.access_secret_version(name=name)
        # Generate JWK key from the secret
        private_key_pem = response.payload.data.decode("UTF-8")
        key = jwk.JWK.from_pem(private_key_pem.encode())

        # Give key 3 hour lifetime
        issued_at = datetime.now(timezone.utc)
        expiration = issued_at + timedelta(hours=3)

        # sub - Subject (buildId)
        # iat - Issued at Timestamp
        # exp - Expiration Timestamp
        payload = {
            "sub": buildId,
            "iat": int(issued_at.timestamp()),
            "exp": int(expiration.timestamp())
        }


        token = jwt.JWT(header={
            "alg": "RS256",
            "typ": "JWT",
            "kid": key.thumbprint()
        }, claims=payload)

        token.make_signed_token(key)
        return token.serialize()

    def serve_jwk(self) -> dict:
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{self.env.project}/secrets/jwt_public_key/versions/latest"
        response = client.access_secret_version(name=name)
        public_key_pem = response.payload.data.decode("UTF-8")

        key = jwk.JWK.from_pem(public_key_pem.encode())
        return {"keys": [json.loads(key.export_public())]}

    def save_score(
            self,
            data: dict,
    ) -> str:
        buildId = data['buildId']
        score = data['score']

        if not buildId or score is None:
            raise BadRequest(message="Missing or invalid data for required fields buildId, or score")

        try:
            self.db.update(
                collection_name=self.collection,
                doc_id=buildId,
                data={"id": buildId,"score": score},
            )
            self.logger.info(
                f"Saved WebXR score for {buildId} with score:{score}",
                buildId=buildId,
                score=score,
            )
            return buildId
        except Exception as e:
            self.logger.error(
                f"Failed to save WebXR score for {buildId} with score:{score}",
                buildId=buildId,
            )
            raise AgogeValidationError(f"Failed to save WebXR score with errors: {e}")
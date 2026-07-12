"""Cloudflare R2 file storage via the S3-compatible API (boto3)."""

from __future__ import annotations

from app.core.logging import get_logger

logger = get_logger(__name__)


class R2FileStore:
    """Upload / download / delete file bytes in a Cloudflare R2 bucket."""

    def __init__(
        self,
        account_id: str,
        access_key_id: str,
        secret_access_key: str,
        bucket_name: str,
    ) -> None:
        import boto3
        from botocore.config import Config

        self._bucket = bucket_name
        self._client = boto3.client(
            "s3",
            endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name="auto",
            config=Config(signature_version="s3v4"),
        )

    def upload(self, key: str, data: bytes, mime_type: str = "application/octet-stream") -> str:
        self._client.put_object(
            Bucket=self._bucket, Key=key, Body=data, ContentType=mime_type
        )
        logger.debug("R2 upload: %s (%d bytes)", key, len(data))
        return key

    def download(self, key: str) -> bytes:
        response = self._client.get_object(Bucket=self._bucket, Key=key)
        data: bytes = response["Body"].read()
        logger.debug("R2 download: %s (%d bytes)", key, len(data))
        return data

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)
        logger.debug("R2 delete: %s", key)

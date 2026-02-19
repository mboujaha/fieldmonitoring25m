from __future__ import annotations

import io
from urllib.parse import urljoin, urlparse

import boto3
from botocore.client import Config

from app.core.config import get_settings


def get_s3_client():
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=Config(signature_version="s3v4"),
    )


def get_s3_client_for_endpoint(endpoint_url: str):
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=Config(signature_version="s3v4"),
    )


def _known_s3_netlocs() -> set[str]:
    settings = get_settings()
    netlocs = {urlparse(settings.s3_endpoint_url).netloc}
    if settings.s3_public_endpoint_url:
        netlocs.add(urlparse(settings.s3_public_endpoint_url).netloc)
    return {netloc for netloc in netlocs if netloc}


def _default_public_endpoint_url() -> str:
    settings = get_settings()
    if settings.s3_public_endpoint_url:
        return settings.s3_public_endpoint_url

    endpoint = urlparse(settings.s3_endpoint_url)
    if endpoint.hostname == "minio":
        public_host = "localhost"
        public_port = f":{endpoint.port}" if endpoint.port else ""
        return f"{endpoint.scheme}://{public_host}{public_port}"

    return settings.s3_endpoint_url


def upload_bytes(key: str, payload: bytes, content_type: str) -> str:
    settings = get_settings()
    s3 = get_s3_client()
    s3.put_object(Bucket=settings.s3_bucket, Key=key, Body=io.BytesIO(payload), ContentType=content_type)
    endpoint = settings.s3_endpoint_url.rstrip("/") + "/"
    return urljoin(endpoint, f"{settings.s3_bucket}/{key}")


def build_object_key(prefix: str, object_id: str, extension: str) -> str:
    clean_extension = extension.lstrip(".")
    return f"{prefix}/{object_id}.{clean_extension}"


def try_extract_bucket_key(uri: str) -> str | None:
    settings = get_settings()
    parsed = urlparse(uri)
    if parsed.netloc not in _known_s3_netlocs():
        return None

    prefix = f"/{settings.s3_bucket}/"
    if not parsed.path.startswith(prefix):
        return None

    key = parsed.path[len(prefix):]
    return key or None


def download_bytes(uri: str) -> bytes:
    key = try_extract_bucket_key(uri)
    if key is None:
        raise ValueError("URI is not in configured object storage bucket")

    settings = get_settings()
    s3 = get_s3_client()
    response = s3.get_object(Bucket=settings.s3_bucket, Key=key)
    return response["Body"].read()


def create_presigned_get_url(uri: str, expires_seconds: int = 900, external: bool = False) -> str:
    key = try_extract_bucket_key(uri)
    if key is None:
        return uri

    settings = get_settings()
    endpoint = _default_public_endpoint_url() if external else settings.s3_endpoint_url
    s3 = get_s3_client_for_endpoint(endpoint)
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": key},
        ExpiresIn=expires_seconds,
    )

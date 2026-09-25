"""Serve the built dashboard from a private S3 bucket through the HTTP API.

Used when CloudFront isn't available (config.yaml: web.hosting = api). SPA routing: unknown
paths without a file extension fall back to index.html. Hashed /assets/* files are cached
for a year; index.html is never cached so deploys show up immediately.
"""

from __future__ import annotations

import base64
import mimetypes
import os
from pathlib import PurePosixPath

import boto3
from botocore.exceptions import ClientError

s3 = boto3.client("s3")

TEXT_TYPES = ("text/", "application/javascript", "application/json", "image/svg+xml")
_cache: dict[str, tuple[bytes, str]] = {}


def object_key(raw_path: str) -> str:
    """Map a request path to a bucket key, rejecting traversal."""
    parts = [p for p in PurePosixPath("/" + raw_path.lstrip("/")).parts[1:] if p not in ("", ".")]
    if ".." in parts:
        raise ValueError("invalid path")
    key = "/".join(parts)
    if not key or not PurePosixPath(key).suffix:
        return "index.html"
    return key


def content_type(key: str) -> str:
    if key.endswith(".js"):
        return "application/javascript"
    return mimetypes.guess_type(key)[0] or "application/octet-stream"


def fetch(key: str) -> tuple[bytes, str] | None:
    if key in _cache:
        return _cache[key]
    try:
        body = s3.get_object(Bucket=os.environ["SITE_BUCKET"], Key=key)["Body"].read()
    except ClientError as err:
        if err.response["Error"]["Code"] in ("NoSuchKey", "AccessDenied"):
            return None
        raise
    result = (body, content_type(key))
    if key.startswith("assets/"):  # content-hashed, safe to keep for the container's lifetime
        _cache[key] = result
    return result


def handler(event: dict, _context: object) -> dict:
    try:
        key = object_key(event.get("rawPath", "/"))
    except ValueError:
        return {"statusCode": 400, "body": "bad request"}
    found = fetch(key)
    if found is None:
        return {"statusCode": 404, "headers": {"Content-Type": "text/plain"}, "body": "not found"}
    body, mime = found
    headers = {
        "Content-Type": mime,
        "Cache-Control": "public, max-age=31536000, immutable" if key.startswith("assets/") else "no-cache",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "strict-origin-when-cross-origin",
    }
    if mime.startswith(TEXT_TYPES):
        return {"statusCode": 200, "headers": headers, "body": body.decode("utf-8")}
    return {"statusCode": 200, "headers": headers, "body": base64.b64encode(body).decode(), "isBase64Encoded": True}

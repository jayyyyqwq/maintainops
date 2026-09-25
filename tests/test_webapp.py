from __future__ import annotations

import base64
import io
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

import webapp.handler as webapp


@pytest.mark.parametrize(
    ("path", "key"),
    [
        ("/", "index.html"),
        ("/machines/m3", "index.html"),  # SPA route
        ("/assets/index-abc.js", "assets/index-abc.js"),
        ("//assets/./app.css", "assets/app.css"),
    ],
)
def test_object_key(path, key):
    assert webapp.object_key(path) == key


def test_path_traversal_rejected():
    with pytest.raises(ValueError):
        webapp.object_key("/assets/../../etc/passwd")
    assert webapp.handler({"rawPath": "/../secret.txt"}, None)["statusCode"] == 400


@pytest.fixture
def s3(monkeypatch):
    monkeypatch.setenv("SITE_BUCKET", "site")
    client = MagicMock()
    monkeypatch.setattr(webapp, "s3", client)
    webapp._cache.clear()
    return client


def test_serves_text_with_cache_headers(s3):
    s3.get_object.return_value = {"Body": io.BytesIO(b"console.log(1)")}
    response = webapp.handler({"rawPath": "/assets/index-abc.js"}, None)
    assert response["body"] == "console.log(1)"
    assert response["headers"]["Content-Type"] == "application/javascript"
    assert "immutable" in response["headers"]["Cache-Control"]


def test_index_is_not_cached(s3):
    s3.get_object.return_value = {"Body": io.BytesIO(b"<html></html>")}
    response = webapp.handler({"rawPath": "/"}, None)
    assert response["headers"]["Cache-Control"] == "no-cache"


def test_binary_is_base64(s3):
    s3.get_object.return_value = {"Body": io.BytesIO(b"\x89PNG")}
    response = webapp.handler({"rawPath": "/logo.png"}, None)
    assert response["isBase64Encoded"] is True
    assert base64.b64decode(response["body"]) == b"\x89PNG"


def test_missing_file_404(s3):
    s3.get_object.side_effect = ClientError({"Error": {"Code": "NoSuchKey", "Message": ""}}, "GetObject")
    assert webapp.handler({"rawPath": "/favicon.ico"}, None)["statusCode"] == 404

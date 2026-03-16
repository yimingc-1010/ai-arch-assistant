"""Tests for POST /rag/sync webhook endpoint."""

from __future__ import annotations

import hashlib
import hmac
import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


BODY = b"{}"
SECRET = "test-webhook-secret"


def _make_sig(body: bytes, secret: str) -> str:
    mac = hmac.new(secret.encode(), body, hashlib.sha256)
    return f"sha256={mac.hexdigest()}"


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", SECRET)
    monkeypatch.setenv("LAWRAG_CHROMA_DIR", "/tmp/test-chroma")
    monkeypatch.setenv("LAWRAG_LAWS_DIR", "/tmp/test-laws")
    from autocrawler_api.app import create_app
    return TestClient(create_app())


class TestSyncRoute:
    def test_valid_signature_returns_202(self, client):
        sig = _make_sig(BODY, SECRET)
        with patch("autocrawler_api.routes.sync._run_sync_background"):
            resp = client.post(
                "/rag/sync",
                content=BODY,
                headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"},
            )
        assert resp.status_code == 202
        assert resp.json()["status"] == "sync started"

    def test_invalid_signature_returns_401(self, client):
        resp = client.post(
            "/rag/sync",
            content=BODY,
            headers={"X-Hub-Signature-256": "sha256=wronghex", "Content-Type": "application/json"},
        )
        assert resp.status_code == 401

    def test_missing_signature_header_returns_401(self, client):
        resp = client.post("/rag/sync", content=BODY)
        assert resp.status_code == 401

    def test_no_secret_configured_returns_500(self, monkeypatch):
        monkeypatch.delenv("GITHUB_WEBHOOK_SECRET", raising=False)
        monkeypatch.setenv("LAWRAG_CHROMA_DIR", "/tmp/test-chroma")
        monkeypatch.setenv("LAWRAG_LAWS_DIR", "/tmp/test-laws")
        from autocrawler_api.app import create_app
        client = TestClient(create_app())
        resp = client.post(
            "/rag/sync",
            content=BODY,
            headers={"X-Hub-Signature-256": "sha256=anything"},
        )
        assert resp.status_code == 500

    def test_sync_dispatched_as_background_task(self, client):
        """Verify _run_sync_background is scheduled (not called inline before 202 returns)."""
        sig = _make_sig(BODY, SECRET)
        with patch("autocrawler_api.routes.sync._run_sync_background") as mock_sync:
            resp = client.post(
                "/rag/sync",
                content=BODY,
                headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"},
            )
        assert resp.status_code == 202
        mock_sync.assert_called_once()

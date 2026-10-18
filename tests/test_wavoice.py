"""Unit and integration tests for wa-voice."""

import hashlib
import hmac
import subprocess
import pytest
from httpx import ASGITransport, AsyncClient

from wavoice.core.config import settings
from wavoice.core.ice import build_ice_servers
from wavoice.core.lifecycle import CallClaimManager
from wavoice.core.tunnel import ensure_cloudflared_binary
from wavoice.server.app import create_app
from wavoice.server.security import verify_whatsapp_signature
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_webhook_get_verification_success():
    """Verify that Meta's hub.challenge GET request returns 200 and the challenge string."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        params = {
            "hub.mode": "subscribe",
            "hub.verify_token": settings.whatsapp_verify_token,
            "hub.challenge": "test_challenge_12345",
        }
        resp = await client.get("/webhook", params=params)
        assert resp.status_code == 200
        assert resp.text == "test_challenge_12345"


@pytest.mark.asyncio
async def test_webhook_get_verification_invalid_token():
    """Verify that a mismatched verify token returns 403 Forbidden."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        params = {
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong_token",
            "hub.challenge": "test_challenge_12345",
        }
        resp = await client.get("/webhook", params=params)
        assert resp.status_code == 403


def test_hmac_signature_verification():
    """Verify HMAC-SHA256 signature validation accepts valid and rejects tampered payloads."""
    secret = "my_meta_secret_123"
    body = b'{"object":"whatsapp_business_account"}'

    # Valid signature
    sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    verify_whatsapp_signature(app_secret=secret, raw_body=body, signature_header=f"sha256={sig}")

    # Tampered body
    with pytest.raises(HTTPException) as exc_info:
        verify_whatsapp_signature(
            app_secret=secret,
            raw_body=b'{"object":"tampered"}',
            signature_header=f"sha256={sig}",
        )
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_call_claim_deduplication():
    """Verify atomic call claiming prevents duplicate connect delivery race conditions."""
    manager = CallClaimManager(ttl_seconds=60)
    call_id = "call_abc_123"

    # First delivery wins the claim
    claimed_first = await manager.claim_call(call_id)
    assert claimed_first is True

    # Immediate duplicate delivery from Meta is rejected
    claimed_second = await manager.claim_call(call_id)
    assert claimed_second is False

    # After finishing the call, claim is cleared
    await manager.release_claim(call_id)
    claimed_after_release = await manager.claim_call(call_id)
    assert claimed_after_release is True


def test_cloudflared_binary_execution():
    """Verify the automatically downloaded cloudflared binary runs on this OS."""
    binary = ensure_cloudflared_binary()
    assert binary.exists()

    result = subprocess.run([str(binary), "--version"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "cloudflared version" in result.stdout.lower()


def test_ice_servers_builder():
    """Verify STUN / TURN server candidate builder output."""
    # STUN default
    servers = build_ice_servers(stun_url="stun:stun.l.google.com:19302")
    assert len(servers) >= 1
    assert "stun:stun.l.google.com:19302" in servers[0].urls

    # With TURN
    servers_with_turn = build_ice_servers(
        stun_url="stun:stun.l.google.com:19302",
        turn_url="turn:turn.test.com:3478",
        turn_username="user1",
        turn_password="pass1",
    )
    assert len(servers_with_turn) == 2
    assert servers_with_turn[1].username == "user1"


@pytest.mark.asyncio
async def test_webhook_rejects_payload_too_large():
    """Verify that requests exceeding 1MB payload limit return 413 Payload Too Large."""
    app = create_app()
    transport = ASGITransport(app=app)
    large_body = b"x" * (1_048_576 + 10)  # > 1MB
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/webhook", content=large_body)
        assert resp.status_code == 413
        assert "Payload too large" in resp.text


@pytest.mark.asyncio
async def test_webhook_rejects_content_length_header_too_large():
    """Verify that requests advertising Content-Length > 1MB are rejected early with 413."""
    app = create_app()
    transport = ASGITransport(app=app)
    headers = {"content-length": "2000000"}  # 2MB
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/webhook", content=b"{}", headers=headers)
        assert resp.status_code == 413


def test_env_file_permissions_restricted(tmp_path, monkeypatch):
    """Verify that _update_env sets 0o600 (owner read/write only) on .env."""
    import os
    from wavoice.cli import _update_env

    test_env = tmp_path / ".env"
    monkeypatch.chdir(tmp_path)

    _update_env({"TEST_SECRET": "my_secret_token_123"})
    assert test_env.exists()

    mode = os.stat(test_env).st_mode & 0o777
    assert mode == 0o600


"""Tests for LiveKit Cloud WhatsApp integration."""

import hashlib
import hmac
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from httpx import ASGITransport, AsyncClient

from wavoice.core.config import Settings
from wavoice.providers.livekit.client import LiveKitCloudClient, LiveKitClientError
from wavoice.providers.livekit.detector import parse_livekit_env_block
from wavoice.providers.livekit.provider import LiveKitProvider
from wavoice.providers.livekit.webhook import create_livekit_app


def test_parse_livekit_env_block():
    """Verify parsing credentials from a pasted .env block."""
    raw_block = """
    # LiveKit Cloud Project
    LIVEKIT_URL="wss://my-test-proj.livekit.cloud"
    LIVEKIT_API_KEY=APIxxxxxxxxxxxxxx
    LIVEKIT_API_SECRET='secret_key_123456789'
    """
    parsed = parse_livekit_env_block(raw_block)
    assert parsed["LIVEKIT_URL"] == "wss://my-test-proj.livekit.cloud"
    assert parsed["LIVEKIT_API_KEY"] == "APIxxxxxxxxxxxxxx"
    assert parsed["LIVEKIT_API_SECRET"] == "secret_key_123456789"


@pytest.mark.asyncio
async def test_livekit_client_accept_call():
    """Verify accept_whatsapp_call builds the protobuf request properly."""
    client = LiveKitCloudClient(
        url="wss://test.livekit.cloud",
        api_key="API123",
        api_secret="SEC456",
    )

    mock_api = MagicMock()
    mock_connector = MagicMock()
    mock_connector.accept_whatsapp_call = AsyncMock(return_value=MagicMock())
    mock_api.connector = mock_connector

    with patch.object(client, "get_api", return_value=mock_api):
        await client.accept_whatsapp_call(
            whatsapp_phone_number_id="phone_123",
            whatsapp_api_key="meta_token_abc",
            whatsapp_call_id="call_999",
            sdp_offer="v=0\r\no=...",
            room_name="wa-call-999",
            caller_phone="+15551234",
        )

        assert mock_connector.accept_whatsapp_call.called
        req = mock_connector.accept_whatsapp_call.call_args[0][0]
        assert req.whatsapp_phone_number_id == "phone_123"
        assert req.whatsapp_api_key == "meta_token_abc"
        assert req.whatsapp_cloud_api_version == "23.0"
        assert req.whatsapp_call_id == "call_999"
        assert req.room_name == "wa-call-999"
        assert req.participant_identity == "+15551234"
        assert req.sdp.type == "offer"
        assert req.sdp.sdp == "v=0\r\no=..."
        assert len(req.agents) == 1
        assert req.agents[0].agent_name == "wavoice-agent"


@pytest.mark.asyncio
async def test_livekit_client_disconnect_call():
    """Verify disconnect_whatsapp_call builds the protobuf request properly."""
    client = LiveKitCloudClient(
        url="wss://test.livekit.cloud",
        api_key="API123",
        api_secret="SEC456",
    )

    mock_api = MagicMock()
    mock_connector = MagicMock()
    mock_connector.disconnect_whatsapp_call = AsyncMock(return_value=MagicMock())
    mock_api.connector = mock_connector

    with patch.object(client, "get_api", return_value=mock_api):
        await client.disconnect_whatsapp_call(
            whatsapp_call_id="call_999",
            whatsapp_api_key="meta_token_abc",
            user_initiated=True,
        )

        assert mock_connector.disconnect_whatsapp_call.called
        req = mock_connector.disconnect_whatsapp_call.call_args[0][0]
        assert req.whatsapp_call_id == "call_999"
        assert req.whatsapp_api_key == "meta_token_abc"
        assert req.disconnect_reason == 1  # USER_INITIATED


@pytest.mark.asyncio
async def test_livekit_webhook_get_handshake():
    """Verify hub.challenge handshake on LiveKit webhook app."""
    cfg = Settings(
        livekit_url="wss://test.livekit.cloud",
        livekit_api_key="API123",
        livekit_api_secret="SEC456",
    )
    app = create_livekit_app(config=cfg)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/webhook", params={
            "hub.mode": "subscribe",
            "hub.verify_token": cfg.whatsapp_verify_token,
            "hub.challenge": "challenge_livekit_abc",
        })
        assert resp.status_code == 200
        assert resp.text == "challenge_livekit_abc"


@pytest.mark.asyncio
async def test_livekit_webhook_inbound_call_dispatch():
    """Verify incoming connect event triggers LiveKit accept_whatsapp_call."""
    cfg = Settings(
        whatsapp_token="meta_token_xyz",
        whatsapp_phone_number_id="phone_888",
        whatsapp_app_secret="test_app_secret",
        livekit_url="wss://test.livekit.cloud",
        livekit_api_key="API123",
        livekit_api_secret="SEC456",
    )

    mock_lk_client = MagicMock()
    mock_lk_client.accept_whatsapp_call = AsyncMock()

    app = create_livekit_app(config=cfg, client=mock_lk_client)
    transport = ASGITransport(app=app)

    body = b"""{
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "waba_1",
            "changes": [{
                "value": {
                    "call": {
                        "id": "call_test_123",
                        "event": "connect",
                        "from": "+15550001",
                        "sdp": "v=0\\r\\no=offer..."
                    }
                }
            }]
        }]
    }"""

    sig = hmac.new(b"test_app_secret", body, hashlib.sha256).hexdigest()
    headers = {"x-hub-signature-256": f"sha256={sig}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/webhook", content=body, headers=headers)
        assert resp.status_code == 200

    # Yield control to allow background task to run
    import asyncio
    await asyncio.sleep(0.05)

    assert mock_lk_client.accept_whatsapp_call.called
    kwargs = mock_lk_client.accept_whatsapp_call.call_args[1]
    assert kwargs["whatsapp_call_id"] == "call_test_123"
    assert kwargs["caller_phone"] == "+15550001"
    assert kwargs["room_name"] == "wa-call-call_test_123"


@pytest.mark.asyncio
async def test_livekit_webhook_inbound_call_with_session_sdp():
    """Verify incoming connect event with Meta's session.sdp payload."""
    cfg = Settings(
        whatsapp_token="meta_token_xyz",
        whatsapp_phone_number_id="phone_888",
        whatsapp_app_secret=None,
        livekit_url="wss://test.livekit.cloud",
        livekit_api_key="API123",
        livekit_api_secret="SEC456",
    )

    mock_lk_client = MagicMock()
    mock_lk_client.accept_whatsapp_call = AsyncMock()

    app = create_livekit_app(config=cfg, client=mock_lk_client)
    transport = ASGITransport(app=app)

    body = b"""{
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "waba_1",
            "changes": [{
                "value": {
                    "calls": [{
                        "id": "wacid.123456",
                        "event": "connect",
                        "from": "919999999999",
                        "session": {
                            "sdp": "v=0\\r\\no=meta_offer...",
                            "sdp_type": "offer"
                        }
                    }]
                }
            }]
        }]
    }"""

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/webhook", content=body)
        assert resp.status_code == 200

    import asyncio
    await asyncio.sleep(0.05)

    assert mock_lk_client.accept_whatsapp_call.called
    kwargs = mock_lk_client.accept_whatsapp_call.call_args[1]
    assert kwargs["whatsapp_call_id"] == "wacid.123456"
    assert kwargs["sdp_offer"] == "v=0\r\no=meta_offer..."
    assert kwargs["caller_phone"] == "919999999999"


@pytest.mark.asyncio
async def test_livekit_provider_doctor():
    """Verify LiveKitProvider doctor checks."""
    # When missing credentials
    empty_cfg = Settings(livekit_url=None, livekit_api_key=None, livekit_api_secret=None)
    with patch("wavoice.providers.livekit.provider.detect_local_livekit_config", return_value=None):
        provider = LiveKitProvider(config=empty_cfg)
        diag = await provider.doctor()
        assert "credentials" in diag
        ok, _ = diag["credentials"]
        assert ok is False

    # When credentials present and connection mocked
    valid_cfg = Settings(
        livekit_url="wss://test.livekit.cloud",
        livekit_api_key="API1234567890",
        livekit_api_secret="SEC456",
    )
    provider_valid = LiveKitProvider(config=valid_cfg)
    mock_client = MagicMock()
    mock_client.validate_connection = AsyncMock(return_value={"api_key": "API123...", "active_rooms": 0})
    mock_client.close = AsyncMock()
    with patch.object(provider_valid, "get_client", return_value=mock_client):
        diag_valid = await provider_valid.doctor()
        assert diag_valid["credentials"][0] is True
        assert diag_valid["connectivity"][0] is True

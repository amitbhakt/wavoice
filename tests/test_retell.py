"""Unit tests for Retell AI Provider and SIP Integration."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from wavoice.core.config import Settings
from wavoice.core.meta import MetaGraphClient
from wavoice.providers.retell.client import RetellClient, RetellClientError
from wavoice.providers.retell.provider import RetellProvider


@pytest.fixture
def mock_retell_settings():
    return Settings(
        whatsapp_token="mock_meta_token",
        whatsapp_phone_number_id="1234567890",
        retell_api_key="mock_retell_key",
        retell_agent_id="mock_agent_123",
        cloudonix_domain="sip.cloudonix.io",
    )


@pytest.mark.asyncio
async def test_meta_enable_sip_calling():
    """Test that enable_sip_calling constructs the correct Graph API payload."""
    mock_session = MagicMock()
    mock_session.closed = False
    mock_post = MagicMock()
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value={"success": True})
    mock_post.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_post.__aexit__ = AsyncMock(return_value=None)
    mock_session.post = MagicMock(return_value=mock_post)

    client = MetaGraphClient(access_token="fake_token", session=mock_session)

    res = await client.enable_sip_calling("phone_123", sip_host="sip.cloudonix.io", sip_port=5061)
    assert res is True

    # Verify payload format
    call_args = mock_session.post.call_args
    assert "https://graph.facebook.com/v21.0/phone_123/settings" in call_args[0][0]
    payload = call_args[1]["json"]
    assert payload["calling"]["status"] == "ENABLED"
    assert payload["calling"]["sip"]["status"] == "ENABLED"
    assert payload["calling"]["sip"]["servers"][0]["hostname"] == "sip.cloudonix.io"
    assert payload["calling"]["sip"]["servers"][0]["port"] == 5061


@pytest.mark.asyncio
async def test_retell_client_validate_connection_success():
    """Test RetellClient.validate_connection with valid credentials."""
    mock_session = MagicMock()
    mock_get = MagicMock()
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value=[{"agent_id": "agent_1"}, {"agent_id": "agent_2"}])
    mock_get.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_get.__aexit__ = AsyncMock(return_value=None)
    mock_session.get = MagicMock(return_value=mock_get)

    client = RetellClient(api_key="valid_key")
    with patch.object(client, "_get_session", AsyncMock(return_value=mock_session)):
        res = await client.validate_connection()
        assert res["valid"] is True
        assert res["agent_count"] == 2


@pytest.mark.asyncio
async def test_retell_client_validate_connection_unauthorized():
    """Test RetellClient.validate_connection handles 401 error."""
    mock_session = MagicMock()
    mock_get = MagicMock()
    mock_resp = AsyncMock()
    mock_resp.status = 401
    mock_get.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_get.__aexit__ = AsyncMock(return_value=None)
    mock_session.get = MagicMock(return_value=mock_get)

    client = RetellClient(api_key="bad_key")
    with patch.object(client, "_get_session", AsyncMock(return_value=mock_session)):
        with pytest.raises(RetellClientError, match="invalid or unauthorized"):
            await client.validate_connection()


@pytest.mark.asyncio
async def test_retell_client_get_agent():
    """Test RetellClient.get_agent returns agent info."""
    mock_session = MagicMock()
    mock_get = MagicMock()
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value={"agent_id": "agent_123", "agent_name": "Sales Rep"})
    mock_get.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_get.__aexit__ = AsyncMock(return_value=None)
    mock_session.get = MagicMock(return_value=mock_get)

    client = RetellClient(api_key="valid_key")
    with patch.object(client, "_get_session", AsyncMock(return_value=mock_session)):
        agent = await client.get_agent("agent_123")
        assert agent["agent_name"] == "Sales Rep"
        assert agent["agent_id"] == "agent_123"


@pytest.mark.asyncio
async def test_retell_client_import_phone_number():
    """Test RetellClient.import_phone_number invokes correct payload."""
    mock_session = MagicMock()
    mock_post = MagicMock()
    mock_resp = AsyncMock()
    mock_resp.status = 201
    mock_resp.json = AsyncMock(return_value={"phone_number": "+1234567890", "inbound_agent_id": "agent_123"})
    mock_post.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_post.__aexit__ = AsyncMock(return_value=None)
    mock_session.post = MagicMock(return_value=mock_post)

    client = RetellClient(api_key="valid_key")
    with patch.object(client, "_get_session", AsyncMock(return_value=mock_session)):
        res = await client.import_phone_number(
            phone_number="+1234567890",
            inbound_agent_id="agent_123",
            termination_uri="sip.cloudonix.io",
        )
        assert res["phone_number"] == "+1234567890"

        call_args = mock_session.post.call_args
        payload = call_args[1]["json"]
        assert payload["phone_number"] == "+1234567890"
        assert payload["inbound_agents"][0]["agent_id"] == "agent_123"
        assert payload["termination_uri"] == "sip.cloudonix.io"


@pytest.mark.asyncio
async def test_retell_provider_setup_flow(mock_retell_settings):
    """Test end-to-end setup flow in RetellProvider."""
    provider = RetellProvider(config=mock_retell_settings)

    mock_retell_client = MagicMock()
    mock_retell_client.get_agent = AsyncMock(return_value={"agent_id": "mock_agent_123", "agent_name": "Support Bot"})
    mock_retell_client.import_phone_number = AsyncMock(return_value={"phone_number": "+1234567890", "status": "registered"})
    provider._client = mock_retell_client

    with patch("wavoice.providers.retell.provider.MetaGraphClient") as MockMeta:
        mock_meta_instance = AsyncMock()
        mock_meta_instance.enable_sip_calling = AsyncMock(return_value=True)
        mock_meta_instance.close = AsyncMock()
        MockMeta.return_value = mock_meta_instance

        result = await provider.setup(meta_info={"phone_id": "phone_999", "display_phone_number": "+1234567890"})

        assert result["provider"] == "retell"
        assert result["agent_name"] == "Support Bot"
        assert result["phone_number"] == "+1234567890"
        assert result["sip_gateway"] == "sip.cloudonix.io:5061"

        mock_retell_client.get_agent.assert_called_once_with("mock_agent_123")
        mock_retell_client.import_phone_number.assert_called_once()
        mock_meta_instance.enable_sip_calling.assert_called_once_with(
            phone_number_id="phone_999",
            sip_host="sip.cloudonix.io",
            sip_port=5061,
        )


@pytest.mark.asyncio
async def test_retell_provider_doctor():
    """Test RetellProvider doctor health checks."""
    settings_no_key = Settings(retell_api_key=None)
    provider_fail = RetellProvider(config=settings_no_key)
    res_fail = await provider_fail.doctor()
    assert res_fail["credentials"][0] is False

    settings_with_key = Settings(retell_api_key="valid_key", retell_agent_id="agent_123")
    provider_ok = RetellProvider(config=settings_with_key)
    mock_client = MagicMock()
    mock_client.validate_connection = AsyncMock(return_value={"valid": True, "agent_count": 3})
    mock_client.get_agent = AsyncMock(return_value={"agent_name": "Test Bot"})
    mock_client.close = AsyncMock()
    provider_ok._client = mock_client

    res_ok = await provider_ok.doctor()
    assert res_ok["credentials"][0] is True
    assert res_ok["agent"][0] is True
    assert "Test Bot" in res_ok["agent"][1]

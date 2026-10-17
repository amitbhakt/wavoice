"""Tests for Dograh Cloud integration and workflow provisioning."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from wavoice.providers.dograh import DograhCloudClient, DograhAPIError, DograhProvider
from wavoice.core.config import Settings


@pytest.mark.asyncio
async def test_dograh_webhook_url():
    client = DograhCloudClient(api_key="dograh_key_123", base_url="https://api.dograh.com")
    assert client.get_whatsapp_webhook_url() == "https://api.dograh.com/api/v1/telephony/whatsapp/webhook"


@pytest.mark.asyncio
async def test_create_telephony_configuration_payload():
    client = DograhCloudClient(api_key="dograh_key_123")
    
    mock_response = {
        "id": 42,
        "name": "WhatsApp - +123456789",
        "provider": "whatsapp",
        "credentials": {
            "webhook_verify_token": "secret_verify_token_xyz"
        }
    }
    
    with patch.object(client, "_request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = mock_response
        result = await client.create_telephony_configuration(
            name="WhatsApp - +123456789",
            access_token="meta_token_abc",
            waba_id="waba_123",
            app_secret="app_secret_456",
        )
        assert result["id"] == 42
        assert result["credentials"]["webhook_verify_token"] == "secret_verify_token_xyz"
        
        mock_req.assert_awaited_once_with(
            "POST",
            "/api/v1/organizations/telephony-configs",
            json_data={
                "name": "WhatsApp - +123456789",
                "is_default_outbound": False,
                "config": {
                    "provider": "whatsapp",
                    "access_token": "meta_token_abc",
                    "waba_id": "waba_123",
                    "app_secret": "app_secret_456",
                },
            },
        )


@pytest.mark.asyncio
async def test_sample_workflow_structure():
    client = DograhCloudClient(api_key="dograh_key_123")
    
    mock_response = {"id": 101, "name": "WhatsApp Voice Assistant"}
    
    with patch.object(client, "_request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = mock_response
        result = await client.create_sample_whatsapp_workflow("WhatsApp Voice Assistant")
        assert result["id"] == 101
        
        # Verify payload passed to Dograh API
        call_args = mock_req.await_args
        method, path = call_args[0]
        json_data = call_args[1]["json_data"]
        
        assert method == "POST"
        assert path == "/api/v1/workflow/create/definition"
        assert json_data["name"] == "WhatsApp Voice Assistant"
        
        nodes = json_data["workflow_definition"]["nodes"]
        node_types = [n["type"] for n in nodes]
        assert node_types == ["startCall", "agentNode", "endCall"]
        
        # Verify starting greeting prompt includes the requested text
        start_node = next(n for n in nodes if n["type"] == "startCall")
        assert start_node["data"]["greeting_type"] == "text"
        assert "Hello! You have successfully connected WhatsApp AI calling via Dograh" in start_node["data"]["greeting"]
        
        # Verify edges exist
        edges = json_data["workflow_definition"]["edges"]
        assert len(edges) == 2
        assert edges[0]["source"] == "start-node"
        assert edges[0]["target"] == "agent-node"
        assert edges[1]["source"] == "agent-node"
        assert edges[1]["target"] == "end-node"


@pytest.mark.asyncio
async def test_publish_workflow_success():
    client = DograhCloudClient(api_key="dograh_key_123")
    with patch.object(client, "_request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = {"status": "published", "version": 1}
        resp = await client.publish_workflow(13625)
        assert resp["status"] == "published"
        mock_req.assert_awaited_once_with("POST", "/api/v1/workflow/13625/publish", json_data={})


@pytest.mark.asyncio
async def test_publish_workflow_no_draft_graceful():
    client = DograhCloudClient(api_key="dograh_key_123")
    with patch.object(client, "_request", new_callable=AsyncMock) as mock_req:
        mock_req.side_effect = DograhAPIError("No draft to publish", status_code=400)
        resp = await client.publish_workflow(13625)
        assert resp["status"] == "published"
        assert resp["workflow_id"] == 13625


@pytest.mark.asyncio
async def test_dograh_provider_validate_credentials():
    cfg = Settings(dograh_api_key="test_dograh_key")
    provider = DograhProvider(config=cfg)
    
    with patch.object(provider.get_client(), "list_telephony_configurations", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = [{"id": 1, "name": "Test Config"}]
        res = await provider.validate_credentials()
        assert res["status"] == "connected"
        assert res["configurations_count"] == 1


@pytest.mark.asyncio
async def test_dograh_provider_doctor():
    cfg = Settings(dograh_api_key="test_dograh_key")
    provider = DograhProvider(config=cfg)

    with patch.object(provider.get_client(), "list_telephony_configurations", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = [{"id": 1}]
        diag = await provider.doctor()
        assert diag["credentials"][0] is True
        assert diag["connectivity"][0] is True


@pytest.mark.asyncio
async def test_dograh_provider_doctor_missing_key():
    cfg = Settings(dograh_api_key="")
    provider = DograhProvider(config=cfg)
    diag = await provider.doctor()
    assert diag["credentials"][0] is False


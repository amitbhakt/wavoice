"""Dograh Cloud API Client.

Automates:
- Registering WhatsApp telephony configurations
- Syncing phone numbers into Dograh
- Creating pre-configured sample WhatsApp agent workflows
- Publishing workflows
- Binding workflows to phone numbers for instant WhatsApp voice calling
"""

import asyncio
from typing import Any, Dict, List, Optional
import aiohttp
from loguru import logger


DEFAULT_DOGRAH_API_URL = "https://api.dograh.com"


class DograhAPIError(Exception):
    """Raised when an API request to Dograh fails."""

    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[Any] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class DograhCloudClient:
    """Async client for Dograh Cloud REST API."""

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_DOGRAH_API_URL,
        session: Optional[aiohttp.ClientSession] = None,
    ):
        self.api_key = api_key.strip()
        self.base_url = base_url.rstrip("/")
        self._external_session = session
        self._owned_session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._external_session and not self._external_session.closed:
            return self._external_session
        if self._owned_session is None or self._owned_session.closed:
            self._owned_session = aiohttp.ClientSession()
        return self._owned_session

    async def close(self) -> None:
        if self._owned_session and not self._owned_session.closed:
            await self._owned_session.close()

    @property
    def _headers(self) -> Dict[str, str]:
        return {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def get_whatsapp_webhook_url(self) -> str:
        """Return the public Dograh endpoint where Meta must deliver WhatsApp call webhooks."""
        return f"{self.base_url}/api/v1/telephony/whatsapp/webhook"

    async def _request(
        self,
        method: str,
        path: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        session = await self._get_session()
        url = f"{self.base_url}{path}"

        async with session.request(
            method=method,
            url=url,
            headers=self._headers,
            json=json_data,
            params=params,
        ) as resp:
            try:
                data = await resp.json()
            except Exception:
                text = await resp.text()
                data = {"raw_text": text}

            if resp.status not in (200, 201, 204):
                detail = data.get("detail", data.get("message", str(data)))
                raise DograhAPIError(
                    f"Dograh API {method} {path} failed ({resp.status}): {detail}",
                    status_code=resp.status,
                    response_data=data,
                )
            return data

    async def create_telephony_configuration(
        self,
        name: str,
        access_token: str,
        waba_id: str,
        app_secret: str,
    ) -> Dict[str, Any]:
        """Create a new WhatsApp telephony configuration on Dograh Cloud.

        Dograh automatically checks credentials against Meta, subscribes the app
        to the WABA, and generates a unique webhook_verify_token.
        """
        payload = {
            "name": name,
            "is_default_outbound": False,
            "config": {
                "provider": "whatsapp",
                "access_token": access_token,
                "waba_id": waba_id,
                "app_secret": app_secret,
            },
        }
        return await self._request("POST", "/api/v1/organizations/telephony-configs", json_data=payload)

    async def list_telephony_configurations(self) -> List[Dict[str, Any]]:
        """List all telephony configurations for the organization."""
        data = await self._request("GET", "/api/v1/organizations/telephony-configs")
        return data.get("configurations", [])

    async def get_telephony_configuration(self, config_id: int) -> Dict[str, Any]:
        """Fetch full details (including credentials & verify token) for a configuration."""
        return await self._request("GET", f"/api/v1/organizations/telephony-configs/{config_id}")

    async def sync_phone_numbers(self, config_id: int) -> Dict[str, Any]:
        """Sync phone numbers from Meta WABA into Dograh for this configuration."""
        return await self._request(
            "POST",
            f"/api/v1/organizations/telephony-configs/{config_id}/phone-numbers/sync",
        )

    async def list_phone_numbers(self, config_id: int) -> List[Dict[str, Any]]:
        """List phone numbers associated with a telephony configuration."""
        data = await self._request(
            "GET",
            f"/api/v1/organizations/telephony-configs/{config_id}/phone-numbers",
        )
        return data if isinstance(data, list) else data.get("phone_numbers", [])

    async def create_sample_whatsapp_workflow(
        self,
        name: str = "WhatsApp Voice Assistant",
    ) -> Dict[str, Any]:
        """Create a starter conversational AI workflow formatted for WhatsApp voice calls."""
        workflow_def = {
            "nodes": [
                {
                    "id": "start-node",
                    "type": "startCall",
                    "position": {"x": 400, "y": 80},
                    "data": {
                        "name": "Start Call",
                        "is_start": True,
                        "greeting_type": "text",
                        "greeting": (
                            "Hello! You have successfully connected WhatsApp AI calling via Dograh. "
                            "I am your live test assistant. How are you doing today?"
                        ),
                        "prompt": (
                            "Greet the caller warmly with the introductory message confirming their "
                            "WhatsApp AI calling integration is live. Then ask how they are doing today."
                        ),
                    },
                },
                {
                    "id": "agent-node",
                    "type": "agentNode",
                    "position": {"x": 400, "y": 280},
                    "data": {
                        "name": "WhatsApp Assistant",
                        "prompt": (
                            "You are a friendly and enthusiastic voice assistant confirming a successful "
                            "WhatsApp voice setup on Dograh. Keep your answers brief, natural, and conversational "
                            "(1-2 sentences). If the user responds, confirms they can hear you, or asks if it works, "
                            "tell them their setup is completely working with crystal clear audio. Let them know "
                            "they can customize prompts, tools, and voices anytime in Dograh Studio at app.dograh.com. "
                            "If the user says they are good, says goodbye, or thanks you, transition to End Call."
                        ),
                    },
                },
                {
                    "id": "end-node",
                    "type": "endCall",
                    "position": {"x": 400, "y": 500},
                    "data": {
                        "name": "End Call",
                        "prompt": "Awesome! Your setup is verified and complete. Have a wonderful day, and goodbye!",
                    },
                },
            ],
            "edges": [
                {
                    "id": "edge-start-to-agent",
                    "type": "custom",
                    "animated": True,
                    "source": "start-node",
                    "target": "agent-node",
                    "data": {
                        "label": "Begin Conversation",
                        "condition": "Always take this route",
                    },
                },
                {
                    "id": "edge-agent-to-end",
                    "type": "custom",
                    "animated": True,
                    "source": "agent-node",
                    "target": "end-node",
                    "data": {
                        "label": "User Ends Call",
                        "condition": (
                            "The caller says goodbye, expresses thanks, or indicates "
                            "they are done and want to hang up."
                        ),
                    },
                },
            ],
            "viewport": {"x": 0, "y": 0, "zoom": 1},
        }

        payload = {
            "name": name,
            "workflow_definition": workflow_def,
        }
        return await self._request("POST", "/api/v1/workflow/create/definition", json_data=payload)

    async def publish_workflow(self, workflow_id: int) -> Dict[str, Any]:
        """Publish the workflow draft so runtime can execute it for live calls.

        Newly created workflows in Dograh are already published as V1 by default.
        """
        try:
            return await self._request("POST", f"/api/v1/workflow/{workflow_id}/publish", json_data={})
        except DograhAPIError as e:
            err_text = f"{str(e)} {str(e.response_data)}".lower()
            if e.status_code == 400 and ("no draft" in err_text or "already published" in err_text or "already" in err_text):
                logger.debug(f"[Dograh] Workflow {workflow_id} is already published as initial version.")
                return {"status": "published", "workflow_id": workflow_id}
            raise

    async def bind_workflow_to_phone_number(
        self,
        config_id: int,
        phone_number_row_id: int,
        workflow_id: int,
    ) -> Dict[str, Any]:
        """Assign an inbound workflow to a specific phone number in Dograh."""
        payload = {"inbound_workflow_id": workflow_id}
        return await self._request(
            "PUT",
            f"/api/v1/organizations/telephony-configs/{config_id}/phone-numbers/{phone_number_row_id}",
            json_data=payload,
        )

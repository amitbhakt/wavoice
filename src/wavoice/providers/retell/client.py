"""Retell AI API Client for WAVoice."""

from typing import Any, Dict, List, Optional
import aiohttp
from loguru import logger

RETELL_BASE_URL = "https://api.retellai.com"


class RetellClientError(Exception):
    """Raised when an operation on the Retell API fails."""
    pass


class RetellClient:
    """Async client for interacting with Retell AI REST APIs."""

    def __init__(self, api_key: str, base_url: str = RETELL_BASE_URL):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed or self._session._loop.is_closed():
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    @property
    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def validate_connection(self) -> Dict[str, Any]:
        """Test API key validity by querying list of agents or phone numbers."""
        session = await self._get_session()
        url = f"{self.base_url}/list-agents"
        try:
            async with session.get(url, headers=self._headers) as resp:
                if resp.status == 200:
                    agents = await resp.json()
                    logger.success(f"[Retell] Connected successfully. Found {len(agents)} agent(s).")
                    return {"valid": True, "agent_count": len(agents)}
                elif resp.status in (401, 403):
                    raise RetellClientError("Retell API Key is invalid or unauthorized.")
                else:
                    text = await resp.text()
                    raise RetellClientError(f"Retell connection validation failed (HTTP {resp.status}): {text}")
        except aiohttp.ClientError as e:
            raise RetellClientError(f"Network error connecting to Retell AI: {e}") from e

    async def get_agent(self, agent_id: str) -> Dict[str, Any]:
        """Fetch details for a specific Retell agent."""
        session = await self._get_session()
        url = f"{self.base_url}/get-agent/{agent_id}"
        try:
            async with session.get(url, headers=self._headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data
                elif resp.status == 404:
                    raise RetellClientError(f"Retell Agent ID '{agent_id}' was not found.")
                else:
                    text = await resp.text()
                    raise RetellClientError(f"Failed to fetch Retell agent '{agent_id}' (HTTP {resp.status}): {text}")
        except aiohttp.ClientError as e:
            raise RetellClientError(f"Network error fetching Retell agent: {e}") from e

    async def list_phone_numbers(self) -> List[Dict[str, Any]]:
        """List all phone numbers configured in Retell."""
        session = await self._get_session()
        url = f"{self.base_url}/list-phone-numbers"
        try:
            async with session.get(url, headers=self._headers) as resp:
                if resp.status == 200:
                    return await resp.json()
                text = await resp.text()
                raise RetellClientError(f"Failed to list Retell phone numbers: {text}")
        except aiohttp.ClientError as e:
            raise RetellClientError(f"Network error listing Retell phone numbers: {e}") from e

    async def import_phone_number(
        self,
        phone_number: str,
        inbound_agent_id: str,
        termination_uri: Optional[str] = "sip.cloudonix.io",
        nickname: Optional[str] = "WhatsApp Voice (WAVoice)",
    ) -> Dict[str, Any]:
        """Import an external phone number (or SIP route) into Retell bound to an inbound agent."""
        session = await self._get_session()
        url = f"{self.base_url}/import-phone-number"
        payload: Dict[str, Any] = {
            "phone_number": phone_number,
            "inbound_agents": [
                {
                    "agent_id": inbound_agent_id,
                    "weight": 1.0,
                    "agent_version": "latest_published",
                }
            ],
        }
        if termination_uri:
            payload["termination_uri"] = termination_uri
        if nickname:
            payload["nickname"] = nickname

        logger.info(f"[Retell] Importing number {phone_number} bound to agent {inbound_agent_id}...")
        try:
            async with session.post(url, headers=self._headers, json=payload) as resp:
                data = await resp.json()
                if resp.status in (200, 201):
                    logger.success(f"[Retell] Successfully registered number {phone_number} with Retell agent {inbound_agent_id}!")
                    return data
                # If already imported, retrieve it or handle gracefully
                err_msg = data.get("message", str(data))
                if "already exists" in err_msg.lower() or "already imported" in err_msg.lower():
                    logger.info(f"[Retell] Phone number {phone_number} is already imported in Retell.")
                    return {"phone_number": phone_number, "status": "already_exists"}
                raise RetellClientError(f"Retell import-phone-number failed (HTTP {resp.status}): {err_msg}")
        except aiohttp.ClientError as e:
            raise RetellClientError(f"Network error importing phone number to Retell: {e}") from e

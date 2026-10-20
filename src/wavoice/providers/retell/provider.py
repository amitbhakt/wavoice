"""Retell AI Provider for WAVoice.

Enables WhatsApp voice calls to be answered directly by Retell AI voice agents
via Meta SIP trunking and Cloudonix gateway routing.
"""

from typing import Any, Dict, Optional
from loguru import logger

from wavoice.core.config import Settings, settings
from wavoice.core.meta import MetaGraphClient
from wavoice.providers.base import BaseProvider
from wavoice.providers.retell.client import RetellClient, RetellClientError


class RetellProvider(BaseProvider):
    """Execution provider for Retell AI voice agents via SIP."""

    name: str = "retell"

    def __init__(self, config: Optional[Settings] = None):
        self.config = config or settings
        self._client: Optional[RetellClient] = None

    def get_client(self) -> RetellClient:
        if self._client is None:
            if not self.config.retell_api_key:
                raise RetellClientError("RETELL_API_KEY is not configured in settings or environment.")
            self._client = RetellClient(api_key=self.config.retell_api_key)
        return self._client

    async def validate_credentials(self) -> Dict[str, Any]:
        """Validate Retell API key and agent availability."""
        client = self.get_client()
        conn = await client.validate_connection()
        if self.config.retell_agent_id:
            agent = await client.get_agent(self.config.retell_agent_id)
            conn["agent_name"] = agent.get("agent_name", "Unknown")
            conn["agent_id"] = self.config.retell_agent_id
        return conn

    async def setup(self, meta_info: Dict[str, Any], ingress_url: str = "") -> Dict[str, Any]:
        """Perform one-time platform setup:
        1. Validate Retell API key and Agent ID.
        2. Bind phone number to Retell agent via /import-phone-number.
        3. Enable SIP calling on Meta Phone Number ID (routing to SIP gateway).
        """
        # 1. Validate Retell credentials and agent
        client = self.get_client()
        if not self.config.retell_agent_id:
            raise RetellClientError("RETELL_AGENT_ID must be specified for setup.")

        logger.info(f"[Retell] Verifying agent '{self.config.retell_agent_id}'...")
        agent_data = await client.get_agent(self.config.retell_agent_id)
        agent_name = agent_data.get("agent_name", self.config.retell_agent_id)
        logger.success(f"[Retell] Verified Agent: {agent_name} ({self.config.retell_agent_id})")

        # 2. Extract phone number details from Meta info
        display_num = meta_info.get("display_phone_number") or meta_info.get("phone_id")
        phone_id = meta_info.get("phone_id") or self.config.whatsapp_phone_number_id
        sip_host = self.config.cloudonix_domain or "sip.cloudonix.io"

        # 3. Register number in Retell bound to agent
        clean_num = "".join(ch for ch in str(display_num) if ch.isdigit() or ch == "+")
        if not clean_num.startswith("+"):
            clean_num = f"+{clean_num}"

        logger.info(f"[Retell] Importing phone number {clean_num} to Retell agent {agent_name}...")
        import_res = await client.import_phone_number(
            phone_number=clean_num,
            inbound_agent_id=self.config.retell_agent_id,
            termination_uri=sip_host,
            nickname=f"WhatsApp Voice ({clean_num})",
        )

        # 4. Enable SIP Calling on Meta WhatsApp Number
        if self.config.whatsapp_token and phone_id:
            meta = MetaGraphClient(self.config.whatsapp_token)
            try:
                logger.info(f"[Meta] Enabling SIP Calling on phone {phone_id} -> {sip_host}:5061...")
                sip_ok = await meta.enable_sip_calling(
                    phone_number_id=phone_id,
                    sip_host=sip_host,
                    sip_port=5061,
                )
                if not sip_ok:
                    # Fallback to standard voice calling if SIP tier threshold is pending
                    logger.warning("[Meta] SIP calling configuration returned warning; ensuring standard voice is enabled as fallback.")
                    await meta.enable_voice_calling(phone_id)
            finally:
                await meta.close()

        return {
            "provider": self.name,
            "agent_id": self.config.retell_agent_id,
            "agent_name": agent_name,
            "phone_number": clean_num,
            "sip_gateway": f"{sip_host}:5061",
            "retell_import": import_res,
        }

    async def doctor(self) -> Dict[str, Any]:
        """Check Retell configuration health."""
        results: Dict[str, Any] = {}

        if not self.config.retell_api_key:
            results["credentials"] = (False, "RETELL_API_KEY is missing from environment")
            return results

        client = self.get_client()
        try:
            conn = await client.validate_connection()
            results["credentials"] = (True, f"Retell API key valid ({conn.get('agent_count', 0)} agents found)")
        except Exception as e:
            results["credentials"] = (False, f"Retell API key error: {e}")
            await client.close()
            return results

        if self.config.retell_agent_id:
            try:
                agent = await client.get_agent(self.config.retell_agent_id)
                results["agent"] = (True, f"Agent verified: {agent.get('agent_name', self.config.retell_agent_id)}")
            except Exception as e:
                results["agent"] = (False, f"Agent error: {e}")
        else:
            results["agent"] = (False, "RETELL_AGENT_ID is not configured")

        await client.close()
        return results

"""LiveKit Cloud Provider implementation for WAVoice."""

from typing import Any, Dict, Optional
from loguru import logger

from wavoice.core.config import Settings, settings
from wavoice.providers.base import BaseProvider
from wavoice.providers.livekit.client import LiveKitCloudClient, LiveKitClientError
from wavoice.providers.livekit.detector import detect_local_livekit_config


class LiveKitProvider(BaseProvider):
    """Execution provider for LiveKit Cloud WhatsApp AI voice calls."""

    name: str = "livekit"

    def __init__(self, config: Optional[Settings] = None):
        self.config = config or settings
        self._client: Optional[LiveKitCloudClient] = None

    def get_client(self) -> LiveKitCloudClient:
        if self._client is None:
            if not self.config.livekit_url or not self.config.livekit_api_key or not self.config.livekit_api_secret:
                raise LiveKitClientError("LiveKit credentials not configured in settings.")
            self._client = LiveKitCloudClient(
                url=self.config.livekit_url,
                api_key=self.config.livekit_api_key,
                api_secret=self.config.livekit_api_secret,
            )
        return self._client

    async def validate_credentials(self) -> Dict[str, Any]:
        """Validate LiveKit Cloud URL, API Key, and Secret."""
        client = self.get_client()
        return await client.validate_connection()

    async def setup(self, meta_info: Dict[str, Any], ingress_url: str) -> Dict[str, Any]:
        """Perform platform setup and verification for LiveKit Cloud."""
        # 1. Validate connection
        conn_info = await self.validate_credentials()
        display_num = meta_info.get("display_phone_number", meta_info.get("phone_id", "Unknown"))

        return {
            "provider": self.name,
            "display_num": display_num,
            "livekit_url": self.config.livekit_url,
            "ingress_url": ingress_url,
            "active_rooms": conn_info.get("active_rooms", 0),
        }

    async def doctor(self) -> Dict[str, Any]:
        """Check LiveKit Cloud configuration health."""
        results: Dict[str, Any] = {}

        has_creds = bool(self.config.livekit_url and self.config.livekit_api_key and self.config.livekit_api_secret)
        if not has_creds:
            detected = detect_local_livekit_config()
            if detected:
                results["credentials"] = (True, f"Found local LiveKit project: {detected.get('project_name', 'default')}")
            else:
                results["credentials"] = (False, "LIVEKIT_URL, LIVEKIT_API_KEY, or LIVEKIT_API_SECRET missing")
            return results

        results["credentials"] = (True, f"Configured URL: {self.config.livekit_url}")
        client = self.get_client()
        try:
            conn = await client.validate_connection()
            results["connectivity"] = (True, f"Connected to LiveKit Cloud (Key: {conn['api_key']})")
        except Exception as e:
            results["connectivity"] = (False, f"LiveKit Cloud connection failed: {e}")
        finally:
            await client.close()

        return results

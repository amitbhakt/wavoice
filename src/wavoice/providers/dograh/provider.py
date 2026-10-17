"""Dograh Cloud Provider implementation for WAVoice."""

from typing import Any, Dict, Optional
from loguru import logger

from wavoice.core.config import Settings, settings
from wavoice.providers.base import BaseProvider
from wavoice.providers.dograh.client import DograhCloudClient, DograhAPIError


class DograhProvider(BaseProvider):
    """Execution provider for Dograh Cloud visual voice agents."""

    name: str = "dograh"

    def __init__(self, config: Optional[Settings] = None):
        self.config = config or settings
        self._client: Optional[DograhCloudClient] = None

    def get_client(self) -> DograhCloudClient:
        if self._client is None:
            if not self.config.dograh_api_key:
                raise DograhAPIError("Dograh API key not configured in settings.")
            self._client = DograhCloudClient(
                api_key=self.config.dograh_api_key,
                base_url=self.config.dograh_base_url or "https://api.dograh.com",
            )
        return self._client

    async def validate_credentials(self) -> Dict[str, Any]:
        """Validate Dograh Cloud API Key by fetching telephony configurations."""
        client = self.get_client()
        configs = await client.list_telephony_configurations()
        return {
            "status": "connected",
            "configurations_count": len(configs),
        }

    async def setup(self, meta_info: Dict[str, Any], ingress_url: str = "") -> Dict[str, Any]:
        """Perform platform setup on Dograh Cloud."""
        client = self.get_client()
        configs = await client.list_telephony_configurations()
        return {
            "provider": self.name,
            "webhook_url": client.get_whatsapp_webhook_url(),
            "existing_configs": len(configs),
        }

    async def doctor(self) -> Dict[str, Any]:
        """Check Dograh Cloud configuration health."""
        results: Dict[str, Any] = {}

        if not self.config.dograh_api_key:
            results["credentials"] = (False, "DOGRAH_API_KEY not configured in .env")
            return results

        results["credentials"] = (True, "DOGRAH_API_KEY configured")

        try:
            client = self.get_client()
            configs = await client.list_telephony_configurations()
            results["connectivity"] = (True, f"Connected to {client.base_url} ({len(configs)} configs found)")
        except Exception as e:
            results["connectivity"] = (False, f"Connection failed: {e}")
        finally:
            if self._client:
                await self._client.close()

        return results

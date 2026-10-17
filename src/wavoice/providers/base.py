"""Abstract Base Provider for WAVoice Telephony & AI Platforms."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BaseProvider(ABC):
    """Abstract interface for all WhatsApp Voice AI integration providers."""

    name: str = "base"

    @abstractmethod
    async def validate_credentials(self) -> Dict[str, Any]:
        """Validate provider credentials and test connection to the platform."""
        pass

    @abstractmethod
    async def setup(self, meta_info: Dict[str, Any], ingress_url: str) -> Dict[str, Any]:
        """Perform one-time platform setup (register configs, sync numbers, bind workflows)."""
        pass

    @abstractmethod
    async def doctor(self) -> Dict[str, Any]:
        """Perform provider-specific health diagnostic checks."""
        pass

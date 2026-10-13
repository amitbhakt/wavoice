"""wa-voice: One-command WhatsApp Voice AI with Pipecat."""

from wavoice.core.config import Settings, settings
from wavoice.sdk import WhatsAppVoiceApp

__version__ = "0.1.0"
__all__ = ["WhatsAppVoiceApp", "Settings", "settings"]

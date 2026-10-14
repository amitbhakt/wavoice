"""Configuration settings for wa-voice using pydantic-settings."""

import secrets
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _get_default_port() -> int:
    """Return 8000 if free, or fallback to 8080/8765 if 8000 is occupied by another app."""
    import socket
    for candidate in (8000, 8080, 8765, 8081):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", candidate)) != 0:
                return candidate
    return 8000


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Meta WhatsApp Business Cloud API Credentials
    whatsapp_token: str = Field(
        default="",
        alias="WHATSAPP_TOKEN",
        description="Meta System User Access Token with whatsapp_business_messaging & whatsapp_business_management",
    )
    whatsapp_phone_number_id: str = Field(
        default="",
        alias="WHATSAPP_PHONE_NUMBER_ID",
        description="WhatsApp Business Phone Number ID",
    )
    whatsapp_waba_id: Optional[str] = Field(
        default=None,
        alias="WHATSAPP_WABA_ID",
        description="WhatsApp Business Account ID (WABA ID) for webhook auto-subscription",
    )
    whatsapp_app_secret: Optional[str] = Field(
        default=None,
        alias="WHATSAPP_APP_SECRET",
        description="Meta App Secret for X-Hub-Signature-256 HMAC validation",
    )
    whatsapp_verify_token: str = Field(
        default_factory=lambda: secrets.token_hex(16),
        alias="WHATSAPP_WEBHOOK_VERIFY_TOKEN",
        description="Verification token for Meta webhook hub.challenge handshake",
    )

    # Server & Tunneling
    host: str = Field(default="127.0.0.1", alias="HOST")
    port: int = Field(default_factory=_get_default_port, alias="PORT")
    public_url: Optional[str] = Field(
        default=None,
        alias="PUBLIC_URL",
        description="Custom public HTTPS URL (if not using automated Cloudflare Quick Tunnel)",
    )

    # AI Models
    gemini_api_key: Optional[str] = Field(
        default=None,
        alias="GEMINI_API_KEY",
        description="Google Gemini API Key for default Gemini 2.0 Flash Live voice agent",
    )
    openai_api_key: Optional[str] = Field(
        default=None,
        alias="OPENAI_API_KEY",
        description="OpenAI API Key (optional alternative)",
    )
    dograh_api_key: Optional[str] = Field(
        default=None,
        alias="DOGRAH_API_KEY",
        description="Dograh Cloud API Key (from app.dograh.com/api-keys > 'API Keys' section, NOT Service Key)",
    )
    dograh_base_url: str = Field(
        default="https://api.dograh.com",
        alias="DOGRAH_BASE_URL",
        description="Dograh API base URL (defaults to Dograh Cloud)",
    )

    # WebRTC ICE Servers (STUN / TURN)
    stun_server: str = Field(
        default="stun:stun.l.google.com:19302",
        alias="STUN_SERVER",
    )
    turn_server: Optional[str] = Field(
        default=None,
        alias="TURN_SERVER",
        description="Optional TURN server URI (e.g., turn:turn.example.com:3478?transport=udp)",
    )
    turn_username: Optional[str] = Field(
        default=None,
        alias="TURN_USERNAME",
    )
    turn_password: Optional[str] = Field(
        default=None,
        alias="TURN_PASSWORD",
    )

    # Anonymous Usage Telemetry
    telemetry_enabled: bool = Field(
        default=True,
        alias="WAVOICE_TELEMETRY",
        description="Enable anonymous usage telemetry (can be disabled via prompt or DO_NOT_TRACK=1)",
    )


settings = Settings()

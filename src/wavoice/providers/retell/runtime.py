"""Retell Local Runtime orchestrator.

Coordinates:
- Cloudflare Quick Tunnel (or custom public URL)
- Meta Webhook 3-Tier Synchronization
- FastAPI Webhook Relay to Retell AI WebRTC Gateway
"""

import asyncio
from typing import Optional
from loguru import logger
import uvicorn

from wavoice.core.config import Settings, settings
from wavoice.core.meta import MetaGraphClient
from wavoice.core.tunnel import CloudflareTunnel
from wavoice.providers.retell.webhook import create_retell_app


class RetellRuntime:
    """Orchestrator for running Retell WhatsApp Voice AI locally."""

    def __init__(self, config: Optional[Settings] = None):
        self.config = config or settings
        self._tunnel: Optional[CloudflareTunnel] = None

    async def setup_ingress_and_meta(
        self,
        local_port: int,
        tunnel: bool = True,
        custom_url: Optional[str] = None,
    ) -> str:
        """Establish tunnel/public URL and synchronize Meta webhooks."""
        if custom_url:
            public_url = custom_url.rstrip("/")
        elif self.config.public_url:
            public_url = self.config.public_url.rstrip("/")
        elif tunnel:
            self._tunnel = CloudflareTunnel(local_port=local_port, host=self.config.host)
            public_url = await self._tunnel.start()
        else:
            public_url = f"http://{self.config.host}:{local_port}"

        webhook_url = f"{public_url}/webhook"

        if self.config.whatsapp_token and self.config.whatsapp_phone_number_id:
            meta = MetaGraphClient(self.config.whatsapp_token)
            try:
                # 1. Ensure Standard Voice Calling is enabled on Meta number
                await meta.enable_voice_calling(self.config.whatsapp_phone_number_id)

                # 2. Override Phone-level webhook
                await meta.override_phone_number_webhook(
                    phone_number_id=self.config.whatsapp_phone_number_id,
                    callback_url=webhook_url,
                    verify_token=self.config.whatsapp_verify_token,
                )

                # 3. Subscribe WABA webhook
                waba_id = self.config.whatsapp_waba_id or await meta.discover_waba_id()
                if waba_id:
                    await meta.subscribe_waba_webhook(
                        waba_id=waba_id,
                        callback_url=webhook_url,
                        verify_token=self.config.whatsapp_verify_token,
                    )
            finally:
                await meta.close()

        return webhook_url

    def run(
        self,
        port: Optional[int] = None,
        tunnel: bool = True,
        custom_url: Optional[str] = None,
    ) -> None:
        """Synchronous entry point to start the Retell WhatsApp local runtime."""
        local_port = port or self.config.port
        fastapi_app = create_retell_app(config=self.config)

        @fastapi_app.on_event("startup")
        async def on_startup():
            async def _bg():
                await asyncio.sleep(0.5)
                try:
                    wh_url = await self.setup_ingress_and_meta(
                        local_port=local_port,
                        tunnel=tunnel,
                        custom_url=custom_url,
                    )
                    logger.success(f"🚀 Retell AI WhatsApp Bridge is LIVE! Webhook: {wh_url}")
                except Exception as e:
                    logger.error(f"Retell setup error: {e}")

            asyncio.create_task(_bg())

        @fastapi_app.on_event("shutdown")
        async def on_shutdown():
            if self._tunnel:
                await self._tunnel.stop()

        uvicorn.run(
            fastapi_app,
            host=self.config.host,
            port=local_port,
            log_level="info",
        )

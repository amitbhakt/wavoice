"""LiveKit Cloud Runtime orchestrator.

Coordinates:
- Cloudflare Quick Tunnel (or custom public URL)
- Meta Webhook 3-Tier Synchronization
- FastAPI Webhook Relay
- Background LiveKit Agent Worker
"""

import asyncio
import threading
from typing import Optional
from loguru import logger
import uvicorn

from wavoice.core.config import Settings, settings
from wavoice.core.meta import MetaGraphClient
from wavoice.core.tunnel import CloudflareTunnel
from wavoice.providers.livekit.agent import run_livekit_agent_worker
from wavoice.providers.livekit.client import LiveKitCloudClient
from wavoice.providers.livekit.webhook import create_livekit_app


class LiveKitRuntime:
    """Orchestrator for running LiveKit WhatsApp Voice AI."""

    def __init__(self, config: Optional[Settings] = None):
        self.config = config or settings
        self._tunnel: Optional[CloudflareTunnel] = None
        self._client: Optional[LiveKitCloudClient] = None
        self._agent_thread: Optional[threading.Thread] = None

    def get_client(self) -> LiveKitCloudClient:
        if self._client is None:
            if not self.config.livekit_url or not self.config.livekit_api_key or not self.config.livekit_api_secret:
                raise RuntimeError("LiveKit credentials (LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET) must be set.")
            self._client = LiveKitCloudClient(
                url=self.config.livekit_url,
                api_key=self.config.livekit_api_key,
                api_secret=self.config.livekit_api_secret,
            )
        return self._client

    async def setup_ingress_and_meta(
        self,
        local_port: int,
        tunnel: bool = True,
        custom_url: Optional[str] = None,
    ) -> str:
        """Establish tunnel/public URL and synchronize Meta webhooks."""
        if custom_url:
            public_url = custom_url.rstrip("/")
            logger.info(f"[LiveKit Ingress] Using custom public URL: {public_url}")
        elif self.config.public_url:
            public_url = self.config.public_url.rstrip("/")
            logger.info(f"[LiveKit Ingress] Using configured public URL: {public_url}")
        elif tunnel:
            self._tunnel = CloudflareTunnel(local_port=local_port, host=self.config.host)
            public_url = await self._tunnel.start()
        else:
            public_url = f"http://{self.config.host}:{local_port}"
            logger.warning(f"[LiveKit Ingress] Running without tunnel: {public_url}")

        webhook_url = f"{public_url}/webhook"

        # Auto-subscribe with Meta if credentials are present
        if self.config.whatsapp_token and self.config.whatsapp_phone_number_id:
            meta = MetaGraphClient(self.config.whatsapp_token)
            try:
                phone_info = await meta.verify_phone_number(self.config.whatsapp_phone_number_id)
                display_num = phone_info.get("display_phone_number", self.config.whatsapp_phone_number_id)
                logger.success(f"[Meta] Verified WhatsApp Number: {display_num}")

                # Ensure voice calling is enabled
                try:
                    calling = await meta.get_calling_settings(self.config.whatsapp_phone_number_id)
                    if calling.get("status") != "ENABLED":
                        await meta.enable_voice_calling(self.config.whatsapp_phone_number_id)
                except Exception as e:
                    logger.debug(f"[Meta] Calling settings check notice: {e}")

                # Override Phone-level webhook
                try:
                    await meta.override_phone_number_webhook(
                        phone_number_id=self.config.whatsapp_phone_number_id,
                        callback_url=webhook_url,
                        verify_token=self.config.whatsapp_verify_token,
                    )
                    logger.success(f"[Meta] Webhook routed to: {webhook_url}")
                except Exception as e:
                    logger.debug(f"[Meta] Phone webhook override notice: {e}")

                # Subscribe WABA webhook
                waba_id = self.config.whatsapp_waba_id or await meta.discover_waba_id()
                if waba_id:
                    try:
                        await meta.subscribe_waba_webhook(
                            waba_id=waba_id,
                            callback_url=webhook_url,
                            verify_token=self.config.whatsapp_verify_token,
                        )
                    except Exception as e:
                        logger.debug(f"[Meta] WABA webhook notice: {e}")

            finally:
                await meta.close()

        return webhook_url

    def start_agent_worker(self, agent_name: Optional[str] = None) -> None:
        """Launch the bundled LiveKit agent worker in a background daemon thread."""
        chosen_agent = agent_name or self.config.livekit_agent_name or "wavoice-agent"
        logger.info(f"[LiveKit] Launching background voice agent worker ({chosen_agent})...")
        self._agent_thread = threading.Thread(
            target=run_livekit_agent_worker,
            kwargs={
                "livekit_url": self.config.livekit_url,
                "api_key": self.config.livekit_api_key,
                "api_secret": self.config.livekit_api_secret,
                "agent_name": chosen_agent,
            },
            daemon=True,
            name="livekit-agent-worker",
        )
        self._agent_thread.start()

    def run(
        self,
        port: Optional[int] = None,
        tunnel: bool = True,
        custom_url: Optional[str] = None,
        run_agent: bool = True,
        agent_name: Optional[str] = None,
    ) -> None:
        """Synchronous entry point to run the LiveKit WhatsApp runtime."""
        local_port = port or self.config.port
        if agent_name:
            self.config.livekit_agent_name = agent_name

        client = self.get_client()

        # Start agent worker in background
        if run_agent:
            self.start_agent_worker(agent_name=self.config.livekit_agent_name)

        fastapi_app = create_livekit_app(config=self.config, client=client)

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
                    logger.success(f"🚀 LiveKit WhatsApp Bridge is LIVE! Webhook: {wh_url}")
                except Exception as e:
                    logger.error(f"LiveKit setup error: {e}")

            asyncio.create_task(_bg())

        @fastapi_app.on_event("shutdown")
        async def on_shutdown():
            if self._tunnel:
                await self._tunnel.stop()
            if self._client:
                await self._client.close()

        uvicorn.run(
            fastapi_app,
            host=self.config.host,
            port=local_port,
            log_level="info",
        )

"""Universal Pipecat SDK for WhatsApp Voice AI.

Allows any developer to attach arbitrary Pipecat voice pipelines to incoming
WhatsApp voice calls with a single decorator (@app.on_call).
"""

import asyncio
from typing import Callable, Optional

import uvicorn
from loguru import logger
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.transports.whatsapp.api import WhatsAppConnectCall

from wavoice.agents.gemini_live import run_gemini_live_agent
from wavoice.core.config import Settings, settings
from wavoice.core.meta import MetaGraphClient
from wavoice.core.tunnel import CloudflareTunnel
from wavoice.server.app import CallHandlerType, create_app


class WhatsAppVoiceApp:
    """Main application runtime for WhatsApp Voice AI with Pipecat."""

    def __init__(self, config: Optional[Settings] = None):
        self.config = config or settings
        self._custom_handler: Optional[CallHandlerType] = None
        self._tunnel: Optional[CloudflareTunnel] = None

    def on_call(self, handler_fn: Callable) -> Callable:
        """Register a custom Pipecat handler for incoming calls.

        The handler can have either signature:
        - async def handler(transport: SmallWebRTCTransport, call: WhatsAppConnectCall): ...
        - async def handler(connection: SmallWebRTCConnection, call: WhatsAppConnectCall): ...
        """

        async def _adapted_handler(connection: SmallWebRTCConnection, call: WhatsAppConnectCall) -> None:
            from pipecat.transports.base_transport import TransportParams

            transport = SmallWebRTCTransport(
                webrtc_connection=connection,
                params=TransportParams(
                    audio_in_enabled=True,
                    audio_out_enabled=True,
                    video_in_enabled=False,
                ),
            )
            try:
                # Try passing (transport, call)
                await handler_fn(transport, call)
            except TypeError:
                # Fallback to passing (connection, call)
                await handler_fn(connection, call)

        self._custom_handler = _adapted_handler
        return handler_fn

    async def _setup_tunnel_and_webhook(self, local_port: int) -> str:
        """Initialize tunnel and auto-register with Meta if WABA_ID is configured."""
        if self.config.public_url:
            public_url = self.config.public_url.rstrip("/")
            logger.info(f"Using explicitly configured public URL: {public_url}")
        else:
            self._tunnel = CloudflareTunnel(local_port=local_port, host=self.config.host)
            public_url = await self._tunnel.start()

        webhook_url = f"{public_url}/webhook"

        # Check credentials and auto-subscribe if WABA_ID is provided
        # Check credentials and auto-subscribe if WABA_ID is provided
        if self.config.whatsapp_token and self.config.whatsapp_phone_number_id:
            meta = MetaGraphClient(self.config.whatsapp_token)
            try:
                # 1. First validate token health
                token_info = await meta.inspect_token()
                if not token_info or token_info.get("error"):
                    logger.error(f"[Meta] Token validation failed: {token_info.get('error', 'Invalid token')}")
                    logger.warning("👉 Run 'wavoice init' to update your Meta Access Token.")
                    return webhook_url

                phone_info = await meta.verify_phone_number(self.config.whatsapp_phone_number_id)
                display_num = phone_info.get("display_phone_number", self.config.whatsapp_phone_number_id)
                logger.success(f"[Meta] Verified WhatsApp Number: {display_num} ({phone_info.get('verified_name', 'Verified')})")

                # Auto-check and enable voice calling on the phone number
                try:
                    calling_settings = await meta.get_calling_settings(self.config.whatsapp_phone_number_id)
                    calling_status = calling_settings.get("status")
                    if calling_status != "ENABLED":
                        logger.info(f"[Meta] Voice calling status is '{calling_status}'. Auto-enabling via Graph API...")
                        await meta.enable_voice_calling(self.config.whatsapp_phone_number_id)
                    else:
                        logger.success("[Meta] Voice calling is ENABLED on this number!")
                except Exception as e:
                    logger.debug(f"[Meta] Could not auto-check voice calling settings: {e}")

                # Ensure phone-number level webhook override (Priority #1 in Meta) points to our tunnel
                try:
                    await meta.override_phone_number_webhook(
                        phone_number_id=self.config.whatsapp_phone_number_id,
                        callback_url=webhook_url,
                        verify_token=self.config.whatsapp_verify_token,
                    )
                except Exception as e:
                    logger.debug(f"[Meta] Phone-number webhook override error: {e}")

                waba_id = self.config.whatsapp_waba_id or await meta.discover_waba_id()
                waba_subscribed = False
                if waba_id:
                    # Retry WABA webhook subscription up to 3 times in case Meta's edge servers encounter brief DNS propagation delay
                    for attempt in range(1, 4):
                        try:
                            await meta.subscribe_waba_webhook(
                                waba_id=waba_id,
                                callback_url=webhook_url,
                                verify_token=self.config.whatsapp_verify_token,
                            )
                            waba_subscribed = True
                            break
                        except Exception as e:
                            if attempt < 3 and "502" in str(e) or "resolve host" in str(e).lower():
                                logger.info(f"[Meta] Waiting for public DNS propagation (attempt {attempt}/3)...")
                                await asyncio.sleep(2.0)
                            else:
                                logger.warning(f"[Meta] Auto-subscription to WABA ({waba_id}) failed: {e}. You may need to paste webhook URL manually in Meta Console.")
                                break

                # Also update App-level webhook subscriptions for 'calls' if app_secret is available
                if self.config.whatsapp_app_secret:
                    try:
                        app_id = token_info.get("app_id")
                        if app_id:
                            await meta.subscribe_app_webhook(
                                app_id=str(app_id),
                                app_secret=self.config.whatsapp_app_secret,
                                callback_url=webhook_url,
                                verify_token=self.config.whatsapp_verify_token,
                            )
                    except Exception as e:
                        logger.debug(f"[Meta] App-level webhook subscription error: {e}")
            except Exception as e:
                err_str = str(e).lower()
                if "expire" in err_str:
                    logger.error("❌ Meta Access Token has EXPIRED! Please refresh your token.")
                elif "malformed" in err_str:
                    logger.error("❌ Meta Access Token is MALFORMED or invalid.")
                else:
                    logger.error(f"❌ Meta API error: {e}")
                logger.warning("👉 Run 'wavoice init' to update your token.")
                return None
            finally:
                await meta.close()

        return webhook_url

    def run(self, tunnel: bool = True, port: Optional[int] = None) -> None:
        """Start the WhatsApp Voice AI server and tunnel synchronously."""
        port = port or self.config.port

        # Default to Gemini Live agent if no custom pipeline was attached
        handler = self._custom_handler or run_gemini_live_agent
        async def _startup_wrapper():
            if tunnel:
                async def _background_setup():
                    # Give Uvicorn 0.5s to bind to the port and start accepting traffic
                    await asyncio.sleep(0.5)
                    try:
                        webhook_url = await self._setup_tunnel_and_webhook(local_port=port)
                        if webhook_url:
                            logger.success(f"🚀 WhatsApp Voice Server is live! Callback URL: {webhook_url}")
                        else:
                            logger.warning("⚠️ WhatsApp Voice Server started, but Meta webhook configuration failed. Check logs above.")
                    except Exception as e:
                        logger.error(f"Failed to start tunnel: {e}")

                asyncio.create_task(_background_setup())

        async def _shutdown_wrapper():
            if self._tunnel:
                await self._tunnel.stop()

        fastapi_app = create_app(
            call_handler=handler,
            startup_fn=_startup_wrapper,
            shutdown_fn=_shutdown_wrapper,
            config=self.config,
        )

        uvicorn.run(
            fastapi_app,
            host=self.config.host,
            port=port,
            log_level="info",
        )

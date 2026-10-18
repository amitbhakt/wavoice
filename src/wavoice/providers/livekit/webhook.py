"""FastAPI Webhook Relay for LiveKit WhatsApp Connector.

Receives Meta WhatsApp Cloud API webhooks (calls) and bridges them
directly into LiveKit Cloud using `accept_whatsapp_call`.
"""

import asyncio
from typing import Any, Dict, Optional
from fastapi import APIRouter, FastAPI, HTTPException, Query, Request
from loguru import logger
from starlette.responses import PlainTextResponse

from wavoice.core.config import Settings, settings
from wavoice.core.lifecycle import lifecycle_manager
from wavoice.providers.livekit.client import LiveKitCloudClient
from wavoice.server.security import verify_whatsapp_signature


router = APIRouter()
_livekit_client: Optional[LiveKitCloudClient] = None
_background_tasks: set[asyncio.Task] = set()


def set_active_livekit_client(client: LiveKitCloudClient) -> None:
    global _livekit_client
    _livekit_client = client


def get_active_livekit_client(cfg: Settings) -> LiveKitCloudClient:
    global _livekit_client
    if _livekit_client is None:
        if not cfg.livekit_url or not cfg.livekit_api_key or not cfg.livekit_api_secret:
            raise RuntimeError("LiveKit credentials (LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET) not set.")
        _livekit_client = LiveKitCloudClient(
            url=cfg.livekit_url,
            api_key=cfg.livekit_api_key,
            api_secret=cfg.livekit_api_secret,
        )
    return _livekit_client


@router.get("/webhook")
async def handle_livekit_webhook_verification(
    request: Request,
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
):
    """Handle Meta's webhook verification handshake."""
    cfg: Settings = getattr(request.app.state, "config", settings)
    if hub_mode != "subscribe":
        logger.warning(f"[LiveKit Webhook] Invalid hub.mode: {hub_mode}")
        raise HTTPException(status_code=400, detail="Invalid hub.mode")

    if hub_verify_token != cfg.whatsapp_verify_token:
        logger.warning("[LiveKit Webhook] Verification token mismatch")
        raise HTTPException(status_code=403, detail="Invalid verification token")

    logger.success("[LiveKit Webhook] Verification challenge succeeded!")
    return PlainTextResponse(hub_challenge, status_code=200)


@router.post("/webhook")
async def handle_livekit_webhook_event(request: Request):
    """Handle incoming WhatsApp Cloud API events (call connect, terminate, etc.)."""
    cfg: Settings = getattr(request.app.state, "config", settings)
    raw_body = await request.body()
    signature_header = request.headers.get("x-hub-signature-256")

    # Verify HMAC signature if app_secret is configured
    verify_whatsapp_signature(
        app_secret=cfg.whatsapp_app_secret,
        raw_body=raw_body,
        signature_header=signature_header,
    )

    try:
        payload = await request.json()
    except Exception as e:
        logger.warning(f"[LiveKit Webhook] Non-JSON payload: {e}")
        return {"status": "ignored"}

    entry_list = payload.get("entry", [])
    if not entry_list:
        return {"status": "ignored"}

    for entry in entry_list:
        for change in entry.get("changes", []):
            val = change.get("value", {})
            calls_raw = val.get("calls")
            if isinstance(calls_raw, list):
                call_list = calls_raw
            elif val.get("call"):
                call_list = [val.get("call")]
            else:
                call_list = []

            for call in call_list:
                if not isinstance(call, dict):
                    continue

                event_type = call.get("event")
                call_id = call.get("id")
                from_number = (
                    call.get("from")
                    or call.get("from_")
                    or (val.get("contacts") and val["contacts"][0].get("wa_id"))
                    or "whatsapp_caller"
                )
                phone_number_id = cfg.whatsapp_phone_number_id or val.get("metadata", {}).get("phone_number_id")

                if event_type == "connect":
                    session = call.get("session") or {}
                    sdp_offer = call.get("sdp") or session.get("sdp")
                    if not sdp_offer:
                        logger.warning(f"[LiveKit Webhook] Call connect event missing SDP: {call_id}")
                        continue

                    # Deduplication: atomic claim lock
                    is_first_claim = await lifecycle_manager.claim_call(call_id)
                    if not is_first_claim:
                        logger.debug(f"[LiveKit Webhook] Ignoring duplicate call claim for {call_id}")
                        continue

                    room_name = f"wa-call-{call_id}"
                    logger.info(f"[LiveKit Webhook] Inbound call {call_id} from {from_number} -> dispatching to LiveKit")

                    async def _forward_call(
                        c_id=call_id,
                        c_sdp=sdp_offer,
                        c_room=room_name,
                        c_from=from_number,
                        c_pid=phone_number_id,
                    ):
                        try:
                            client = get_active_livekit_client(cfg)
                            await client.accept_whatsapp_call(
                                whatsapp_phone_number_id=c_pid,
                                whatsapp_api_key=cfg.whatsapp_token,
                                whatsapp_call_id=c_id,
                                sdp_offer=c_sdp,
                                room_name=c_room,
                                caller_phone=c_from,
                                agent_name=cfg.livekit_agent_name or "wavoice-agent",
                            )
                        except Exception as err:
                            logger.error(f"[LiveKit Webhook] Failed to bridge call {c_id}: {err}")
                            await lifecycle_manager.release_claim(c_id)

                    task = asyncio.create_task(_forward_call())
                    _background_tasks.add(task)
                    task.add_done_callback(_background_tasks.discard)

                elif event_type == "terminate":
                    logger.info(f"[LiveKit Webhook] Call {call_id} terminated by user")
                    await lifecycle_manager.release_claim(call_id)

                    async def _disconnect_call(c_id=call_id):
                        try:
                            client = get_active_livekit_client(cfg)
                            await client.disconnect_whatsapp_call(
                                whatsapp_call_id=c_id,
                                whatsapp_api_key=cfg.whatsapp_token,
                                user_initiated=True,
                            )
                        except Exception as err:
                            logger.debug(f"[LiveKit Webhook] Disconnect notice for {c_id}: {err}")

                    task = asyncio.create_task(_disconnect_call())
                    _background_tasks.add(task)
                    task.add_done_callback(_background_tasks.discard)

    return {"status": "ok"}


def create_livekit_app(
    config: Optional[Settings] = None,
    client: Optional[LiveKitCloudClient] = None,
) -> FastAPI:
    """Create a FastAPI application configured for LiveKit WhatsApp Webhooks."""
    cfg = config or settings
    app = FastAPI(title="WAVoice LiveKit Webhook Relay")
    app.state.config = cfg
    if client:
        set_active_livekit_client(client)
    app.include_router(router)
    return app

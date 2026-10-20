"""FastAPI Webhook Relay for Retell AI WhatsApp Voice Calls.

Enables zero-friction local testing:
1. Receives Meta WhatsApp incoming call webhook (with SDP offer).
2. Calls Retell AI POST /v3/create-web-call to initialize agent session.
3. Posts the SDP offer to Retell's WebRTC Gateway (/webrtc-proxy/{call_id}/v1/webrtc/sessions).
4. Returns the SDP answer to Meta WhatsApp to establish live bidirectional voice.
"""

import asyncio
import aiohttp
from typing import Any, Dict, Optional
from fastapi import APIRouter, FastAPI, HTTPException, Query, Request
from loguru import logger
from starlette.responses import PlainTextResponse

from wavoice.core.config import Settings, settings
from wavoice.core.lifecycle import lifecycle_manager
from wavoice.core.meta import MetaGraphClient
from wavoice.providers.retell.client import RetellClient
from wavoice.server.security import verify_whatsapp_signature

MAX_WEBHOOK_BODY_SIZE = 1_048_576

router = APIRouter()
_http_session: Optional[aiohttp.ClientSession] = None
_background_tasks: set[asyncio.Task] = set()


def _get_session() -> aiohttp.ClientSession:
    global _http_session
    if _http_session is None or _http_session.closed or _http_session._loop.is_closed():
        _http_session = aiohttp.ClientSession()
    return _http_session


@router.get("/webhook")
async def handle_retell_webhook_verification(
    request: Request,
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
):
    """Handle Meta's webhook verification handshake."""
    cfg: Settings = getattr(request.app.state, "config", settings)
    if hub_mode != "subscribe":
        raise HTTPException(status_code=400, detail="Invalid hub.mode")

    import hmac
    if not hmac.compare_digest(hub_verify_token, cfg.whatsapp_verify_token):
        raise HTTPException(status_code=403, detail="Invalid verification token")

    logger.success("[Retell Webhook] Meta challenge verification succeeded!")
    return PlainTextResponse(hub_challenge, status_code=200)


@router.post("/webhook")
async def handle_retell_webhook_event(request: Request):
    """Handle incoming WhatsApp Cloud API events and bridge directly to Retell AI."""
    cfg: Settings = getattr(request.app.state, "config", settings)

    raw_body = await request.body()
    if len(raw_body) > MAX_WEBHOOK_BODY_SIZE:
        raise HTTPException(status_code=413, detail="Payload too large")

    signature_header = request.headers.get("x-hub-signature-256")
    verify_whatsapp_signature(
        app_secret=cfg.whatsapp_app_secret,
        raw_body=raw_body,
        signature_header=signature_header,
    )

    try:
        payload = await request.json()
    except Exception as e:
        logger.warning(f"[Retell Webhook] Non-JSON payload: {e}")
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
                    session_info = call.get("session") or {}
                    sdp_offer = call.get("sdp") or session_info.get("sdp")
                    if not sdp_offer:
                        logger.warning(f"[Retell Webhook] Call connect missing SDP offer: {call_id}")
                        continue

                    # Prevent duplicate deliveries
                    is_first_claim = await lifecycle_manager.claim_call(call_id)
                    if not is_first_claim:
                        logger.debug(f"[Retell Webhook] Duplicate connect ignored for {call_id}")
                        continue

                    logger.info(f"[Retell Webhook] Inbound WhatsApp call {call_id} from {from_number} -> Bridging to Retell AI...")

                    async def _bridge_to_retell(
                        c_id=call_id,
                        c_sdp=sdp_offer,
                        c_from=from_number,
                        c_pid=phone_number_id,
                    ):
                        try:
                            # 1. Create Web Call on Retell to initialize session
                            retell_session = _get_session()
                            retell_url = "https://api.retellai.com/v3/create-web-call"
                            retell_headers = {
                                "Authorization": f"Bearer {cfg.retell_api_key}",
                                "Content-Type": "application/json",
                            }
                            web_call_payload = {
                                "agent_id": cfg.retell_agent_id,
                                "metadata": {
                                    "caller_phone": c_from,
                                    "whatsapp_call_id": c_id,
                                },
                            }
                            async with retell_session.post(retell_url, headers=retell_headers, json=web_call_payload) as resp:
                                if resp.status not in (200, 201):
                                    err_text = await resp.text()
                                    raise RuntimeError(f"Retell create-web-call failed ({resp.status}): {err_text}")
                                web_call_data = await resp.json()

                            r_call_id = web_call_data["call_id"]
                            r_access_token = web_call_data["access_token"]
                            logger.success(f"[Retell] Session created: {r_call_id}")

                            # 2. Negotiate WebRTC SDP with Retell's WebRTC Gateway
                            proxy_url = f"https://api.retellai.com/webrtc-proxy/{r_call_id}/v1/webrtc/sessions"
                            proxy_headers = {
                                "Authorization": f"Bearer {r_access_token}",
                                "Content-Type": "application/json",
                            }
                            proxy_payload = {
                                "identity": "client",
                                "sdp": c_sdp,
                            }
                            async with retell_session.post(proxy_url, headers=proxy_headers, json=proxy_payload) as resp:
                                if resp.status not in (200, 201):
                                    err_text = await resp.text()
                                    raise RuntimeError(f"Retell WebRTC Proxy negotiation failed ({resp.status}): {err_text}")
                                proxy_data = await resp.json()

                            sdp_answer = proxy_data.get("sdp")
                            if not sdp_answer:
                                raise RuntimeError(f"Retell proxy did not return SDP answer: {proxy_data}")

                            # 3. Answer Meta WhatsApp Call with Retell's SDP Answer
                            meta_client = MetaGraphClient(access_token=cfg.whatsapp_token, session=retell_session)
                            answer_url = f"https://graph.facebook.com/v21.0/{c_pid}/calls"
                            answer_payload = {
                                "messaging_product": "whatsapp",
                                "call_id": c_id,
                                "action": "accept",
                                "session": {
                                    "sdp_type": "answer",
                                    "sdp": sdp_answer,
                                },
                            }
                            async with retell_session.post(
                                answer_url,
                                headers={"Authorization": f"Bearer {cfg.whatsapp_token}", "Content-Type": "application/json"},
                                json=answer_payload,
                            ) as resp:
                                meta_resp = await resp.json()
                                if resp.status in (200, 201) and meta_resp.get("success"):
                                    logger.success(f"[Retell <-> WhatsApp] Call {c_id} CONNECTED! Agent speaking.")
                                else:
                                    logger.error(f"[Meta] Failed to accept call with answer: {meta_resp}")

                        except Exception as e:
                            logger.error(f"[Retell Webhook] Failed to bridge call {c_id}: {e}")
                            await lifecycle_manager.release_claim(c_id)

                    task = asyncio.create_task(_bridge_to_retell())
                    _background_tasks.add(task)
                    task.add_done_callback(_background_tasks.discard)

                elif event_type == "terminate":
                    logger.info(f"[Retell Webhook] Call {call_id} ended by user.")
                    await lifecycle_manager.finish_call(call_id)

    return {"status": "success"}


def create_retell_app(config: Settings) -> FastAPI:
    """Create FastAPI application for Retell WhatsApp bridge."""
    app = FastAPI(title="WAVoice Retell Bridge")
    app.state.config = config
    app.include_router(router)
    return app

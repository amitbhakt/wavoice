"""FastAPI Webhook Server for Meta WhatsApp Business Calling API.

Handles:
- GET /webhook: Meta hub.challenge verification handshake
- POST /webhook: HMAC signature check, atomic call claiming, WebRTC negotiation,
  and dispatching calls to Pipecat pipelines.
"""

import asyncio
import json
from typing import Any, Callable, Coroutine, Dict, Optional

import aiohttp
from fastapi import APIRouter, FastAPI, HTTPException, Query, Request
from loguru import logger
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
from pipecat.transports.whatsapp.api import (
    WhatsAppConnectCall,
    WhatsAppWebhookRequest,
)
from pipecat.transports.whatsapp.client import WhatsAppClient
from starlette.responses import PlainTextResponse

from wavoice.core.config import Settings, settings
from wavoice.core.ice import build_ice_servers
from wavoice.core.lifecycle import lifecycle_manager
from wavoice.core.meta import MetaGraphClient
from wavoice.server.security import verify_whatsapp_signature

router = APIRouter()

# Type for call handler callback:
# async def handler(connection: SmallWebRTCConnection, call: WhatsAppConnectCall) -> None:
CallHandlerType = Callable[[SmallWebRTCConnection, WhatsAppConnectCall], Coroutine[Any, Any, None]]

_http_session: Optional[aiohttp.ClientSession] = None
_whatsapp_client: Optional[WhatsAppClient] = None
_background_tasks: set[asyncio.Task] = set()


def _get_http_session() -> aiohttp.ClientSession:
    global _http_session
    if _http_session is None or _http_session.closed:
        _http_session = aiohttp.ClientSession()
    return _http_session


def get_whatsapp_client(cfg: Settings) -> WhatsAppClient:
    """Get or instantiate the Pipecat WhatsAppClient."""
    global _whatsapp_client
    if _whatsapp_client is None:
        session = _get_http_session()
        ice_servers = build_ice_servers(
            stun_url=cfg.stun_server,
            turn_url=cfg.turn_server,
            turn_username=cfg.turn_username,
            turn_password=cfg.turn_password,
        )
        # Signature is already verified in FastAPI router upfront, so pass
        # whatsapp_secret=None to avoid redundant internal verification errors in WhatsAppClient.
        _whatsapp_client = WhatsAppClient(
            whatsapp_token=cfg.whatsapp_token,
            phone_number_id=cfg.whatsapp_phone_number_id,
            session=session,
            ice_servers=ice_servers,
            whatsapp_secret=None,
        )
    return _whatsapp_client


@router.get("/webhook")
async def handle_webhook_verification(
    request: Request,
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
):
    """Handle Meta's webhook verification handshake."""
    cfg: Settings = getattr(request.app.state, "config", settings)
    if hub_mode != "subscribe":
        logger.warning(f"[Webhook] Invalid hub.mode: {hub_mode}")
        raise HTTPException(status_code=400, detail="Invalid hub.mode")

    if hub_verify_token != cfg.whatsapp_verify_token:
        logger.warning(
            f"[Webhook] Verification failed: token mismatch (received: {hub_verify_token}, expected: {cfg.whatsapp_verify_token})"
        )
        raise HTTPException(status_code=403, detail="Invalid verification token")

    logger.success("[Webhook] Verification challenge succeeded!")
    return PlainTextResponse(hub_challenge, status_code=200)


@router.post("/webhook")
async def handle_webhook_event(request: Request):
    """Handle incoming WhatsApp Cloud API events (connect, terminate, etc.)."""
    cfg: Settings = getattr(request.app.state, "config", settings)
    raw_body = await request.body()
    signature_header = request.headers.get("x-hub-signature-256")

    # 1. Verify HMAC Signature
    verify_whatsapp_signature(
        app_secret=cfg.whatsapp_app_secret,
        raw_body=raw_body,
        signature_header=signature_header,
    )

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception as e:
        logger.error(f"[Webhook] Failed to parse JSON: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON")

    entry_list = payload.get("entry") or []
    for entry in entry_list:
        changes = entry.get("changes") or []
        for change in changes:
            field = change.get("field")
            if field != "calls":
                continue

            value = change.get("value") or {}
            metadata = value.get("metadata") or {}
            phone_number_id = str(metadata.get("phone_number_id") or "")
            calls = value.get("calls") or []

            for call_data in calls:
                event = call_data.get("event")
                call_id = call_data.get("id") or ""

                if event == "connect":
                    await _handle_connect_event(
                        request=request,
                        call_data=call_data,
                        phone_number_id=phone_number_id,
                        payload=payload,
                        entry=entry,
                        change=change,
                        raw_body=raw_body,
                        cfg=cfg,
                    )
                elif event == "terminate":
                    if call_id:
                        await _handle_terminate_event(
                            call_id=call_id,
                            phone_number_id=phone_number_id,
                            payload=payload,
                            raw_body=raw_body,
                            cfg=cfg,
                        )

    return {"status": "success"}


async def _handle_connect_event(
    request: Request,
    call_data: Dict[str, Any],
    phone_number_id: str,
    payload: Dict[str, Any],
    entry: Dict[str, Any],
    change: Dict[str, Any],
    raw_body: bytes,
    cfg: Settings,
) -> None:
    call_id = call_data.get("id") or ""
    from_number = call_data.get("from") or ""
    session_data = call_data.get("session") or {}
    sdp_type = session_data.get("sdp_type")

    if sdp_type != "offer":
        logger.warning(f"[Webhook] Unexpected sdp_type: {sdp_type} for call {call_id}")
        return

    # Atomic claim to prevent double delivery answering
    if not await lifecycle_manager.claim_call(call_id):
        logger.warning(f"[Webhook] Duplicate connect ignored for call {call_id}")
        return

    meta_client = MetaGraphClient(cfg.whatsapp_token)
    client = get_whatsapp_client(cfg)
    handler: Optional[CallHandlerType] = getattr(request.app.state, "call_handler", None)

    async def on_connected(connection: SmallWebRTCConnection, call: WhatsAppConnectCall) -> None:
        caller_from = getattr(call, "from_", getattr(call, "From", "caller"))
        logger.success(f"[Call] Answered incoming call {call.id} from {caller_from}!")
        start_time = time.time()
        from wavoice.core.telemetry import track_event
        track_event("call_answered", {"call_id_prefix": call.id[:10] if call.id else ""})

        async def _run_agent() -> None:
            pipeline_err: Optional[str] = None
            try:
                if handler:
                    await handler(connection, call)
                else:
                    logger.error("[Call] No call_handler registered on app state!")
            except Exception as e:
                err_str = str(e).lower()
                if "190" in err_str or "expire" in err_str or "session has expired" in err_str:
                    pipeline_err = "token_expired"
                    logger.critical(f"❌ [Call {call.id}] Meta Access Token EXPIRED mid-call! Please generate a new token and update .env")
                else:
                    pipeline_err = "pipeline_error"
                    logger.error(f"[Call] Error in pipeline for call {call.id}: {e}", exc_info=True)
            finally:
                duration_secs = round(time.time() - start_time, 2)
                # If the bot hung up first, notify Meta to terminate the call on the caller's phone
                terminated_by_caller = await lifecycle_manager.is_terminated_by_meta(call.id)
                if not terminated_by_caller:
                    await meta_client.terminate_call(phone_number_id, call.id)
                await lifecycle_manager.finish_call(call.id)
                track_event("call_completed", {
                    "duration_seconds": duration_secs,
                    "terminated_by": "caller" if terminated_by_caller else "bot",
                    "error": pipeline_err,
                })

        task = asyncio.create_task(_run_agent())
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

    try:
        # Narrow payload to this call for Pipecat client
        single_call_value = {**(change.get("value") or {}), "calls": [call_data]}
        single_payload = {**payload, "entry": [{**entry, "changes": [{**change, "value": single_call_value}]}]}

        await client.handle_webhook_request(
            request=WhatsAppWebhookRequest.model_validate(single_payload),
            connection_callback=on_connected,
            raw_body=raw_body,
        )
    except Exception as e:
        err_type = "token_expired" if ("190" in err_str or "expire" in err_str or "session has expired" in err_str) else "webrtc_error"
        if err_type == "token_expired":
            logger.critical(f"❌ [Call {call_id}] Failed to answer call: Meta Access Token has EXPIRED! Please refresh your token.")
        else:
            logger.error(f"[Call] Failed to establish WebRTC for call {call_id}: {e}")
        from wavoice.core.telemetry import track_event
        track_event("call_failed", {"error": err_type})
        await meta_client.reject_call(phone_number_id, call_id)
        await lifecycle_manager.release_claim(call_id)


async def _handle_terminate_event(
    call_id: str,
    phone_number_id: str,
    payload: Dict[str, Any],
    raw_body: bytes,
    cfg: Settings,
) -> None:
    logger.info(f"[Call] Remote terminate received for call {call_id}")
    await lifecycle_manager.mark_terminated_by_meta(call_id)
    client = get_whatsapp_client(cfg)
    try:
        await client.handle_webhook_request(
            WhatsAppWebhookRequest.model_validate(payload),
            raw_body=raw_body,
        )
    except Exception as e:
        logger.warning(f"[Call] Terminate handling error for {call_id}: {e}")


from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    startup_fn = getattr(app.state, "startup_fn", None)
    if startup_fn:
        await startup_fn()
    yield
    # Graceful shutdown: cancel any remaining background tasks immediately
    global _background_tasks, _http_session
    for t in list(_background_tasks):
        if not t.done():
            t.cancel()
    if _http_session and not _http_session.closed:
        await _http_session.close()

    shutdown_fn = getattr(app.state, "shutdown_fn", None)
    if shutdown_fn:
        await shutdown_fn()


def create_app(
    call_handler: Optional[CallHandlerType] = None,
    startup_fn: Optional[Callable[[], Coroutine[Any, Any, None]]] = None,
    shutdown_fn: Optional[Callable[[], Coroutine[Any, Any, None]]] = None,
    config: Optional[Settings] = None,
) -> FastAPI:
    """Create and configure the FastAPI server."""
    app = FastAPI(title="wavoice", version="0.2.0", lifespan=lifespan)
    app.state.call_handler = call_handler
    app.state.startup_fn = startup_fn
    app.state.shutdown_fn = shutdown_fn
    app.state.config = config or settings
    app.include_router(router)
    return app

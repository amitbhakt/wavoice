"""LiveKit Cloud Connector & Room Management Client."""

from typing import Any, Dict, List, Optional
from loguru import logger

from livekit.api import LiveKitAPI
from livekit.api.connector_service import (
    AcceptWhatsAppCallRequest,
    AcceptWhatsAppCallResponse,
    DisconnectWhatsAppCallRequest,
    DisconnectWhatsAppCallResponse,
)
from livekit.protocol.agent_dispatch import RoomAgentDispatch


class LiveKitClientError(Exception):
    """Raised when a request to LiveKit Cloud fails."""
    pass


class LiveKitCloudClient:
    """High-level client for LiveKit Cloud WhatsApp Connector and Room Management."""

    def __init__(
        self,
        url: str,
        api_key: str,
        api_secret: str,
    ):
        self.url = url.strip()
        self.api_key = api_key.strip()
        self.api_secret = api_secret.strip()
        self._api: Optional[LiveKitAPI] = None

    def get_api(self) -> LiveKitAPI:
        if self._api is None:
            self._api = LiveKitAPI(
                url=self.url,
                api_key=self.api_key,
                api_secret=self.api_secret,
            )
        return self._api

    async def close(self) -> None:
        if self._api is not None:
            await self._api.aclose()
            self._api = None

    async def validate_connection(self) -> Dict[str, Any]:
        """Test authentication and project connectivity with LiveKit Cloud."""
        api = self.get_api()
        try:
            from livekit.protocol.room import ListRoomsRequest
            rooms = await api.room.list_rooms(ListRoomsRequest())
            return {
                "success": True,
                "url": self.url,
                "api_key": f"{self.api_key[:6]}...{self.api_key[-4:]}" if len(self.api_key) > 10 else "***",
                "active_rooms": len(rooms.rooms) if hasattr(rooms, "rooms") else 0,
            }
        except Exception as e:
            logger.error(f"[LiveKit] Connection validation failed: {e}")
            raise LiveKitClientError(f"LiveKit Cloud connection failed: {e}") from e

    async def accept_whatsapp_call(
        self,
        whatsapp_phone_number_id: str,
        whatsapp_api_key: str,
        whatsapp_call_id: str,
        sdp_offer: str,
        room_name: str,
        caller_phone: str,
        participant_name: str = "WhatsApp Caller",
        whatsapp_cloud_api_version: str = "23.0",
        agent_name: Optional[str] = "wavoice-agent",
    ) -> AcceptWhatsAppCallResponse:
        """Bridge an incoming WhatsApp voice call into a LiveKit room."""
        api = self.get_api()

        request = AcceptWhatsAppCallRequest()
        request.whatsapp_phone_number_id = whatsapp_phone_number_id
        request.whatsapp_api_key = whatsapp_api_key
        request.whatsapp_cloud_api_version = whatsapp_cloud_api_version
        request.whatsapp_call_id = whatsapp_call_id
        request.room_name = room_name
        request.participant_identity = caller_phone
        request.participant_name = participant_name
        request.sdp.type = "offer"
        request.sdp.sdp = sdp_offer

        if agent_name:
            request.agents.append(RoomAgentDispatch(agent_name=agent_name))

        logger.info(
            f"[LiveKit] Accepting WhatsApp call ID {whatsapp_call_id} from {caller_phone} into room '{room_name}' (agent={agent_name})"
        )
        try:
            response = await api.connector.accept_whatsapp_call(request)
            logger.success(f"[LiveKit] Call accepted successfully into room '{room_name}'")
            return response
        except Exception as e:
            logger.error(f"[LiveKit] accept_whatsapp_call failed: {e}")
            raise LiveKitClientError(f"Failed to accept WhatsApp call on LiveKit: {e}") from e

    async def disconnect_whatsapp_call(
        self,
        whatsapp_call_id: str,
        whatsapp_api_key: str,
        user_initiated: bool = False,
    ) -> DisconnectWhatsAppCallResponse:
        """Disconnect an active WhatsApp voice call."""
        api = self.get_api()

        request = DisconnectWhatsAppCallRequest()
        request.whatsapp_call_id = whatsapp_call_id
        request.whatsapp_api_key = whatsapp_api_key
        # DisconnectReason enum: 0 = BUSINESS_INITIATED, 1 = USER_INITIATED
        request.disconnect_reason = 1 if user_initiated else 0

        logger.info(f"[LiveKit] Disconnecting WhatsApp call ID {whatsapp_call_id}")
        try:
            response = await api.connector.disconnect_whatsapp_call(request)
            return response
        except Exception as e:
            logger.debug(f"[LiveKit] disconnect_whatsapp_call notice: {e}")
            raise LiveKitClientError(f"Failed to disconnect WhatsApp call: {e}") from e

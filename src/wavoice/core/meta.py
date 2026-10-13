"""Meta WhatsApp Business Cloud API client.

Handles:
- Token verification and permissions inspection
- Phone number status inspection
- Programmatic webhook subscription on the WABA
- Programmatic enablement of WhatsApp Voice Calling (POST /settings)
- Remote call rejection and termination
"""

from typing import Any, Dict, Optional
import aiohttp
from loguru import logger

GRAPH_API_VERSION = "v21.0"
GRAPH_BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


class TokenExpiredError(Exception):
    """Raised when a Meta access token is expired or invalidated."""
    pass


class TokenInvalidError(Exception):
    """Raised when a Meta access token is malformed or invalid."""
    pass


class MetaGraphClient:
    """Async client for Meta Graph API operations."""

    def __init__(self, access_token: str, session: Optional[aiohttp.ClientSession] = None):
        self.access_token = access_token
        self._external_session = session
        self._owned_session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._external_session and not self._external_session.closed:
            return self._external_session
        if self._owned_session is None or self._owned_session.closed:
            self._owned_session = aiohttp.ClientSession()
        return self._owned_session

    async def close(self) -> None:
        if self._owned_session and not self._owned_session.closed:
            await self._owned_session.close()

    @property
    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    async def verify_phone_number(self, phone_number_id: str) -> Dict[str, Any]:
        """Fetch details of a WhatsApp Business phone number."""
        session = await self._get_session()
        url = f"{GRAPH_BASE_URL}/{phone_number_id}"
        params = {"fields": "display_phone_number,verified_name,code_verification_status,quality_rating"}

        async with session.get(url, headers=self._headers, params=params) as resp:
            data = await resp.json()
            if resp.status != 200:
                error_msg = data.get("error", {}).get("message", "Unknown Meta API error")
                raise ValueError(f"Failed to verify Phone Number ID ({phone_number_id}): {error_msg}")
            return data

    async def get_calling_settings(self, phone_number_id: str) -> Dict[str, Any]:
        """Inspect calling configuration on the phone number."""
        session = await self._get_session()
        url = f"{GRAPH_BASE_URL}/{phone_number_id}/settings"
        params = {"fields": "calling"}

        async with session.get(url, headers=self._headers, params=params) as resp:
            data = await resp.json()
            if resp.status != 200:
                logger.debug(f"[Meta] Could not retrieve calling settings for {phone_number_id}: {data}")
                return {}
            return data.get("calling", {})

    async def enable_voice_calling(self, phone_number_id: str) -> bool:
        """Programmatically turn on WhatsApp Voice Calling via Meta Graph API."""
        session = await self._get_session()
        url = f"{GRAPH_BASE_URL}/{phone_number_id}/settings"
        payload = {
            "calling": {
                "status": "ENABLED",
                "call_icon_visibility": "DEFAULT",
            }
        }

        logger.info(f"Enabling voice calling for phone number {phone_number_id} via Graph API...")
        async with session.post(url, headers=self._headers, json=payload) as resp:
            data = await resp.json()
            if resp.status == 200 and data.get("success"):
                logger.success(f"[Meta] Voice calling successfully enabled for {phone_number_id}!")
                return True
            else:
                error_msg = data.get("error", {}).get("message", str(data))
                logger.warning(f"[Meta] Could not auto-enable voice calling: {error_msg}")
                return False

    async def subscribe_waba_webhook(
        self,
        waba_id: str,
        callback_url: str,
        verify_token: str,
    ) -> bool:
        """Register the webhook callback URL and verify token on the WhatsApp Business Account."""
        session = await self._get_session()
        url = f"{GRAPH_BASE_URL}/{waba_id}/subscribed_apps"
        payload = {
            "override_callback_uri": callback_url,
            "verify_token": verify_token,
        }

        logger.info(f"Subscribing Meta App to WABA ({waba_id}) with callback URL: {callback_url}")
        async with session.post(url, headers=self._headers, json=payload) as resp:
            data = await resp.json()
            if resp.status != 200 or not data.get("success"):
                error_msg = data.get("error", {}).get("message", str(data))
                raise ValueError(f"Failed to subscribe webhook to WABA ({waba_id}): {error_msg}")
            logger.success(f"Successfully subscribed webhook to WABA ({waba_id})!")
            return True

    async def subscribe_app_webhook(
        self,
        app_id: str,
        app_secret: str,
        callback_url: str,
        verify_token: str,
    ) -> bool:
        """Register the webhook callback URL and subscribe to 'calls' and 'messages' at the Meta App level."""
        session = await self._get_session()
        app_token = f"{app_id}|{app_secret}"
        url = f"{GRAPH_BASE_URL}/{app_id}/subscriptions"
        payload = {
            "object": "whatsapp_business_account",
            "callback_url": callback_url,
            "fields": "calls,messages",
            "verify_token": verify_token,
            "access_token": app_token,
        }

        logger.info(f"Subscribing Meta App ({app_id}) to webhook fields 'calls,messages' at {callback_url}...")
        async with session.post(url, data=payload) as resp:
            data = await resp.json()
            if resp.status == 200 and data.get("success"):
                logger.success(f"[Meta] Successfully configured App ({app_id}) webhook for 'calls,messages'!")
                return True
            else:
                error_msg = data.get("error", {}).get("message", str(data))
                logger.warning(f"[Meta] App webhook subscription: {error_msg}")
                return False

    async def override_phone_number_webhook(
        self,
        phone_number_id: str,
        callback_url: str,
        verify_token: str,
    ) -> bool:
        """Set a phone-number specific webhook override (highest priority in Meta routing hierarchy)."""
        session = await self._get_session()
        url = f"{GRAPH_BASE_URL}/{phone_number_id}"
        payload = {
            "webhook_configuration": {
                "override_callback_uri": callback_url,
                "verify_token": verify_token,
            }
        }

        logger.info(f"Setting Phone Number ({phone_number_id}) webhook override to {callback_url}...")
        async with session.post(url, headers=self._headers, json=payload) as resp:
            data = await resp.json()
            if resp.status == 200 and data.get("success"):
                logger.success(f"[Meta] Successfully updated Phone Number ({phone_number_id}) webhook override!")
                return True
            else:
                error_msg = data.get("error", {}).get("message", str(data))
                logger.debug(f"[Meta] Phone number webhook override response: {error_msg}")
                return False

    async def inspect_token(self) -> Dict[str, Any]:
        """Inspect the active token to check validity, app_id, scopes, and expiration."""
        session = await self._get_session()
        url = f"{GRAPH_BASE_URL}/debug_token"
        params = {
            "input_token": self.access_token,
            "access_token": self.access_token,
        }

        try:
            async with session.get(url, params=params) as resp:
                data = await resp.json()
                if resp.status == 200:
                    token_data = data.get("data", {})
                    if not token_data.get("is_valid", False):
                        error_info = token_data.get("error", {})
                        error_msg = error_info.get("message", "Token is invalid or expired")
                        error_code = error_info.get("code")
                        if error_code in (190, 102) or "expire" in error_msg.lower():
                            raise TokenExpiredError(f"Meta Access Token has expired: {error_msg}")
                        raise TokenInvalidError(f"Meta Access Token is invalid: {error_msg}")
                    return token_data

                err = data.get("error", {})
                err_msg = err.get("message", "Could not debug token")
                err_code = err.get("code")
                if err_code in (190, 102) or "expire" in err_msg.lower():
                    raise TokenExpiredError(f"Meta Access Token has expired: {err_msg}")
                elif "malformed" in err_msg.lower() or err_code == 2500:
                    raise TokenInvalidError(f"Meta Access Token is malformed: {err_msg}")
                return {"error": err_msg}
        except (TokenExpiredError, TokenInvalidError):
            raise
        except Exception as e:
            return {"error": str(e)}

    async def discover_waba_id(self) -> Optional[str]:
        """Auto-discover WABA ID from token scopes if not explicitly provided."""
        data = await self.inspect_token()
        for scope_obj in data.get("granular_scopes", []):
            if scope_obj.get("scope") in ("whatsapp_business_management", "whatsapp_business_messaging"):
                target_ids = scope_obj.get("target_ids", [])
                if target_ids:
                    return str(target_ids[0])
        return None

    async def list_phone_numbers(self, waba_id: str) -> list[Dict[str, Any]]:
        """Fetch all phone numbers attached to a WhatsApp Business Account."""
        session = await self._get_session()
        url = f"{GRAPH_BASE_URL}/{waba_id}/phone_numbers"
        try:
            async with session.get(url, headers=self._headers) as resp:
                data = await resp.json()
                return data.get("data", [])
        except Exception as e:
            logger.debug(f"[Meta] Could not list phone numbers for WABA {waba_id}: {e}")
            return []

    async def discover_phone_number_id(self, waba_id: Optional[str] = None) -> Optional[str]:
        """Auto-discover the primary phone number ID from the WABA account."""
        target_waba = waba_id or await self.discover_waba_id()
        if not target_waba:
            return None
        numbers = await self.list_phone_numbers(target_waba)
        if numbers:
            return str(numbers[0].get("id"))
        return None

    async def get_webhook_diagnostics(
        self,
        phone_number_id: str,
        waba_id: Optional[str] = None,
        app_secret: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Check all 3 tiers of Meta webhook subscription status."""
        session = await self._get_session()
        diag = {
            "phone_level": None,
            "waba_level": None,
            "app_level": None,
        }

        # Tier 1: Phone number override
        try:
            url = f"{GRAPH_BASE_URL}/{phone_number_id}"
            async with session.get(url, headers=self._headers, params={"fields": "webhook_configuration"}) as resp:
                data = await resp.json()
                configs = data.get("webhook_configuration", {})
                diag["phone_level"] = configs.get("phone_number")
        except Exception as e:
            diag["phone_level"] = f"Error: {e}"

        # Tier 2: WABA subscribed apps
        target_waba = waba_id or await self.discover_waba_id()
        if target_waba:
            try:
                url = f"{GRAPH_BASE_URL}/{target_waba}/subscribed_apps"
                async with session.get(url, headers=self._headers) as resp:
                    data = await resp.json()
                    subscribed_list = data.get("data", [])
                    diag["waba_level"] = [
                        app.get("override_callback_uri") or "Default App Callback"
                        for app in subscribed_list
                    ]
            except Exception as e:
                diag["waba_level"] = f"Error: {e}"

        # Tier 3: Meta App subscriptions
        token_info = await self.inspect_token()
        app_id = token_info.get("app_id")
        if app_id and app_secret:
            try:
                app_token = f"{app_id}|{app_secret}"
                url = f"{GRAPH_BASE_URL}/{app_id}/subscriptions"
                async with session.get(url, params={"access_token": app_token}) as resp:
                    data = await resp.json()
                    subs = data.get("data", [])
                    diag["app_level"] = [
                        f"{sub.get('object')}: {sub.get('callback_url')}"
                        for sub in subs
                        if sub.get("active")
                    ]
            except Exception as e:
                diag["app_level"] = f"Error: {e}"

        return diag

    async def reject_call(self, phone_number_id: str, call_id: str) -> Dict[str, Any]:
        """Explicitly decline a ringing WhatsApp call."""
        session = await self._get_session()
        url = f"{GRAPH_BASE_URL}/{phone_number_id}/calls"
        payload = {
            "messaging_product": "whatsapp",
            "call_id": call_id,
            "action": "reject",
        }

        try:
            async with session.post(url, headers=self._headers, json=payload) as resp:
                data = await resp.json()
                logger.info(f"[Meta] Rejected call {call_id}: status={resp.status}")
                return data
        except Exception as e:
            logger.error(f"[Meta] Failed to reject call {call_id}: {e}")
            return {"error": str(e)}

    async def terminate_call(self, phone_number_id: str, call_id: str) -> Dict[str, Any]:
        """Explicitly hang up an ongoing WhatsApp call."""
        session = await self._get_session()
        url = f"{GRAPH_BASE_URL}/{phone_number_id}/calls"
        payload = {
            "messaging_product": "whatsapp",
            "call_id": call_id,
            "action": "terminate",
        }

        try:
            async with session.post(url, headers=self._headers, json=payload) as resp:
                data = await resp.json()
                logger.info(f"[Meta] Terminated call {call_id}: status={resp.status}")
                return data
        except Exception as e:
            logger.error(f"[Meta] Failed to terminate call {call_id}: {e}")
            return {"error": str(e)}

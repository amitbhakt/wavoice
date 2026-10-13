"""Webhook security and HMAC-SHA256 signature verification."""

import hashlib
import hmac
from typing import Optional
from fastapi import HTTPException
from loguru import logger


def verify_whatsapp_signature(
    app_secret: Optional[str],
    raw_body: bytes,
    signature_header: Optional[str],
) -> None:
    """Validate Meta's X-Hub-Signature-256 HMAC for incoming webhook payloads.

    Raises:
        HTTPException: 403 if signature is missing or does not match.
    """
    if not app_secret:
        # If the user has not configured app_secret, we allow payloads (useful in early dev),
        # but log a warning.
        logger.debug("[Security] No WHATSAPP_APP_SECRET configured, skipping signature verification")
        return

    if not signature_header:
        logger.warning("[Security] Missing X-Hub-Signature-256 header")
        raise HTTPException(status_code=403, detail="Missing webhook signature")

    if not signature_header.startswith("sha256="):
        logger.warning("[Security] Invalid signature header format")
        raise HTTPException(status_code=403, detail="Invalid signature header format")

    expected_sig = signature_header[len("sha256=") :]
    computed_sig = hmac.new(
        app_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_sig, computed_sig):
        logger.warning("[Security] Webhook signature mismatch")
        raise HTTPException(status_code=403, detail="Invalid webhook signature")

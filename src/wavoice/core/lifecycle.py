"""Call lifecycle and deduplication management.

Meta delivers incoming 'connect' webhooks with at-least-once guarantees.
If processing takes more than ~1-2 seconds, Meta retries immediately.
This module ensures only ONE pipeline instance handles any given call_id.
"""

import asyncio
import time
from typing import Dict, Set
from loguru import logger


class CallClaimManager:
    """Manages atomic call claims and lifecycle states across concurrent webhooks."""

    def __init__(self, ttl_seconds: float = 600.0):
        self.ttl_seconds = ttl_seconds
        self._lock = asyncio.Lock()
        # Maps call_id -> timestamp claimed
        self._claims: Dict[str, float] = {}
        # Tracks calls whose pipeline is active
        self._active_calls: Set[str] = set()
        # Tracks calls that Meta already reported as terminated
        self._terminated_by_meta: Set[str] = set()

    async def claim_call(self, call_id: str) -> bool:
        """Atomically claim a call_id. Returns True if this delivery won the claim."""
        now = time.monotonic()
        async with self._lock:
            # Clean expired claims
            expired = [cid for cid, ts in self._claims.items() if now - ts > self.ttl_seconds]
            for cid in expired:
                del self._claims[cid]
                self._active_calls.discard(cid)
                self._terminated_by_meta.discard(cid)

            if call_id in self._claims:
                logger.warning(f"[Lifecycle] Call {call_id} is already claimed, dropping duplicate connect")
                return False

            self._claims[call_id] = now
            self._active_calls.add(call_id)
            return True

    async def release_claim(self, call_id: str) -> None:
        """Release a claim if processing failed before the call was picked up."""
        async with self._lock:
            self._claims.pop(call_id, None)
            self._active_calls.discard(call_id)
            self._terminated_by_meta.discard(call_id)
            logger.info(f"[Lifecycle] Released claim for call {call_id}")

    async def mark_terminated_by_meta(self, call_id: str) -> None:
        """Record that Meta reported this call terminated (user hung up)."""
        async with self._lock:
            self._terminated_by_meta.add(call_id)

    async def is_terminated_by_meta(self, call_id: str) -> bool:
        """Check if Meta already ended this call."""
        async with self._lock:
            return call_id in self._terminated_by_meta

    async def finish_call(self, call_id: str) -> None:
        """Mark a call as completely finished and teardown complete."""
        async with self._lock:
            self._active_calls.discard(call_id)
            self._terminated_by_meta.discard(call_id)


# Global singleton claim manager
lifecycle_manager = CallClaimManager()

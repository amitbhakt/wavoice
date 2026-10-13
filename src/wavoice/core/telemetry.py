"""Anonymous usage telemetry for WAVoice.

Allows developers to opt out at any time via:
- Prompt selection in `wavoice init`
- Environment variable: `WAVOICE_TELEMETRY=false` or `DO_NOT_TRACK=1`
- CLI flag: `--no-telemetry`
"""

import asyncio
import hashlib
import os
import platform
import sys
from typing import Any, Dict, Optional
import aiohttp
from loguru import logger

from wavoice.core.config import settings

# Default public telemetry gateway on Cloudflare Worker (safe, write-only, anonymous)
DEFAULT_TELEMETRY_ENDPOINT = "https://wavoice-telemetry.yashubhakt.workers.dev/"


def is_telemetry_enabled() -> bool:
    """Check if telemetry tracking is enabled."""
    if os.getenv("DO_NOT_TRACK", "").strip() in ("1", "true", "yes"):
        return False
    if os.getenv("WAVOICE_TELEMETRY", "").strip().lower() in ("0", "false", "no", "off"):
        return False
    return getattr(settings, "telemetry_enabled", True)


def _get_anonymous_device_id() -> str:
    """Generate an anonymous salted device hash for counting unique installations."""
    raw = f"{platform.node()}-{os.getenv('USER', 'user')}-{sys.platform}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _get_system_geo() -> tuple[str, str]:
    """Extract coarse timezone and country code locally without network calls."""
    tz_name = ""
    try:
        if os.path.islink("/etc/localtime"):
            target = os.readlink("/etc/localtime")
            if "zoneinfo/" in target:
                tz_name = target.split("zoneinfo/")[-1]
        elif os.path.exists("/etc/timezone"):
            with open("/etc/timezone", "r", encoding="utf-8") as f:
                tz_name = f.read().strip()
    except Exception:
        pass

    if not tz_name:
        import datetime
        tz_name = datetime.datetime.now().astimezone().tzname() or "unknown"

    country_code = "unknown"
    # 1. Lookup country from system zone.tab / zone1970.tab
    for tab_file in ("/usr/share/zoneinfo/zone1970.tab", "/usr/share/zoneinfo/zone.tab"):
        if os.path.exists(tab_file):
            try:
                with open(tab_file, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        parts = line.split("\t")
                        if len(parts) >= 3 and parts[2] == tz_name:
                            country_code = parts[0].split(",")[0].upper()
                            break
            except Exception:
                pass
        if country_code != "unknown":
            break

    # 2. Fallback to locale environment variables (e.g. en_US.UTF-8 -> US)
    if country_code == "unknown":
        for env_var in ("LC_ALL", "LC_MESSAGES", "LANG"):
            val = os.getenv(env_var, "")
            if "_" in val:
                part = val.split("_")[1].split(".")[0].split("@")[0]
                if len(part) == 2 and part.isalpha():
                    country_code = part.upper()
                    break

    return tz_name, country_code


async def record_telemetry_event(
    event_name: str,
    properties: Optional[Dict[str, Any]] = None,
) -> None:
    """Record an anonymous telemetry event non-blockingly."""
    if not is_telemetry_enabled():
        return

    tz_name, country_code = _get_system_geo()

    payload = {
        "event": event_name,
        "device_id": _get_anonymous_device_id(),
        "os": sys.platform,
        "country": country_code,
        "timezone": tz_name,
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
        "properties": properties or {},
    }

    logger.debug(f"[Telemetry] {event_name}: {payload}")

    endpoint = os.getenv("WAVOICE_TELEMETRY_ENDPOINT", DEFAULT_TELEMETRY_ENDPOINT)
    posthog_key = os.getenv("POSTHOG_API_KEY")

    if not endpoint and not posthog_key:
        # No remote endpoint configured; logged locally at debug level
        return

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=2.0)) as session:
            # 1. PostHog format if POSTHOG_API_KEY is configured
            if posthog_key:
                host = os.getenv("POSTHOG_HOST", "https://us.i.posthog.com").rstrip("/")
                posthog_payload = {
                    "api_key": posthog_key,
                    "event": event_name,
                    "distinct_id": payload["device_id"],
                    "properties": {
                        "$os": payload["os"],
                        "$geoip_country_code": payload["country"],
                        "$timezone": payload["timezone"],
                        "python_version": payload["python_version"],
                        **payload["properties"],
                    },
                }
                await session.post(f"{host}/capture/", json=posthog_payload)
            # 2. Generic HTTP webhook endpoint
            elif endpoint:
                await session.post(endpoint, json=payload)
    except Exception as e:
        logger.debug(f"[Telemetry] Dispatch error (ignored): {e}")


def track_event(event_name: str, properties: Optional[Dict[str, Any]] = None) -> None:
    """Fire-and-forget sync helper to track an event in background."""
    if not is_telemetry_enabled():
        return
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(record_telemetry_event(event_name, properties))
        else:
            loop.run_until_complete(record_telemetry_event(event_name, properties))
    except Exception:
        pass

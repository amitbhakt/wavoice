"""LiveKit Cloud credential detector and parser."""

import os
import re
from pathlib import Path
from typing import Dict, Optional, Tuple
from loguru import logger


def parse_livekit_env_block(text: str) -> Dict[str, str]:
    """Parse a pasted block of .env text copied from LiveKit Cloud console."""
    credentials: Dict[str, str] = {}
    patterns = {
        "LIVEKIT_URL": r"(?:LIVEKIT_URL|URL)\s*=\s*([^\s\r\n]+)",
        "LIVEKIT_API_KEY": r"(?:LIVEKIT_API_KEY|API_KEY)\s*=\s*([^\s\r\n]+)",
        "LIVEKIT_API_SECRET": r"(?:LIVEKIT_API_SECRET|API_SECRET|SECRET)\s*=\s*([^\s\r\n]+)",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            credentials[key] = match.group(1).strip("\"'")
    return credentials


def detect_local_livekit_config() -> Optional[Dict[str, str]]:
    """Check ~/.livekit/config.yaml or ./livekit.toml for existing credentials."""
    home_config = Path.home() / ".livekit" / "config.yaml"
    if home_config.exists():
        try:
            import yaml
            with open(home_config, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                # LiveKit CLI stores active project or projects map
                projects = data.get("projects", {})
                default_name = data.get("default_project") or (next(iter(projects)) if projects else None)
                if default_name and default_name in projects:
                    proj = projects[default_name]
                    return {
                        "LIVEKIT_URL": proj.get("url", ""),
                        "LIVEKIT_API_KEY": proj.get("api_key", ""),
                        "LIVEKIT_API_SECRET": proj.get("api_secret", ""),
                        "project_name": default_name,
                    }
        except Exception as e:
            logger.debug(f"[LiveKit Detector] Error reading ~/.livekit/config.yaml: {e}")

    # Check project-level livekit.toml
    local_toml = Path("livekit.toml")
    if local_toml.exists():
        try:
            import tomllib
            with open(local_toml, "rb") as f:
                data = tomllib.load(f)
                return {
                    "LIVEKIT_URL": data.get("url", ""),
                    "LIVEKIT_API_KEY": data.get("api_key", ""),
                    "LIVEKIT_API_SECRET": data.get("api_secret", ""),
                    "project_name": data.get("subdomain", "local"),
                }
        except Exception as e:
            logger.debug(f"[LiveKit Detector] Error reading livekit.toml: {e}")

    return None

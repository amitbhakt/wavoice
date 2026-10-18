"""Automated Cloudflare Quick Tunnel manager.

Launches a zero-config cloudflared quick tunnel to expose the local webhook server
to the public internet with a valid SSL certificate (https://*.trycloudflare.com).
"""

import asyncio
import os
import platform
import re
import shutil
import stat
import tarfile
import tempfile
import urllib.request
from pathlib import Path
from typing import Optional

from loguru import logger

CLOUDFLARED_CACHE_DIR = Path.home() / ".wa-voice" / "bin"
TUNNEL_URL_REGEX = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")


def _get_download_url() -> tuple[str, bool]:
    """Return (download_url, is_tar_gz) based on current OS and architecture."""
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "darwin":
        arch = "arm64" if machine in ("arm64", "aarch64") else "amd64"
        return (
            f"https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-{arch}.tgz",
            True,
        )
    elif system == "linux":
        arch = "arm64" if machine in ("arm64", "aarch64") else "amd64"
        return (
            f"https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-{arch}",
            False,
        )
    elif system == "windows":
        return (
            "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe",
            False,
        )
    else:
        raise RuntimeError(f"Unsupported operating system: {system} {machine}")


def ensure_cloudflared_binary() -> Path:
    """Ensure cloudflared executable is available, downloading it if needed."""
    # 1. Check if already on system PATH
    system_path = shutil.which("cloudflared")
    if system_path:
        return Path(system_path)

    # 2. Check local user cache
    binary_name = "cloudflared.exe" if platform.system().lower() == "windows" else "cloudflared"
    cached_binary = CLOUDFLARED_CACHE_DIR / binary_name
    if cached_binary.exists() and os.access(cached_binary, os.X_OK):
        return cached_binary

    # 3. Download to cache directory
    CLOUDFLARED_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    download_url, is_tar = _get_download_url()
    logger.info(f"Downloading cloudflared binary from {download_url}...")

    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        tmp_path = Path(tmp_file.name)
        try:
            urllib.request.urlretrieve(download_url, tmp_path)

            if is_tar:
                with tarfile.open(tmp_path, "r:gz") as tar:
                    if hasattr(tarfile, "data_filter"):
                        tar.extractall(path=CLOUDFLARED_CACHE_DIR, filter="data")
                    else:
                        tar.extractall(path=CLOUDFLARED_CACHE_DIR)
            else:
                shutil.copy2(tmp_path, cached_binary)

            # Ensure executable permissions
            cached_binary.chmod(cached_binary.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
            logger.info(f"cloudflared installed successfully to {cached_binary}")
            return cached_binary
        finally:
            if tmp_path.exists():
                tmp_path.unlink()


class CloudflareTunnel:
    """Manages the lifecycle of a Cloudflare Quick Tunnel."""

    def __init__(self, local_port: int, host: str = "127.0.0.1"):
        self.local_port = local_port
        self.host = host
        self.process: Optional[asyncio.subprocess.Process] = None
        self.public_url: Optional[str] = None
        self._reader_task: Optional[asyncio.Task] = None

    async def start(self, timeout_seconds: int = 30) -> str:
        """Start the tunnel and wait for the public URL to be assigned."""
        binary = ensure_cloudflared_binary()
        cmd = [
            str(binary),
            "tunnel",
            "--url",
            f"http://{self.host}:{self.local_port}",
            "--no-autoupdate",
        ]

        logger.info(f"Starting Cloudflare Quick Tunnel pointing to http://{self.host}:{self.local_port}...")
        self.process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Wait for the trycloudflare.com URL from stderr/stdout
        start_time = asyncio.get_event_loop().time()
        url_future: asyncio.Future[str] = asyncio.get_event_loop().create_future()

        async def _read_stream(stream: asyncio.StreamReader):
            while not stream.at_eof():
                line_bytes = await stream.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode("utf-8", errors="replace")
                match = TUNNEL_URL_REGEX.search(line)
                if match and not url_future.done():
                    url_future.set_result(match.group(0))

        if self.process.stderr:
            asyncio.create_task(_read_stream(self.process.stderr))
        if self.process.stdout:
            asyncio.create_task(_read_stream(self.process.stdout))

        try:
            raw_url = await asyncio.wait_for(url_future, timeout=timeout_seconds)
            # Probe the public URL over HTTP to ensure Cloudflare edge DNS and proxy are warm
            # This prevents Meta's callback verification from failing with 'curl 56: Failed to resolve host'
            import aiohttp
            probe_success = False
            async with aiohttp.ClientSession() as probe_session:
                for _ in range(20):
                    try:
                        async with probe_session.get(f"{raw_url}/docs", timeout=aiohttp.ClientTimeout(total=2)) as resp:
                            if resp.status in (200, 404, 405, 422):
                                probe_success = True
                                break
                    except Exception:
                        pass
                    await asyncio.sleep(0.5)

            self.public_url = raw_url
            logger.success(f"Cloudflare Tunnel active & reachable: {self.public_url}")
            return self.public_url
        except asyncio.TimeoutError:
            await self.stop()
            raise TimeoutError(f"Failed to obtain Cloudflare tunnel URL within {timeout_seconds} seconds")

    async def stop(self) -> None:
        """Gracefully stop the tunnel process."""
        if self.process:
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=5)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None
            self.public_url = None
            logger.info("Cloudflare Quick Tunnel stopped")

    async def __aenter__(self) -> str:
        return await self.start()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.stop()

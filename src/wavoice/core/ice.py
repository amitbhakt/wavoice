"""ICE / STUN / TURN server configuration for WebRTC audio connections."""

from typing import List, Optional
from pipecat.transports.smallwebrtc.connection import IceServer
from wavoice.core.config import settings


def optimize_ice_gathering() -> None:
    """Patch aioice to prevent 5-second timeouts on non-routable virtual tunnel/VPN interfaces.

    By default, aioice discovers every network interface (including virtual interfaces like utun6).
    If an interface has no route to the STUN server, aioice hangs for a full 5-second timeout
    before completing ICE gathering, causing WhatsApp callers to hear 5-7 extra seconds of ringing.
    Filtering to active/routable addresses reduces ICE gathering latency from 5000ms to ~15ms.
    """
    try:
        import socket
        import aioice.ice

        def _fast_get_host_addresses(use_ipv4: bool = True, use_ipv6: bool = False) -> List[str]:
            addrs: List[str] = []
            if use_ipv4:
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    # Query OS routing table for the primary default gateway route
                    s.connect(("8.8.8.8", 80))
                    primary = s.getsockname()[0]
                    s.close()
                    if primary and primary != "127.0.0.1":
                        addrs.append(primary)
                except Exception:
                    pass
            # Fallback to standard aioice discovery if primary route detection fails
            return addrs or aioice.ice._default_get_host_addresses(use_ipv4=use_ipv4, use_ipv6=use_ipv6)

        if not hasattr(aioice.ice, "_default_get_host_addresses"):
            aioice.ice._default_get_host_addresses = aioice.ice.get_host_addresses
            aioice.ice.get_host_addresses = _fast_get_host_addresses
    except Exception:
        pass


def build_ice_servers(
    stun_url: Optional[str] = None,
    turn_url: Optional[str] = None,
    turn_username: Optional[str] = None,
    turn_password: Optional[str] = None,
) -> List[IceServer]:
    """Construct the list of ICE servers for Pipecat's SmallWebRTC connections."""
    optimize_ice_gathering()
    servers: List[IceServer] = []

    # 1. Primary STUN server
    stun = stun_url or settings.stun_server
    if stun:
        servers.append(IceServer(urls=stun))

    # 2. Optional TURN relay server
    turn = turn_url or settings.turn_server
    user = turn_username or settings.turn_username
    pwd = turn_password or settings.turn_password

    if turn and user and pwd:
        servers.append(
            IceServer(
                urls=turn,
                username=user,
                credential=pwd,
            )
        )

    return servers

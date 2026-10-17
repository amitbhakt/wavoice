"""Starter WhatsApp Voice AI Agent powered by LiveKit Inference."""

import asyncio
from typing import Optional
from loguru import logger

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    AutoSubscribe,
    JobContext,
    WorkerOptions,
    inference,
)


DEFAULT_AGENT_INSTRUCTIONS = (
    "You are a friendly and enthusiastic voice assistant confirming a successful "
    "WhatsApp voice setup on LiveKit Cloud. Keep your answers brief, natural, and conversational "
    "(1-2 sentences). If the user responds, confirms they can hear you, or asks if it works, "
    "tell them their setup is completely working with crystal clear audio. "
    "If the user says they are good, says goodbye, or thanks you, congratulate them warmly on their "
    "verified setup and say goodbye."
)

DEFAULT_GREETING = (
    "Hello! You have successfully connected WhatsApp AI calling via LiveKit Cloud. "
    "I am your live test assistant. How are you doing today?"
)


async def default_livekit_entrypoint(ctx: JobContext) -> None:
    """Default entrypoint called when an agent worker joins a room."""
    logger.info(f"[LiveKit Agent] Connecting to room '{ctx.room.name}'...")
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    agent = Agent(
        instructions=DEFAULT_AGENT_INSTRUCTIONS,
        id="wavoice-agent",
    )

    # Use LiveKit Inference (no separate OpenAI/Deepgram/Cartesia keys required!)
    session = AgentSession(
        stt=inference.STT(model="deepgram/nova-3"),
        llm=inference.LLM(model="openai/gpt-4o-mini"),
        tts=inference.TTS(model="cartesia/sonic"),
    )

    await session.start(agent, room=ctx.room)
    logger.success(f"[LiveKit Agent] Agent joined room '{ctx.room.name}', speaking greeting...")
    await session.say(DEFAULT_GREETING)


def run_livekit_agent_worker(
    livekit_url: Optional[str] = None,
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None,
    agent_name: str = "wavoice-agent",
) -> None:
    """Run the LiveKit agent worker as a background process or thread."""
    import os

    if livekit_url:
        os.environ["LIVEKIT_URL"] = livekit_url
    if api_key:
        os.environ["LIVEKIT_API_KEY"] = api_key
    if api_secret:
        os.environ["LIVEKIT_API_SECRET"] = api_secret
    if agent_name:
        os.environ["LIVEKIT_AGENT_NAME"] = agent_name

    opts = WorkerOptions(
        entrypoint_fnc=default_livekit_entrypoint,
        ws_url=livekit_url,
        api_key=api_key,
        api_secret=api_secret,
        agent_name=agent_name,
    )
    server = AgentServer.from_server_options(opts)
    try:
        asyncio.run(server.run(devmode=True))
    except Exception as e:
        logger.debug(f"[LiveKit Agent Worker] Worker exit notice: {e}")

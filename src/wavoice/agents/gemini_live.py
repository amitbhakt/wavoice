"""Default zero-friction voice agent using Google Gemini Multimodal Live API.

Provides native speech-to-speech interaction (~300ms latency) with only ONE API key.
"""

import os
from loguru import logger
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.transports.whatsapp.api import WhatsAppConnectCall

from wavoice.core.config import settings


async def run_gemini_live_agent(
    connection: SmallWebRTCConnection,
    call: WhatsAppConnectCall,
    system_instruction: str = (
        "You are a friendly, concise AI voice assistant speaking with a caller on WhatsApp. "
        "Keep your answers short and natural for a voice conversation."
    ),
    voice: str = "Puck",
) -> None:
    """Execute the default Gemini 2.0 Flash Live speech-to-speech pipeline."""
    api_key = settings.gemini_api_key or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY or GOOGLE_API_KEY is required to run the default Gemini Live voice agent. "
            "Please set it in your .env file or register a custom pipeline with @app.on_call."
        )

    # Import Gemini Live LLM service
    try:
        from pipecat.services.google.gemini_live.llm import GeminiLiveLLMService
    except ImportError:
        try:
            from pipecat.services.gemini_multimodal_live.gemini import GeminiMultimodalLiveLLMService as GeminiLiveLLMService  # type: ignore
        except ImportError:
            raise ImportError(
                "Gemini Live service requires 'pipecat-ai[google]'. Run: uv add 'pipecat-ai[google]'"
            )

    caller_from = getattr(call, "from_", getattr(call, "From", "caller"))
    logger.info(f"[GeminiLive] Starting agent for caller {caller_from} (voice={voice})")

    # 1. Initialize Gemini Live Multimodal Service
    # Note: Disabling Gemini's server-side VAD allows our local Silero + SmartTurn analyzer
    # to explicitly control when turns start and end (activity_start / activity_end), eliminating
    # silence deadlocks where Gemini waits endlessly for server-side turn completion.
    from pipecat.services.google.gemini_live.llm import GeminiLiveLLMSettings, GeminiVADParams

    llm = GeminiLiveLLMService(
        api_key=api_key,
        voice=voice,
        system_instruction=system_instruction,
        settings=GeminiLiveLLMSettings(
            vad=GeminiVADParams(disabled=True),
        ),
    )

    # 2. Configure SmallWebRTCTransport for this connection
    from pipecat.transports.base_transport import TransportParams

    transport = SmallWebRTCTransport(
        webrtc_connection=connection,
        params=TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            video_in_enabled=False,
            bot_vad_stop_secs=0.5,
        ),
    )

    # 3. Configure Context Aggregators with Silero VAD for Ultra-Low Latency (~300ms)
    from pipecat.audio.vad.silero import SileroVADAnalyzer
    from pipecat.audio.vad.vad_analyzer import VADParams
    from pipecat.processors.aggregators.llm_context import LLMContext
    from pipecat.processors.aggregators.llm_response_universal import (
        LLMContextAggregatorPair,
        LLMUserAggregatorParams,
    )
    from pipecat.turns.user_stop.speech_timeout_user_turn_stop_strategy import SpeechTimeoutUserTurnStopStrategy
    from pipecat.turns.user_turn_strategies import UserTurnStrategies

    # Low-latency speech timeout: end turn 0.4s after user stops speaking
    stop_strategy = SpeechTimeoutUserTurnStopStrategy(
        user_speech_timeout=0.4,
        wait_for_transcript=False,
    )

    context = LLMContext([])
    context_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=0.2)),
            user_turn_strategies=UserTurnStrategies(stop=[stop_strategy]),
        ),
        realtime_service_mode=True,
    )
    user_aggregator, assistant_aggregator = context_aggregator

    # 4. Assemble Pipeline
    pipeline = Pipeline([
        transport.input(),
        user_aggregator,
        llm,
        transport.output(),
        assistant_aggregator,
    ])

    task = PipelineTask(pipeline=pipeline, params=PipelineParams(allow_interruptions=True))

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info(f"[GeminiLive] Caller {caller_from} disconnected")
        await task.cancel()

    # Trigger Gemini to start conversation with exact greeting requested
    from pipecat.frames.frames import LLMContextFrame

    initial_context = LLMContext([
        {
            "role": "user",
            "content": (
                "The caller just connected. Greet them immediately by saying exactly: "
                "'Hi, I'm your Gemini AI assistant connected via WhatsApp. You have successfully enabled WhatsApp AI calling.'"
            ),
        }
    ])
    await task.queue_frame(LLMContextFrame(context=initial_context))

    # Disable handle_sigint on pipeline runner so Uvicorn manages Ctrl+C cleanly without hang
    runner = PipelineRunner(handle_sigint=False)
    await runner.run(task)
    logger.info(f"[GeminiLive] Finished session for call {call.id}")

"""Example: Using custom STT + LLM + TTS pipeline with wa-voice.

Demonstrates how to swap out Gemini Live for a traditional cascaded stack:
- STT: Deepgram (or Whisper, Groq, etc.)
- LLM: OpenAI / Anthropic / Groq / Ollama
- TTS: Cartesia / ElevenLabs / Azure

Run this with:
    uv run python examples/custom_stt_llm_tts.py
"""

import os
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.services.cartesia import CartesiaTTSService
from pipecat.services.deepgram import DeepgramSTTService
from pipecat.services.openai import OpenAILLMService
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.transports.whatsapp.api import WhatsAppConnectCall

from wavoice import WhatsAppVoiceApp

app = WhatsAppVoiceApp()


@app.on_call
async def handle_call(transport: SmallWebRTCTransport, call: WhatsAppConnectCall):
    caller = getattr(call, "from_", getattr(call, "From", "caller"))
    print(f"Incoming WhatsApp call from {caller}!")

    # 1. Services
    stt = DeepgramSTTService(api_key=os.environ["DEEPGRAM_API_KEY"])
    llm = OpenAILLMService(api_key=os.environ["OPENAI_API_KEY"], model="gpt-4o-mini")
    tts = CartesiaTTSService(
        api_key=os.environ["CARTESIA_API_KEY"],
        voice_id="79a125e8-cd45-4c13-8a67-188112f4dd22",  # British Lady / Barbershop
    )

    # 2. Context Aggregation & VAD
    context = LLMContext([
        {
            "role": "system",
            "content": "You are a helpful voice assistant on WhatsApp. Keep your answers brief and conversational.",
        }
    ])
    pair = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer()),
    )
    user_agg, assistant_agg = pair

    # 3. Assemble Pipeline
    pipeline = Pipeline([
        transport.input(),
        stt,
        user_agg,
        llm,
        tts,
        transport.output(),
        assistant_agg,
    ])

    task = PipelineTask(pipeline=pipeline, params=PipelineParams(allow_interruptions=True))

    @transport.event_handler("on_client_disconnected")
    async def on_disconnect(transport, client):
        print(f"Caller {caller} hung up.")
        await task.cancel()

    runner = PipelineRunner()
    await runner.run(task)


if __name__ == "__main__":
    app.run()

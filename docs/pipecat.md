# Pipecat Python Multi-Model Pipeline Guide

Build highly customizable, multi-model real-time voice pipelines on WhatsApp with Python and [Pipecat](https://github.com/pipecat-ai/pipecat).

---

## Overview

[Pipecat](https://github.com/pipecat-ai/pipecat) is a real-time framework for voice and multimodal conversational AI. It lets you compose pipelines using any Speech-to-Text (STT), Large Language Model (LLM), and Text-to-Speech (TTS) service.

`WAVoice` solves the hardest part of using Pipecat with WhatsApp:
- Automated WebRTC SDP offer/answer exchange with Meta Graph API.
- Cloudflare Quick Tunnel setup for local development.
- Webhook deduplication and call claim locking.
- Exposing a clean `WhatsAppVoiceApp` SDK with an `@app.on_call` decorator.

---

## Mode 1: Instant Native Speech-to-Speech (Gemini 2.0 Flash)

For ~300ms latency without any pipeline code, WAVoice includes a built-in Gemini Multimodal Live agent:

```bash
uvx wavoice init
# or: wavoice start
```

Requires only:
- `WHATSAPP_TOKEN`
- `WHATSAPP_APP_SECRET`
- `GEMINI_API_KEY`

---

## Mode 2: Custom Multi-Model Cascaded Pipelines (STT $\rightarrow$ LLM $\rightarrow$ TTS)

For complete control over each layer (e.g. Deepgram for STT, OpenAI/Anthropic/Ollama for LLM, Cartesia/ElevenLabs for TTS), write a standard Pipecat pipeline:

```python
import os
from wavoice import WhatsAppVoiceApp
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.services.deepgram import DeepgramSTTService
from pipecat.services.openai import OpenAILLMService
from pipecat.services.cartesia import CartesiaTTSService

app = WhatsAppVoiceApp()

@app.on_call
async def handle_incoming_call(transport, call_info):
    caller = getattr(call_info, "from_", "caller")
    print(f"Incoming WhatsApp voice call from {caller}")

    # 1. Modular Services
    stt = DeepgramSTTService(api_key=os.environ["DEEPGRAM_API_KEY"])
    llm = OpenAILLMService(api_key=os.environ["OPENAI_API_KEY"], model="gpt-4o-mini")
    tts = CartesiaTTSService(api_key=os.environ["CARTESIA_API_KEY"], voice_id="...")

    # 2. Context Aggregation & Silero Voice Activity Detection (VAD)
    context = LLMContext([
        {"role": "system", "content": "You are a concise, helpful voice assistant answering a WhatsApp call."}
    ])
    user_agg, assistant_agg = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer()),
    )

    # 3. Assemble Pipeline
    pipeline = Pipeline([
        transport.input(),    # WebRTC Audio In from WhatsApp
        stt,                  # Speech-to-Text
        user_agg,             # Turn Aggregator
        llm,                  # Large Language Model
        tts,                  # Text-to-Speech
        transport.output(),   # WebRTC Audio Out to WhatsApp
        assistant_agg,
    ])

    # 4. Run Task with Interruption Support
    task = PipelineTask(pipeline=pipeline, params=PipelineParams(allow_interruptions=True))
    runner = PipelineRunner()
    await runner.run(task)

if __name__ == "__main__":
    app.run()  # Launches tunnel, registers Meta webhooks, and serves pipeline
```

*(See [examples/custom_stt_llm_tts.py](../examples/custom_stt_llm_tts.py) for the complete runnable example).*

---

## Production Deployment

When taking your Pipecat pipeline to production:
1. Deploy behind a reverse proxy or cloud host with a static HTTPS domain.
2. Run your app with `--public-url`:
   ```bash
   python my_bot.py --public-url https://voice.yourdomain.com
   ```
3. WAVoice will register `https://voice.yourdomain.com/webhook` with Meta instead of spinning up an ephemeral Cloudflare Quick Tunnel.

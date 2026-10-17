# WAVoice: Set Up WhatsApp Voice AI in 90 Seconds

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Powered by Pipecat](https://img.shields.io/badge/powered%20by-Pipecat-green.svg)](https://github.com/pipecat-ai/pipecat)
[![Author: Amit Bhakt](https://img.shields.io/badge/creator-Amit%20Bhakt-orange.svg)](https://github.com/amitbhakt)

> **The zero-friction, one-command pipeline for WhatsApp Voice AI.**  
> Go from zero to an active AI voice agent answering live WhatsApp calls in under **90 seconds**. No manual Meta dashboard clicking, no ngrok account setup, and no WebRTC configuration required.

<p align="center">
  <img src="assets/demo.gif" alt="WAVoice 90-Second Demo" width="100%" />
</p>

Created by [Amit Bhakt](https://github.com/amitbhakt), `WAVoice` solves the hardest part of building WhatsApp voice agents: **the entire telephony and networking plumbing**.

---

## What You Need First

Before running the setup wizard, have these 3 items ready from your [Meta Developer Portal](https://developers.facebook.com):

1. **Meta Developer App** with the WhatsApp product added.
2. **Meta System User Access Token** with permissions `whatsapp_business_messaging` and `whatsapp_business_management`.
3. **WhatsApp Business Phone Number** (Meta's free test number works out of the box).
*(Optional: A Google Gemini API key if you want to use the default native speech-to-speech agent).*

---

## Why Developers Use WAVoice

Setting up WhatsApp voice calling traditionally requires hours of manual work: navigating Meta Business Manager, registering phone number IDs, manually creating ngrok tunnels, pasting webhook verification tokens, handling WebRTC SDP offer/answers, and diagnosing why audio drops over NAT.

**`WAVoice` collapses all of that into a single 90-second command (`wavoice init`):**

1. **Automated Cloudflare Quick Tunnel**: Ephemeral public HTTPS TLS gateway with zero tokens or account sign-ups for instant local testing.
2. **Auto-Discovery**: Extracts your WABA ID and Phone Number ID directly from your token via Meta Graph API.
3. **Programmatic Calling Activation**: Enables WhatsApp Voice Calling and makes the Call button visible automatically.
4. **Full 3-Tier Webhook Sync**: Programmatically configures Phone Number overrides, WABA subscriptions, and App subscriptions.
5. **Turnkey WebRTC Plumbing**: Automated STUN/TURN traversal, SRTP audio streaming, and atomic call-claim locks to prevent duplicate webhook delivery.

---

## How It Works: Instant Testing vs. Custom Pipelines

Whether you want a complete out-of-the-box agent or a custom multi-model architecture, `WAVoice` separates the **telephony infrastructure** from your **AI logic**:

```
                       ┌────────────────────────────────────────┐
                       │  Telephony Infrastructure Layer        │
                       │  (Handled automatically by WAVoice)    │
                       │                                        │
                       │  - Cloudflare Quick Tunnel             │
                       │  - Meta Graph API Webhooks             │
                       │  - WebRTC SDP Offer / Answer           │
                       │  - SRTP Audio Stream Decoupling        │
                       └───────────────────┬────────────────────┘
                                           │
                       ┌───────────────────┴────────────────────┐
                       ▼                                        ▼
      ┌─────────────────────────────────┐      ┌─────────────────────────────────┐
      │  Mode A: Out-of-the-Box (90s)   │      │  Mode B: Custom Layers          │
      │                                 │      │  (Pluggable Pipecat Pipeline)   │
      │  Run: `wavoice start`           │      │                                 │
      │  Native Speech-to-Speech via    │      │  - STT: Deepgram, Whisper, Groq │
      │  Gemini 2.0 Flash Live          │      │  - LLM: OpenAI, Claude, Ollama  │
      │  (~300ms latency, zero code)    │      │  - TTS: Cartesia, ElevenLabs    │
      └─────────────────────────────────┘      └─────────────────────────────────┘
```

### How does the one-command setup help developers who want separate layers?
When you want to build a cascaded stack (**STT $\rightarrow$ LLM $\rightarrow$ TTS**), you still face the exact same frustrating hurdle: connecting WhatsApp's WebRTC audio stream to your server. 

By running `wavoice init`, **your WhatsApp number and webhook plumbing are 100% configured in 90 seconds**. Then, instead of maintaining complex SIP/WebRTC servers, you simply write standard, modular Python:

```python
from wavoice import WhatsAppVoiceApp

app = WhatsAppVoiceApp()

@app.on_call
async def handle_call(transport, call_info):
    # 'transport' already receives raw audio from WhatsApp WebRTC
    # Plug in any separate STT, LLM, or TTS processor:
    pipeline = Pipeline([
        transport.input(),
        DeepgramSTTService(...),
        OpenAILLMService(...),
        CartesiaTTSService(...),
        transport.output(),
    ])
    ...
```

---

## 90-Second Quickstart

### 1. Launch Setup
Run instantly with zero installation (auto-provisions Python 3.12 in an isolated sandbox):
```bash
uvx wavoice init
```
Or install via `pip` (Python 3.12+):
```bash
pip install wavoice && wavoice init
```

### 2. Enter Your 3 Credentials
The interactive wizard prompts for:
1. `WHATSAPP_TOKEN`: Meta System User access token.
2. `WHATSAPP_APP_SECRET`: Meta App Secret.
3. `GEMINI_API_KEY`: Google Gemini API key.

`WAVoice` automatically discovers your WhatsApp Business Account (WABA), checks phone number status, auto-enables WhatsApp Voice Calling, starts an HTTPS ingress tunnel, and registers all 3 tiers of Meta webhooks.

### 3. Dial & Talk
Open WhatsApp on your phone and place a voice call to your business number. Your AI agent answers immediately with real-time speech!

---

## Pre-Flight Diagnostics

To inspect your setup, token scopes, voice calling flags, and webhook routing tiers at any time:

```bash
uv run wavoice doctor
```

Output:
```text
╦ ╦╔═╗╦  ╦╔═╗╦╔═╗╔═╗   WAVoice v0.1.0
║║║╠═╣╚╗╔╝║ ║║║  ║╣    One-command WhatsApp Voice AI runtime
╚╩╝╩ ╩ ╚╝ ╚═╝╩╚═╝╚═╝

╭────────────────────────────────╮
│ WAVoice Pre-Flight Diagnostics │
╰────────────────────────────────╯
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Check                          ┃ Status       ┃ Details                      ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Meta Credentials               │ PASS         │ Token & Phone ID configured  │
│ Phone Number Reachability      │ PASS         │ Verified number: +1 555-188  │
│ WhatsApp Voice Calling API     │ PASS         │ Voice calling is ENABLED     │
│ Tier 1: Phone Override         │ ACTIVE       │ Cloudflare Tunnel Verified   │
│ Tier 2: WABA Subscription      │ ACTIVE       │ Webhook Subscribed           │
│ Tier 3: App Subscriptions      │ ACTIVE       │ calls, messages Active       │
│ Default AI Agent               │ PASS         │ Gemini 2.0 Flash Live ready  │
└────────────────────────────────┴──────────────┴──────────────────────────────┘
```

---

## Building Custom Multi-Model Pipelines

For developers building with independent STT, LLM, and TTS providers, `WAVoice` exposes the complete [Pipecat](https://github.com/pipecat-ai/pipecat) pipeline:

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
    print(f"Incoming call from {caller}")

    # 1. Custom Layer Services
    stt = DeepgramSTTService(api_key=os.environ["DEEPGRAM_API_KEY"])
    llm = OpenAILLMService(api_key=os.environ["OPENAI_API_KEY"], model="gpt-4o-mini")
    tts = CartesiaTTSService(api_key=os.environ["CARTESIA_API_KEY"], voice_id="...")

    # 2. Context Aggregation & Silero Turn Detection
    context = LLMContext([{"role": "system", "content": "You are a concise voice assistant."}])
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

    task = PipelineTask(pipeline=pipeline, params=PipelineParams(allow_interruptions=True))
    runner = PipelineRunner()
    await runner.run(task)

if __name__ == "__main__":
    app.run()  # Launches tunnel, registers Meta webhooks, and serves pipeline
```

*(See [examples/custom_stt_llm_tts.py](examples/custom_stt_llm_tts.py) for the complete runnable file. For more details, see the [Pipecat Integration Guide](docs/pipecat.md).)*

---

## CLI Command Reference

| Command | Description |
| :--- | :--- |
| `wavoice init` | Complete 90-second setup: prompts for 3 credentials, auto-discovers IDs, turns on voice calling, and launches. Pass `--no-telemetry` to opt out of usage metrics. |
| `wavoice doctor` | Runs diagnostics across Meta credentials, calling status, and 3-tier webhooks. |
| `wavoice start` | Starts the server, establishes the Cloudflare tunnel, and begins accepting calls. Pass `--no-telemetry` to run with telemetry disabled. |
| `wavoice dograh setup` | **One-command Dograh Cloud setup**: connects Meta WhatsApp calling, auto-provisions telephony in Dograh Cloud, deploys a ready-to-test sample voice agent, and routes webhooks in <2 mins. |
| `wavoice livekit setup` | **One-command LiveKit Cloud setup**: connects Meta WhatsApp calling, configures webhooks, auto-detects LiveKit credentials, and sets up a LiveKit voice agent. |
| `wavoice livekit dev` | Starts the LiveKit webhook bridge and launches the bundled LiveKit voice agent. |
| `wavoice livekit doctor` | Diagnostics check for LiveKit Cloud credentials, connectivity, and Meta WhatsApp voice calling. |

---

## Dograh Cloud Integration (Visual No-Code Studio)

If you prefer building voice agents visually with **[Dograh](https://dograh.com)** rather than writing code, WAVoice completely automates your Meta and Dograh Cloud setup:

```bash
uvx wavoice dograh setup
# or: pip install wavoice && wavoice dograh setup
```

In under 30 seconds, this single command:
1. Validates your Meta token and auto-discovers your Phone Number ID and WABA ID.
2. Auto-enables WhatsApp Voice Calling on Meta (`calling.status = "ENABLED"`).
3. Registers the WhatsApp Telephony Configuration in Dograh Cloud (`api.dograh.com`).
4. Syncs your phone numbers into Dograh.
5. Deploys and publishes a test voice agent workflow in Dograh.
6. Binds your WhatsApp number to the new agent workflow.
7. Overrides Meta's webhooks to route incoming calls directly to Dograh Cloud's managed infrastructure.

When it finishes, open WhatsApp on your phone, call your business number, and speak directly to your Dograh visual agent!

👉 *For custom prompt engineering, tools, and voices, see the [Dograh Cloud Integration Guide](docs/dograh.md).*

---

## LiveKit Cloud Integration (Real-Time Voice AI)

If you are using **[LiveKit](https://livekit.io)** to build low-latency voice agents, WAVoice bridges WhatsApp voice calls directly into LiveKit Cloud rooms with zero manual webhook or telephony setup:

```bash
# 1. Connect WhatsApp to LiveKit Cloud (interactive wizard)
uv run wavoice livekit setup

# 2. Launch the bridge & start talking
uv run wavoice livekit dev
```

### Highlights:
- **Ready Out-of-the-Box**: Includes a bundled starter voice agent (`wavoice-agent`) so you can test live calls immediately.
- **Auto-Detection**: Automatically reads your `LIVEKIT_URL`, `LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET` from `~/.livekit/config.yaml` or parses the 1-click `.env` snippet from the LiveKit Cloud dashboard.
- **Ingress Flexibility**: Choose between an automated **Cloudflare Quick Tunnel** (zero-config for local dev) or supply your own `--public-url` for staging/production.
- **LiveKit Insights Ready**: Automatically registers as a named agent (`wavoice-agent`) so call telemetry and room sessions are tracked in your LiveKit Cloud dashboard.

👉 *For routing to existing cloud agents, production deployment, and webhook code snippets, see the [LiveKit Cloud Integration Guide](docs/livekit.md).*

---

## ⚠️ Limitations & Production Deployment

- **Cloudflare Quick Tunnels**: By default, `WAVoice` spins up an automated Cloudflare Quick Tunnel (`trycloudflare.com`). This is designed strictly for **local development, rapid prototyping, and hackathons**—it requires zero account setup, but the tunnel URL is ephemeral and changes whenever the server restarts.
- **24/7 Production Deployment**:
  - **Persistent Ingress**: Host your service behind a static domain or reverse proxy (e.g., Caddy, Nginx, or AWS ALB) and pass your permanent URL via `--public-url`:
    ```bash
    wavoice start --public-url https://voice.yourdomain.com
    # or
    wavoice livekit dev --public-url https://voice.yourdomain.com
    ```
  - **With Dograh Cloud**: If you use `wavoice dograh setup`, Meta's webhooks are routed directly to Dograh Cloud's managed production infrastructure, so you don't need any local tunnel or server running at all!

---

## Technical Details

- **WebRTC Protocol**: WhatsApp Calling exchanges SDP offers/answers over HTTPS and streams media via SRTP over UDP. `WAVoice` uses `aiortc` and Pipecat's `SmallWebRTCTransport` to negotiate codecs and stream PCM audio.
- **Webhook Delivery Deduplication**: Meta delivers webhooks at least once, causing race conditions where multiple workers answer the same call. `WAVoice` uses atomic in-memory claiming per `call_id` to guarantee calls are answered exactly once.
- **Bi-directional Termination**: If the caller hangs up, `WAVoice` tears down the pipeline. If the bot hangs up or times out, `WAVoice` calls `POST /v21.0/{phone_number_id}/calls` with `action: "terminate"` to end the call on the user's phone.
- **Telemetry & Privacy**: WAVoice collects anonymous usage metrics (command runs, answered calls, and coarse country/timezone) to improve SDK stability. No personal info, phone numbers, tokens, or audio data are ever collected. Telemetry is enabled by default, and you can opt out at any time by:
  - Running `wavoice init --no-telemetry` or `wavoice start --no-telemetry`
  - Setting `WAVOICE_TELEMETRY=false` in `.env`
  - Setting `DO_NOT_TRACK=1` in your environment

---

## Maintainer & Credits

Crafted by **Amit Bhakt** ([@amitbhakt](https://github.com/amitbhakt)).

Contributions, issues, and feature suggestions are welcome on GitHub at [https://github.com/amitbhakt/wavoice](https://github.com/amitbhakt/wavoice).

---

## License

MIT License. Copyright (c) 2026 Amit Bhakt.

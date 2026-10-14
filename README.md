# WAVoice: Set Up WhatsApp Voice AI in 90 Seconds

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Powered by Pipecat](https://img.shields.io/badge/powered%20by-Pipecat-green.svg)](https://github.com/pipecat-ai/pipecat)
[![Author: Amit Bhakt](https://img.shields.io/badge/creator-Amit%20Bhakt-orange.svg)](https://github.com/amitbhakt)

> **The zero-friction, one-command pipeline for WhatsApp Voice AI.**  
> Go from zero to an active AI voice agent answering live WhatsApp calls in under **90 seconds**. No manual Meta dashboard clicking, no ngrok account setup, and no WebRTC configuration required.

Created by [Amit Bhakt](https://github.com/amitbhakt), `WAVoice` solves the hardest part of building WhatsApp voice agents: **the entire telephony and networking plumbing**.

---

## Why Developers Use WAVoice

Setting up WhatsApp voice calling traditionally requires hours of manual work: navigating Meta Business Manager, registering phone number IDs, manually creating ngrok tunnels, pasting webhook verification tokens, handling WebRTC SDP offer/answers, and diagnosing why audio drops over NAT.

**`WAVoice` collapses all of that into a single 90-second command (`wavoice init`):**

1. **Automated Cloudflare Quick Tunnel**: Ephemeral public HTTPS TLS gateway with zero tokens or account sign-ups.
2. **Auto-Discovery**: Extracts your WABA ID and Phone Number ID directly from your token via Meta Graph API.
3. **Programmatic Calling Activation**: Enables WhatsApp Voice Calling and makes the Call button visible automatically.
4. **Full 3-Tier Webhook Sync**: Programmatically configures Phone Number overrides, WABA subscriptions, and App subscriptions.
5. **Production WebRTC Infrastructure**: Pre-configured STUN/TURN, SRTP audio handling, and atomic call claim locks (preventing duplicate webhook deliveries).

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

### Step 1: Install & Run

> [!NOTE]
> `WAVoice` requires **Python 3.12+**. Because default system Python on macOS or Windows may be older (e.g. Python 3.9), we recommend using [`uv`](https://github.com/astral-sh/uv) to automatically handle Python versioning with zero friction.

#### Option A: One-Command Instant Launch (No Install Needed)
Works across **macOS, Linux, and Windows**:
```bash
uvx wavoice init
```
*(Automatically provisions Python 3.12+ in an isolated sandbox and launches the setup wizard).*

#### Option B: Global CLI Installation
```bash
# macOS / Linux / Windows (Recommended):
uv tool install wavoice

# Then run from anywhere:
wavoice init
```

#### Option C: Standard `pip` (Requires Python $\ge$ 3.12)
- **macOS / Linux**:
  ```bash
  python3.12 -m venv .venv && source .venv/bin/activate
  pip install wavoice
  wavoice init
  ```
- **Windows (PowerShell / Command Prompt)**:
  ```powershell
  py -3.12 -m venv .venv
  .venv\Scripts\activate
  pip install wavoice
  wavoice init
  ```

#### Option D: From Source
```bash
git clone https://github.com/amitbhakt/wavoice.git
cd wavoice
uv sync
uv run wavoice init
```

### Step 2: Configure in 90 Seconds

The interactive wizard asks for only 3 credentials:
1. `WHATSAPP_TOKEN`: Meta System User access token.
2. `WHATSAPP_APP_SECRET`: Meta App Secret.
3. `GEMINI_API_KEY`: Google Gemini API key.

`WAVoice` automatically discovers your business accounts, activates WhatsApp voice calling, saves `.env`, and starts the server immediately.

### Step 3: Dial & Talk
Open WhatsApp on your phone and dial your business number. Your AI agent answers immediately.

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

*(See [examples/custom_stt_llm_tts.py](examples/custom_stt_llm_tts.py) for the complete runnable file)*

---

## CLI Command Reference

| Command | Description |
| :--- | :--- |
| `wavoice init` | Complete 90-second setup: prompts for 3 credentials, auto-discovers IDs, turns on voice calling, and launches. Pass `--no-telemetry` to opt out of usage metrics. |
| `wavoice doctor` | Runs diagnostics across Meta credentials, calling status, and 3-tier webhooks. |
| `wavoice start` | Starts the server, establishes the Cloudflare tunnel, and begins accepting calls. Pass `--no-telemetry` to run with telemetry disabled. |
| `wavoice dograh setup` | **One-command Dograh Cloud setup**: connects Meta WhatsApp calling, auto-provisions telephony in Dograh Cloud, deploys a ready-to-test sample voice agent, and routes webhooks in <2 mins. |

---

## Dograh Cloud Integration (No-Code Studio)

If you prefer building voice agents visually with **[Dograh](https://dograh.com)** rather than writing Python code, WAVoice can completely automate your Meta and Dograh Cloud setup:

```bash
# Using uv:
uv run wavoice dograh setup

# Or using standard pip3:
pip3 install wavoice
wavoice dograh setup
# (or: python3 -m wavoice dograh setup)
```

In under 30 seconds, this single command:
1. Validates your Meta token and auto-discovers your Phone Number ID and WABA ID.
2. Auto-enables WhatsApp Voice Calling on Meta (`calling.status = "ENABLED"`).
3. Registers the WhatsApp Telephony Configuration in Dograh Cloud (`api.dograh.com`).
4. Syncs your phone numbers into Dograh.
5. Deploys and publishes a test voice agent workflow in Dograh with a greeting: *"Hello! You have successfully connected WhatsApp AI calling via Dograh."*
6. Binds your WhatsApp number to the new agent workflow.
7. Overrides Meta's webhooks to route incoming calls directly to Dograh Cloud.

When it finishes, you can pick up WhatsApp on your phone, call your business number, and speak directly to your Dograh agent!

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

# AGENTS.md — WAVoice Agent Guide

This document is written for AI Coding Agents (such as Antigravity, Claude Code, Cursor, Codex, Windsurf, etc.) assisting users with building, running, extending, or troubleshooting **WAVoice**.

---

## 1. Project Purpose & Scope

**WAVoice** is an open-source Python framework built by Amit Bhakt ([@amitbhakt](https://github.com/amitbhakt)) that turns any WhatsApp Business Phone Number into a real-time AI voice agent in one command.

It wraps:
1. **Meta WhatsApp Business Calling API** (WhatsApp Cloud API v21.0+)
2. **Pipecat AI** (`pipecat-ai[google,webrtc]>=1.12.0`)
3. **Cloudflare Quick Tunnels** (`cloudflared`)
4. **FastAPI & aiortc** for WebRTC SDP / ICE exchange.

---

## 2. Directory Structure & Key Components

```
wavoice/
├── pyproject.toml             # Dependencies & CLI entrypoints ('wavoice', 'wa-voice')
├── README.md                  # Human-facing technical documentation
├── AGENTS.md                  # AI agent operational guide (this file)
├── examples/
│   └── custom_stt_llm_tts.py  # Reference script for Deepgram + OpenAI + Cartesia
├── src/
│   └── wavoice/
│       ├── __init__.py        # Exports WhatsAppVoiceApp, Settings, settings
│       ├── cli.py             # Typer CLI ('init', 'doctor', 'start')
│       ├── sdk.py             # WhatsAppVoiceApp SDK & @app.on_call decorator
│       ├── agents/
│       │   └── gemini_live.py # Default Gemini 2.0 Flash Multimodal Live pipeline
│       ├── core/
│       │   ├── config.py      # Pydantic Settings (.env loader)
│       │   ├── ice.py         # STUN / TURN server candidate builder
│       │   ├── lifecycle.py   # In-memory atomic call claim & deduplication
│       │   ├── meta.py        # Meta Graph API client (auto-discovery, webhooks, voice settings)
│       │   └── tunnel.py      # Cloudflare Quick Tunnel binary manager
│       └── server/
│           ├── app.py         # FastAPI webhook router & WebRTC dispatcher
│           └── security.py    # X-Hub-Signature-256 HMAC verification
└── tests/
    └── test_wa_voice.py       # Pytest unit tests (HMAC, claim locks, ice servers, cloudflared)
```

---

## 3. High-Priority Gotchas for Agents

### A. Meta Webhook Routing Hierarchy
Meta routes WhatsApp calling webhooks in strict priority order:
1. **Phone Number Level Override** (`POST /v21.0/{phone_number_id}` with `webhook_configuration`): **Highest Priority**.
2. **WABA Level Subscribed App** (`POST /v21.0/{waba_id}/subscribed_apps`): Second Priority.
3. **App Level Subscriptions** (`POST /v21.0/{app_id}/subscriptions`): Fallback.

**Crucial**: If a phone number previously had a phone-level override set (e.g. from an old ngrok or another SaaS service), Meta will **ignore** the WABA URL and send webhooks to the old URL. WAVoice explicitly overrides Tier 1 on startup via `meta.override_phone_number_webhook()`.

### B. Pipecat 1.12.0 API Specifics
1. **Transport Parameters**:
   - `SmallWebRTCTransport` does NOT use `InputParams`.
   - Use `from pipecat.transports.base_transport import TransportParams`.
   - Always pass `bot_vad_stop_secs=0.5` on realtime pipelines to avoid hanging audio buffers.
2. **PipelineTask Constructor**:
   - `PipelineTask` inherits from `PipelineWorker`.
   - Pass `params` as a keyword argument: `PipelineTask(pipeline=pipeline, params=PipelineParams(...))`.
3. **Call Object Attribute**:
   - In `WhatsAppConnectCall`, the caller number is stored under `call.from_` (with trailing underscore because `from` is a Python keyword), NOT `call.From`.
   - Safe access: `getattr(call, "from_", getattr(call, "From", "caller"))`.
4. **Pipecat WhatsAppClient Body Verification**:
   - `WhatsAppClient` throws `Missing raw request body` if `whatsapp_secret` is passed without `raw_body`.
   - WAVoice verifies the HMAC signature upfront in FastAPI, so it initializes `WhatsAppClient` with `whatsapp_secret=None` and passes `raw_body=raw_body` to `handle_webhook_request`.

### C. macOS WebRTC Local Development
Do **not** run local WebRTC development inside Docker Desktop on macOS. Docker for Mac does not forward UDP packets efficiently over bridge networks, which results in silent audio drops. Run natively using Python 3.12 and `uv`.

---

## 4. How to Assist the User

### Scenario 1: User wants to set up from scratch
Instruct them or execute:
```bash
uv run wavoice init
```
Prompt them only for:
1. `WHATSAPP_TOKEN` (Meta System User token)
2. `WHATSAPP_APP_SECRET`
3. `GEMINI_API_KEY`
WAVoice auto-discovers WABA ID and Phone Number ID and turns on Voice Calling.

### Scenario 2: User wants to diagnose issues
Run:
```bash
uv run wavoice doctor
```
Inspect the output table:
- Check if Voice calling API says `PASS`.
- Check if Tier 1, 2, and 3 webhooks point to the active tunnel.

### Scenario 3: User wants to build a custom STT + LLM + TTS pipeline
Point them to `examples/custom_stt_llm_tts.py`.
The pattern is:
```python
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

app = WhatsAppVoiceApp()

@app.on_call
async def handle_call(transport, call_info):
    # 1. Custom services (STT, LLM, TTS)
    # 2. Silero VAD + LLMContextAggregatorPair
    # 3. Assemble Pipeline: [transport.input(), stt, user_agg, llm, tts, transport.output(), assistant_agg]
    # 4. PipelineTask(pipeline=pipeline, params=PipelineParams(allow_interruptions=True))
    # 5. PipelineRunner().run(task)

if __name__ == "__main__":
    app.run()
```

---

## 5. Running Tests

Always ensure tests pass before making code modifications:
```bash
uv run pytest
```
Unit tests live in `tests/test_wa_voice.py` and test webhook challenge handshakes, HMAC computation, call dedup claim locks, cloudflared execution, and ICE candidates.

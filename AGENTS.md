# AGENTS.md — WAVoice Operational & Development Guide

This guide is designed for AI Coding Agents (Antigravity, Claude Code, Cursor, Codex, Windsurf, Copilot Workspace) operating in this repository. It defines the core mental models, architecture invariants, intent-routing decision trees, and systematic troubleshooting runbooks.

---

## 1. Core Purpose & Mental Model

### What WAVoice Is
**WAVoice** is an open-source bootstrap accelerator and telephony plumbing engine for WhatsApp Voice AI. It eliminates 100% of the friction between Meta's WhatsApp Cloud Calling API and voice agent runtimes:
- Auto-discovers WABA and Phone Number IDs from access tokens.
- Programmatically turns on WhatsApp Voice Calling on Meta Graph API.
- Sets up 3-tier webhook synchronization (Phone Override, WABA Subscription, App Events).
- Handles WebRTC SDP offer/answer exchange, SRTP audio decoupling, and atomic call-claim deduplication.

### The 4 Core Provider Ecosystems
Never confuse the supported execution modes:

| Provider | Best For | Architecture & Ingress | Local Process Needed? |
| :--- | :--- | :--- | :--- |
| **Pipecat** (`wavoice setup` / `start`) | Python engineers building custom STT $\rightarrow$ LLM $\rightarrow$ TTS or native Gemini Live pipelines. | Local WebRTC media server (`SmallWebRTCTransport` + `aiortc`) behind Cloudflare Quick Tunnel or `--public-url`. | **Yes** (`wavoice start`) |
| **Retell AI** (`wavoice retell setup` / `start`) | Voice AI developers running conversational agents via Retell AI. | Direct WebRTC bridge: Meta SDP offer $\rightarrow$ Retell WebRTC Proxy (`create-web-call` + `/webrtc-proxy/sessions`). | **Yes** (`wavoice retell start`) or Cloud Container |
| **LiveKit Cloud** (`wavoice livekit setup` / `start`) | Engineers using LiveKit Cloud & `livekit-agents` for low-latency WebRTC voice rooms. | Webhook bridge translates Meta SDP $\rightarrow$ LiveKit Cloud `AcceptWhatsAppCallRequest` $\rightarrow$ LiveKit Room. | **Yes** (`wavoice livekit start`) |
| **Dograh Cloud** (`wavoice dograh setup`) | Visual/no-code builders creating conversational workflows with drag-and-drop studio tools. | Direct cloud-to-cloud: Meta delivers webhooks directly to `api.dograh.com`. | **No** (Zero tunnels needed) |

> [!NOTE]
> **Cloudonix SIP Trunking (`feat/cloudonix-sip` branch):**
> Serverless SIP routing via Cloudonix is tracked and maintained on the `feat/cloudonix-sip` branch while upstream TLS Certificate Authority requirements with Cloudonix SBC gateways are coordinated.

---

## 2. Directory Structure & Invariants

```
wavoice/
├── pyproject.toml             # CLI entrypoints ('wavoice', 'wa-voice') and dependencies
├── README.md                  # Human-facing technical documentation
├── AGENTS.md                  # AI agent operational guide (this file)
├── docs/                      # Dedicated provider guides (livekit.md, dograh.md, pipecat.md)
├── examples/
│   └── custom_stt_llm_tts.py  # Reference script for Deepgram + OpenAI + Cartesia
├── src/
│   └── wavoice/
│       ├── __init__.py        # Exports WhatsAppVoiceApp, Settings, settings
│       ├── cli.py             # Typer CLI ('init', 'doctor', 'start', 'dograh', 'livekit')
│       ├── sdk.py             # WhatsAppVoiceApp SDK & @app.on_call decorator
│       ├── agents/
│       │   └── gemini_live.py # Default Gemini 2.0 Flash Multimodal Live pipeline
│       ├── core/
│       │   ├── config.py      # Pydantic Settings (.env loader)
│       │   ├── ice.py         # STUN / TURN server candidate builder
│       │   ├── lifecycle.py   # In-memory atomic call claim & deduplication
│       │   ├── meta.py        # Meta Graph API client (auto-discovery, webhooks, voice settings)
│       │   ├── telemetry.py   # Privacy-safe anonymous usage tracking
│       │   └── tunnel.py      # Cloudflare Quick Tunnel binary manager
│       ├── providers/         # Pluggable Voice AI runtime providers
│       │   ├── base.py        # Abstract BaseProvider interface
│       │   ├── dograh/        # Dograh Cloud visual voice agent integration
│       │   │   ├── client.py  # Dograh Cloud REST API client
│       │   │   └── provider.py# Dograh provider setup & diagnostics
│       │   ├── livekit/       # LiveKit Cloud WhatsApp Connector integration
│       │   │   ├── agent.py   # Bundled test voice agent (wavoice-agent)
│       │   │   ├── client.py  # LiveKit Cloud telephony client (AcceptWhatsAppCall)
│       │   │   ├── detector.py# Auto-detects ~/.livekit/config.yaml & LiveKit tokens
│       │   │   ├── provider.py# LiveKit setup wizard, verification & diagnostics
│       │   │   ├── runtime.py # LiveKit webhook server & agent launcher
│       │   │   └── webhook.py # FastAPI webhook handler translating Meta SDP offers
│       │   └── retell/        # Retell AI Voice integration
│       │       ├── client.py  # Retell REST client (list agents, get agent, import numbers)
│       │       ├── provider.py# Retell verification & doctor diagnostics
│       │       ├── runtime.py # Retell bridge runner with automated Quick Tunnel
│       │       └── webhook.py # Translates Meta WhatsApp SDP offer <-> Retell WebRTC proxy
│       └── server/
│           ├── app.py         # FastAPI webhook router & WebRTC dispatcher
│           └── security.py    # X-Hub-Signature-256 HMAC verification
└── tests/
    ├── test_wavoice.py        # Core pipeline, HMAC, claim locks, tunnel, ICE
    ├── test_dograh.py         # Dograh Cloud client & workflow schemas
    ├── test_livekit.py        # LiveKit Cloud client, webhook translation, agent routing
    └── test_retell.py         # Retell AI client, WebRTC bridge negotiation, agent mapping
```

### Architectural Invariants:
1. **Provider Isolation**: All third-party platforms (Dograh, LiveKit, etc.) belong under `src/wavoice/providers/<provider_name>/` and must implement `BaseProvider` (`validate_credentials`, `setup`, `doctor`). Core networking and Meta Graph API stay in `src/wavoice/core/`.
2. **Never Break Test Suite**: Always run `uv run pytest` before and after modifying code. All tests must pass.
3. **No macOS Docker WebRTC**: Local WebRTC debugging must be done natively with Python 3.12 (`uv`), never inside Docker Desktop on macOS (Docker for Mac bridge drops UDP media packets).
4. **Safe Credential Handling**: Never log, commit, or hardcode tokens. All secrets load via `wavoice.core.config.Settings` from `.env`.

---

## 3. Intent Routing Matrix (What to do when the user asks...)

| User Prompt / Request | Exact Agent Action |
| :--- | :--- |
| **"Set up WhatsApp calling from scratch"** | Ask for Meta Token, Secret, and Gemini Key. Execute `uv run wavoice setup`. Verify using `uv run wavoice doctor`. |
| **"Connect to Retell AI"** | Prompt for `RETELL_API_KEY` and `RETELL_AGENT_ID`. Run `uv run wavoice retell setup`, then `uv run wavoice retell start`. Run `uv run wavoice retell doctor` for connectivity check. |
| **"Connect to LiveKit Cloud"** | Check for LiveKit credentials in `~/.livekit/config.yaml` or `.env`. Run `uv run wavoice livekit setup`, then `uv run wavoice livekit start`. |
| **"Route to my existing LiveKit agent"** | Launch the bridge with `--agent-name <name> --no-agent`: `uv run wavoice livekit start --agent-name <name> --no-agent`. |
| **"Connect to Dograh Studio (no-code)"** | Prompt for `DOGRAH_API_KEY`. Run `uv run wavoice dograh setup`. Meta webhooks route directly to Dograh Cloud without local tunnel. |
| **"Build custom STT + LLM + TTS pipeline"** | Reference [`examples/custom_stt_llm_tts.py`](examples/custom_stt_llm_tts.py) using `WhatsAppVoiceApp` and Pipecat's `SmallWebRTCTransport`. |
| **"Nobody answered / It's just ringing"** | **Run Diagnostic Playbook immediately** (Section 4). 90% of the time, this is an expired Meta token or a webhook pointing to a dead tunnel. |
| **"How do I deploy to production?"** | Explain: Host behind persistent domain (`--public-url https://api.yourdomain.com`), or for Dograh use cloud routing, or for LiveKit paste the 15-line webhook handler directly into backend. |

---

## 4. Diagnostic & Troubleshooting Runbook

When a call is ringing and not answered, systematically execute these checks in order:

### Check 1: Meta Access Token Validity
Meta's temporary test tokens expire every 24 hours. When expired, Meta silently drops or rejects call webhooks.
- **How to test**:
  ```bash
  uv run wavoice doctor
  ```
- **Error signal**: `wavoice.core.meta.TokenExpiredError: Meta Access Token has expired: Session has expired...`
- **Fix**: Direct user to [developers.facebook.com](https://developers.facebook.com) $\rightarrow$ WhatsApp $\rightarrow$ API Setup, generate a new token, and update `WHATSAPP_TOKEN` in `.env`.

### Check 2: Webhook Routing Priority (Tier 1 Override)
Meta routes calling webhooks in strict priority:
1. **Tier 1 (Phone Number Override)**: `POST /v21.0/{phone_number_id}` with `webhook_configuration` (**Highest Priority**).
2. **Tier 2 (WABA Subscription)**: `POST /v21.0/{waba_id}/subscribed_apps`.
3. **Tier 3 (App Level)**: Fallback.

- **Gotcha**: If Tier 1 points to an old, dead Cloudflare tunnel from a stopped session, Meta will ignore all other webhooks and calls will just ring.
- **Fix**: Check `Tier 1: Phone Override` in `wavoice doctor`. If testing LiveKit/Pipecat, make sure the local dev process is actively running. If testing Dograh, ensure Tier 1 is explicitly pointed to `https://api.dograh.com/api/v1/telephony/whatsapp/webhook`.

### Check 3: LiveKit Cloud Specific Requirements
1. **Protobuf API Version**: `AcceptWhatsAppCallRequest.whatsapp_cloud_api_version` MUST be `"23.0"` (string literal, no leading "v"). Any other version yields `ServerError: whatsapp cloud api version not supported (status=400)`.
2. **SDP Extraction**: Meta's calling webhook nests the SDP offer at `call["session"]["sdp"]` (not `call["sdp"]`).
3. **Room Agent Dispatch**: To send incoming calls directly to an agent worker without manual room dispatch, always include `req.agents.append(RoomAgentDispatch(agent_name=target_agent))`.

### Check 4: Dograh Cloud Specific Requirements
1. **Synced Phone Row**: Dograh must have the phone number registered under the telephony config (`sync_phone_numbers`).
2. **Bound Inbound Workflow**: The phone row must have `inbound_workflow_id` populated with a published workflow ID (`bind_workflow_to_phone_number`).
3. **Token Freshness on Dograh**: If Meta's token was refreshed, update the telephony configuration on Dograh Cloud (`PUT /api/v1/organizations/telephony-configs/{config_id}`) so Dograh can call Meta back to accept the call.

---

## 5. Development & Testing Commands

### Run Full Test Suite
```bash
uv run pytest
```
*Current test suite: 33 passed across `test_wavoice.py`, `test_dograh.py`, `test_livekit.py`, and `test_retell.py`.*

### Run Provider Diagnostics
```bash
# Core & Meta diagnostics
uv run wavoice doctor

# Retell AI diagnostics
uv run wavoice retell doctor

# LiveKit Cloud diagnostics
uv run wavoice livekit doctor

# Dograh Cloud diagnostics
uv run wavoice dograh doctor
```

### Launch Development Runtimes
```bash
# Mode A: Out-of-the-box Gemini 2.0 Flash Live
uv run wavoice start

# Mode B: Retell AI WebRTC Bridge
uv run wavoice retell start

# Mode C: LiveKit Cloud Bridge (bundled agent)
uv run wavoice livekit start

# Mode D: LiveKit Cloud Bridge (custom external agent)
uv run wavoice livekit start --agent-name my-agent --no-agent
```

---

## 6. Pre-Completion Checklist for AI Agents

Before marking any task complete and pushing to GitHub:
- [ ] Run `uv run pytest` and verify **all tests pass**.
- [ ] Check `git status` to ensure no unwanted files (`.env`, temporary logs, scratch files) are staged.
- [ ] Verify that any modified documentation, docstrings, and `AGENTS.md` accurately reflect current code.
- [ ] Provide clear, step-by-step next actions to the user.

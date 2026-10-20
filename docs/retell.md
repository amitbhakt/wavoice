# Retell AI WhatsApp Integration Guide

Connect Meta WhatsApp Voice Calling directly to your [Retell AI](https://retellai.com) voice agents in under 2 minutes.

---

## Overview

[Retell AI](https://retellai.com) is a leading platform for building low-latency, highly realistic conversational AI voice agents.

`WAVoice` bridges WhatsApp voice calls directly to Retell AI using native WebRTC negotiation:
1. Receives Meta's incoming WhatsApp call webhook containing the WebRTC SDP offer.
2. Initializes an agent call session via Retell's `create-web-call` API.
3. Forwards the WebRTC SDP offer to Retell's WebRTC proxy gateway.
4. Returns the negotiated SDP answer to Meta WhatsApp to establish live, bidirectional audio.
5. Automatically handles Cloudflare Quick Tunnel ingress, 3-tier webhook synchronization, and atomic call claim deduplication.

```
Caller (WhatsApp Phone)
         │ WebRTC Audio (SRTP)
         ▼
Meta Cloud Calling API
         │ Webhook (SDP Offer)
         ▼
WAVoice Retell Bridge (`wavoice retell start`)
         │ WebRTC Proxy (/v2/create-web-call)
         ▼
Retell AI WebRTC Gateway (`api.retellai.com`)
         │ Live Voice Pipeline (STT ➔ LLM ➔ TTS)
         ▼
Your Retell Voice Agent
```

---

## Prerequisites

Before starting, have these credentials ready:

1. **Retell AI Credentials**:
   - An account at [retellai.com](https://retellai.com).
   - Your **Retell API Key** (from the Retell dashboard).
   - Your **Retell Agent ID** (e.g. `agent_...` found under Agents in your dashboard).

2. **Meta Developer Credentials**:
   - Meta Developer App with the **WhatsApp** product added.
   - Meta **System User Access Token** with permissions:
     - `whatsapp_business_messaging`
     - `whatsapp_business_management`
   - WhatsApp Business Phone Number (Meta's free test number works out of the box).
   - Meta App Secret.

---

## Quickstart

### 1. Configure Environment (Optional)

You can save your credentials in a `.env` file in your project folder:

```bash
RETELL_API_KEY="key_..."
RETELL_AGENT_ID="agent_..."
WHATSAPP_TOKEN="EAA..."
WHATSAPP_APP_SECRET="your_app_secret"
```

*(If you don't create a `.env` file, the command will prompt you for them interactively).*

### 2. Start the Retell WebRTC Bridge

Run the one-command runner:

```bash
uvx wavoice retell start
# or: pip install wavoice && wavoice retell start
```

This single command:
- Auto-discovers your Meta Phone Number ID and WABA ID.
- Enables voice calling on your WhatsApp Business number.
- Spins up an automated HTTPS tunnel (via Cloudflare Quick Tunnel) for local testing.
- Registers Meta webhook overrides pointing to your bridge.
- Begins listening for incoming WhatsApp calls.

### 3. Call & Talk

Open WhatsApp on your phone, call your WhatsApp Business number, and speak directly with your Retell AI agent!

---

## Pre-Flight Diagnostics (`wavoice retell doctor`)

If you want to verify your configuration, API keys, or agent connection before launching:

```bash
uvx wavoice retell doctor
```

Output checks:
- **Retell API Key**: Verifies connectivity with `api.retellai.com`.
- **Retell Agent Verification**: Confirms your Agent ID exists and displays the agent name.
- **Meta Token & Permissions**: Verifies Graph API access and calling permissions.
- **WhatsApp Voice Calling Status**: Confirms calling is enabled on your phone number.

---

## CLI Options

```bash
# Custom local port (default: 8000)
wavoice retell start --port 8080

# Disable automated tunnel (if using your own reverse proxy)
wavoice retell start --no-tunnel

# Use a permanent public domain for staging or production
wavoice retell start --custom-url https://voice.yourdomain.com

# Disable anonymous telemetry
wavoice retell start --no-telemetry
```

---

## Production Deployment

By default, `wavoice retell start` establishes a temporary Cloudflare Quick Tunnel (`*.trycloudflare.com`) designed for rapid local testing and development.

For permanent 24/7 production deployments:
1. Deploy WAVoice behind a static reverse proxy or domain (e.g. AWS ALB, Cloudflare, Caddy, or Nginx).
2. Pass your persistent HTTPS domain via `--custom-url` or set `PUBLIC_URL` in your `.env`:
   ```bash
   wavoice retell start --custom-url https://voice.yourcompany.com
   ```
3. WAVoice will register the permanent webhook callback URL with Meta.

---

## Troubleshooting

- **Call is ringing and never answered:**
  1. Run `uvx wavoice retell doctor` to check if your Meta access token expired.
  2. Ensure the local `wavoice retell start` process is actively running in your terminal.
  3. Verify your Retell Agent ID has a valid LLM and voice configured in the Retell dashboard.
- **WebRTC audio drops or latency:**
  Ensure UDP traffic is not blocked on your network or firewall.

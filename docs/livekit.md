# LiveKit Cloud WhatsApp Integration Guide

Connect Meta WhatsApp Voice Calling directly into your [LiveKit](https://livekit.io) real-time WebRTC voice agents in under 2 minutes.

---

## Overview

LiveKit provides ultra-low latency WebRTC infrastructure and an open-source Python Agent framework (`livekit-agents`). 

`WAVoice` acts as an automated setup wizard and webhook bridge for LiveKit Cloud:
1. Discovers and verifies your WhatsApp Business Account (WABA) and phone numbers.
2. Enables WhatsApp Voice Calling on Meta Graph API.
3. Configures 3 tiers of Meta webhooks (Phone Number override, WABA subscriptions, and App events).
4. Translates Meta's WhatsApp WebRTC SDP offer into LiveKit Cloud's managed telephony connector (`AcceptWhatsAppCallRequest`).
5. Dispatches callers directly into LiveKit rooms handled by your LiveKit voice agent.

```
Caller (WhatsApp Phone)
         │ WebRTC Audio / SIP
         ▼
Meta Cloud API (v21.0 / v23.0)
         │ Webhook (SDP Offer)
         ▼
WAVoice Bridge (`wavoice livekit start` / `dev`)
         │ AcceptWhatsAppCallRequest (SDP translation)
         ▼
LiveKit Cloud Telephony Server (Egress/Ingress)
         │ WebRTC Room
         ▼
LiveKit Voice Agent (`wavoice-agent` or custom agent)
```

---

## Prerequisites

1. **Meta Developer Account**:
   - Meta App with WhatsApp product added.
   - System User Access Token with `whatsapp_business_messaging` and `whatsapp_business_management`.
   - Verified WhatsApp Business phone number (Meta's free test number works).
2. **LiveKit Cloud Account**:
   - Free account at [cloud.livekit.io](https://cloud.livekit.io).
   - Project URL (e.g. `wss://<your-project>.livekit.cloud`).
   - LiveKit API Key & API Secret.

---

## Quickstart

### 1. Interactive Setup Wizard

Run:
```bash
uvx wavoice livekit setup
# or: pip install wavoice && wavoice livekit setup
```

`WAVoice` will:
- Auto-detect existing LiveKit credentials from `~/.livekit/config.yaml` or prompt you to paste the 1-click `.env` snippet from your LiveKit Cloud dashboard.
- Prompt for your Meta token and secret (if not already in `.env`).
- Auto-discover your WABA ID and Phone Number ID.
- Enable voice calling on Meta.
- Save everything into `.env`.

### 2. Start the Dev Bridge & Test Agent

```bash
wavoice livekit start
# or: wavoice livekit dev
```

This launches:
- An automated Cloudflare Quick Tunnel (`trycloudflare.com`) for instant local testing.
- The LiveKit webhook bridge on port `8000`.
- The bundled test voice agent (`wavoice-agent`) using Gemini / LiveKit Agents.

Open WhatsApp, call your business phone number, and speak directly to your LiveKit agent!

---

## Routing to Your Own Custom LiveKit Agent

If you already have a voice agent deployed in LiveKit Cloud or running on another machine:

### Option A: Deployed in LiveKit Cloud
Run the bridge pointing to your cloud agent's registered name without starting the bundled local worker:

```bash
wavoice livekit dev --agent-name my-cloud-agent --no-agent
```

### Option B: Local Custom Agent Worker
Run your own agent script in one terminal:
```bash
python my_custom_agent.py dev
```
And in another terminal, run WAVoice to bridge WhatsApp calls to it:
```bash
wavoice livekit dev --agent-name my-custom-agent --no-agent
```

---

## Pre-Flight Diagnostics

To check your LiveKit credentials, project connectivity, and WhatsApp voice calling status at any time:

```bash
wavoice livekit doctor
```

Example Output:
```text
╭───────────────────────────────────╮
│ WAVoice LiveKit Cloud Diagnostics │
╰───────────────────────────────────╯
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Check                        ┃ Status     ┃ Details                      ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Livekit Credentials          │ PASS       │ Configured in .env           │
│ Livekit Cloud Connectivity   │ PASS       │ Project reachable            │
│ Meta Credentials             │ PASS       │ Token & Phone ID configured  │
│ Whatsapp Voice Calling API   │ PASS       │ Voice calling is ENABLED     │
└──────────────────────────────┴────────────┴──────────────────────────────┘
```

---

## Production Deployment

### 1. Persistent Public Ingress
Cloudflare Quick Tunnels (`trycloudflare.com`) are ephemeral and intended for development. For staging or production, host behind a persistent domain (e.g., Caddy, Nginx, AWS ALB, Cloudflare Tunnel with custom domain):

```bash
wavoice livekit dev --public-url https://whatsapp.yourdomain.com --no-tunnel
```

### 2. LiveKit Cloud Webhook Handler (No CLI Bridge)
If you prefer not running WAVoice's bridge process in production, you can embed the ~15-line webhook handler directly into your existing FastAPI/Express/Go backend:

```python
from livekit import api

lk_client = api.LiveKitAPI(url=LIVEKIT_URL, api_key=LIVEKIT_API_KEY, api_secret=LIVEKIT_API_SECRET)

@app.post("/webhook")
async def handle_whatsapp_webhook(request: Request):
    payload = await request.json()
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            call = change.get("value", {}).get("call", {})
            if call and call.get("status") == "ringing":
                req = api.AcceptWhatsAppCallRequest(
                    phone_number_id=change["value"]["metadata"]["phone_number_id"],
                    call_id=call["id"],
                    whatsapp_cloud_api_version="23.0",
                    sdp=call["session"]["sdp"],
                )
                req.agents.append(api.RoomAgentDispatch(agent_name="my-prod-agent"))
                answer = await lk_client.telephony.accept_whatsapp_call(req)
                return Response(content=answer.sdp, media_type="application/sdp")
    return Response(status_code=200)
```

---

## Viewing Logs & Call Analytics

- **Real-Time Audio & Transcripts**: Go to **LiveKit Cloud Dashboard $\rightarrow$ Agents $\rightarrow$ `<agent_name>` $\rightarrow$ Console** during an active call.
- **Past Sessions & Quality**: Go to **LiveKit Cloud Dashboard $\rightarrow$ Sessions / Insights** to inspect latency, jitter, audio packet loss, and full transcripts.

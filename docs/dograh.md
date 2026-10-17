# Dograh Cloud WhatsApp Integration Guide

Connect Meta WhatsApp Voice Calling to your visual, no-code voice agents built in [Dograh](https://dograh.com) in under 30 seconds.

---

## Overview

[Dograh](https://dograh.com) is a visual, no-code voice studio for building production-grade conversational AI agents with integrated telephony, prompt engineering, tools, and analytics.

`WAVoice` completely automates the integration between your Meta Developer App and Dograh Cloud:
1. Validates your Meta token and auto-discovers your Phone Number ID and WABA ID.
2. Auto-enables WhatsApp Voice Calling on Meta (`calling.status = "ENABLED"`).
3. Registers the WhatsApp Telephony Configuration in Dograh Cloud (`api.dograh.com`).
4. Syncs your WhatsApp phone numbers directly into your Dograh workspace.
5. Deploys and publishes a sample conversational voice agent workflow in Dograh.
6. Binds your WhatsApp number to the new agent workflow.
7. Overrides Meta's webhooks to route incoming calls directly to Dograh Cloud's managed infrastructure.

```
Caller (WhatsApp Phone)
         │ WebRTC Audio / SIP
         ▼
Meta Cloud API (v21.0+)
         │ Managed Webhook Routing
         ▼
Dograh Cloud Infrastructure (`api.dograh.com`)
         │ Managed Voice Pipeline
         ▼
Visual Agent Workflow (Dograh Studio)
```

> **Zero local tunnels required!** Because Dograh Cloud hosts the managed telephony infrastructure, once you run setup, Meta routes calls directly to Dograh's servers. You don't need any local daemon or server running on your machine.

---

## Prerequisites

1. **Dograh Account**:
   - Create an account at [app.dograh.com](https://app.dograh.com).
   - Generate an API Key under **Settings $\rightarrow$ API Keys** (`app.dograh.com/api-keys`).
2. **Meta Developer Account**:
   - Meta App with WhatsApp product added.
   - System User Access Token with `whatsapp_business_messaging` and `whatsapp_business_management`.
   - Verified WhatsApp Business phone number (Meta's free test number works).

---

## Quickstart

Run one single command:

```bash
uvx wavoice dograh setup
# or: pip install wavoice && wavoice dograh setup
```

The interactive wizard will prompt for:
1. `DOGRAH_API_KEY`: Your Dograh API Key.
2. `WHATSAPP_TOKEN`: Meta System User access token.
3. `WHATSAPP_APP_SECRET`: Meta App Secret.

In under 30 seconds, `WAVoice` validates all credentials, connects Meta to Dograh, configures the webhooks, and deploys a sample agent.

---

## Dial & Talk

Pick up your phone, open WhatsApp, and call your business number. The newly deployed Dograh voice agent will answer immediately!

---

## Customizing Your Agent in Dograh Studio

Once setup is complete:
1. Log in to [app.dograh.com](https://app.dograh.com).
2. Open the newly created **WhatsApp Voice Agent** workflow.
3. Visually customize:
   - System prompt & persona.
   - Voice models (Cartesia, ElevenLabs, OpenAI, Deepgram, etc.).
   - Tool calling, webhooks, and CRM integrations.
   - Knowledge base & RAG documents.
4. Click **Publish** — updates take effect on live WhatsApp calls instantly with zero downtime.

---

## Pre-Flight Diagnostics

To check your Meta credentials and WhatsApp calling status:

```bash
uv run wavoice doctor
```

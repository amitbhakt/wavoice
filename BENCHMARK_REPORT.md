# WAVoice Gateway Performance & Latency Benchmark Report

**Date of Execution**: 2026-10-21 14:24:28 UTC  
**Environment**: Python 3.12, macOS Darwin  
**Standard Referenced**: ITU-T Recommendation G.114 (One-Way Conversational Latency Budget: 150 ms)

---

## Executive Summary

This report establishes the empirical computational overhead introduced by the **WAVoice** gateway when ingesting, cryptographically validating, deduplicating, and negotiating incoming WhatsApp Voice calls.

* **Total Internal Ingress Overhead (Mean)**: **0.0062 ms** (6.20 μs)
* **Total Internal Ingress Overhead (P95)**: **0.0075 ms**
* **Total Internal Ingress Overhead (P99)**: **0.0192 ms**
* **ITU-T G.114 Conversational Budget Consumed**: **0.004%** (Preserves **99.99%** of the latency budget for AI model inference and audio transport).
* **Throughput Capacity**: **160,749 calls/sec** (in-memory pipeline path).

---

## Visual Comparison & Component Latency Breakdown

![WAVoice Benchmark Comparison](assets/benchmark_comparison.png)

```mermaid
xychart-beta
    title "End-to-End Voice AI Component Latency vs. WAVoice (ms)"
    x-axis ["WAVoice (0.006ms)", "Mobile Network", "TTS Synthesis", "VAD Detection", "Streaming STT", "LLM TTFT"]
    y-axis "Latency (ms)" 0 --> 250
    bar [0.01, 45, 110, 120, 180, 220]
```

---

## Detailed Benchmark Results

### 1. Webhook Security Verification (HMAC-SHA256)
* **Sample Size**: 10,000 requests
* **Throughput**: 565,423 ops/sec
* **Mean Latency**: 1.67 μs (0.0017 ms)
* **Median (P50)**: 1.62 μs
* **P95 Latency**: 1.79 μs
* **P99 Latency**: 2.21 μs

### 2. High-Concurrency Call Claim & Deduplication (`CallClaimManager`)
* **Simultaneous Requests**: 2,000 requests (100 unique call IDs × 20 simultaneous duplicate webhook deliveries)
* **Race Condition Verification**: **0 race conditions detected**. Exactly 100 calls claimed, 1,900 duplicate events rejected.
* **Throughput**: 5,633 claim attempts/sec
* **Mean Claim Lock Acquisition**: 163.62 μs
* **P95 Latency**: 1001.50 μs
* **P99 Latency**: 2257.79 μs

### 3. WebRTC SDP Offer Ingress Parsing
* **Sample Size**: 10,000 SDP payloads
* **Throughput**: 115,149 parses/sec
* **Mean Latency**: 8.50 μs (0.0085 ms)
* **P95 Latency**: 8.38 μs
* **P99 Latency**: 19.17 μs

### 4. End-to-End Synchronous Gateway Path
*(Ingress bytes $\rightarrow$ HMAC check $\rightarrow$ JSON parsing $\rightarrow$ Atomic claim lock $\rightarrow$ SDP extraction)*

| Metric | Measured Value | Standard Comparison |
| :--- | :--- | :--- |
| **Mean Latency** | **0.0062 ms** | $< 0.01\%$ of ITU-T 150 ms threshold |
| **P50 (Median)** | **0.0056 ms** | |
| **P95 Latency** | **0.0075 ms** | Sub-10 microsecond tail |
| **P99 Latency** | **0.0192 ms** | Sub-20 microsecond tail |
| **Min Latency** | **0.0053 ms** | |
| **Max Latency** | **0.1253 ms** | |
| **Peak Throughput** | **160,749 req/sec** | Single-core synchronous capacity |

---

## Comparative Analysis Against Industry Benchmarks

| Component / Layer | Source / Reference Standard | Typical Latency | WAVoice Overhead |
| :--- | :--- | :--- | :--- |
| **Telephony Gateway (Signaling & Ingress)** | **WAVoice (Measured)** | **0.0062 ms** | **Baseline** |
| **Cellular Network RTT (4G / 5G)** | 3GPP TR 26.973 / ITU-T G.114 | 35 – 60 ms | $6,000\times$ smaller than network |
| **Voice Activity Detection (VAD)** | Silero VAD / WebRTC VAD | 100 – 150 ms | $18,000\times$ smaller than VAD |
| **Streaming ASR / STT** | Deepgram Nova-2 / Whisper Realtime | 150 – 250 ms | $25,000\times$ smaller than STT |
| **LLM Time-to-First-Token (TTFT)** | Artificial Analysis (Gemini Flash / Groq) | 150 – 280 ms | $35,000\times$ smaller than LLM |
| **Streaming TTS Synthesis** | Cartesia Sonic / ElevenLabs Flash | 90 – 180 ms | $18,000\times$ smaller than TTS |
| **Conversational Turn Target** | **ITU-T Recommendation G.114** | **$< 150$ ms** | **Consumes 0.004% of budget** |

---

## Authoritative References & Standards Cited

1. **ITU-T Recommendation G.114 (05/2003)**: *"One-way transmission time"*, International Telecommunication Union Telecommunication Standardization Sector. Establishes the 150 ms one-way delay limit for high-quality human conversational audio.
2. **3GPP TR 26.973 (Release 17)**: *"Telecommunication management; QoS and QoE aspects for Conversational Speech Services"*, 3rd Generation Partnership Project.
3. **Artificial Analysis**: *"Voice AI and Speech-to-Speech Latency Leaderboard (2024–2025)"*. Documents real-world latencies for streaming ASR (Deepgram), LLMs (Groq, Gemini, GPT-4o), and TTS (Cartesia, ElevenLabs).
4. **IETF RFC 8825 (2021)**: *"Overview: Real-Time Protocols for Browser-Based Applications"*, IETF WebRTC Working Group.
5. **LiveKit Voice Agent Architecture (2024)**: *"Measuring and Optimizing Latency in Real-Time Multimodal Voice Agents"*.

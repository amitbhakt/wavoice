"""Generate publication-grade benchmark visualization for WAVoice.

Compares:
1. End-to-end Voice AI Latency Budget (ITU-T G.114 vs Network vs Speech Models vs WAVoice).
2. WAVoice Internal Microsecond Latencies (HMAC vs Claim Lock vs SDP Parsing vs E2E Gateway).
"""

import matplotlib.pyplot as plt
import numpy as np

# Set style
plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5), dpi=300)

# --- Subplot 1: End-to-End Conversational Voice AI Latency Stack (ms) ---
categories = [
    "WAVoice Ingress\n(Measured: 0.006 ms)",
    "4G/5G Network RTT\n(3GPP TR 26.973)",
    "Voice Activity Det.\n(Silero VAD)",
    "Streaming STT\n(Deepgram Nova-2)",
    "LLM TTFT\n(Gemini 2.0 Flash)",
    "Streaming TTS\n(Cartesia / ElevenLabs)",
]
# Typical latency values (ms) from published literature & Artificial Analysis
latencies = [0.006, 45.0, 120.0, 180.0, 220.0, 110.0]
colors = ["#22c55e", "#3b82f6", "#6366f1", "#8b5cf6", "#ec4899", "#f97316"]

bars1 = ax1.barh(categories, latencies, color=colors, height=0.55, edgecolor="none")
ax1.set_xscale("log")
ax1.set_xlabel("Latency in Milliseconds (Log Scale)", fontsize=11, fontweight="bold")
ax1.set_title("Voice AI Pipeline Latency Stack vs. WAVoice", fontsize=12, fontweight="bold", pad=12)
ax1.axvline(150, color="#ef4444", linestyle="--", linewidth=1.5, label="ITU-T G.114 Target (<150 ms)")
ax1.axvline(400, color="#b91c1c", linestyle=":", linewidth=1.5, label="ITU-T G.114 Acceptable Limit (400 ms)")

for bar, val in zip(bars1, latencies):
    if val < 0.1:
        text = f"{val:.3f} ms"
    else:
        text = f"{val:.0f} ms"
    ax1.text(val * 1.2, bar.get_y() + bar.get_height() / 2, text, va="center", ha="left", fontsize=9, fontweight="bold")

ax1.set_xlim(0.001, 800)
ax1.legend(loc="lower right", frameon=True, fontsize=9)

# --- Subplot 2: WAVoice Internal Ingress Micro-benchmarks (Microseconds) ---
subsystems = [
    "HMAC-SHA256\nVerify",
    "SDP Ingress\nParsing",
    "Concurrent Claim\nLocking (P95)",
    "Full Gateway\nE2E Path",
]
# Latencies in microseconds
micro_vals = [1.67, 8.50, 163.62, 6.20]
colors2 = ["#0ea5e9", "#06b6d4", "#14b8a6", "#10b981"]

bars2 = ax2.bar(subsystems, micro_vals, color=colors2, width=0.5, edgecolor="none")
ax2.set_yscale("log")
ax2.set_ylabel("Processing Latency in Microseconds (Log Scale)", fontsize=11, fontweight="bold")
ax2.set_title("WAVoice Subsystem Micro-benchmarks (μs)", fontsize=12, fontweight="bold", pad=12)

for bar, val in zip(bars2, micro_vals):
    ax2.text(
        bar.get_x() + bar.get_width() / 2,
        val * 1.3,
        f"{val:.2f} μs\n({val/1000:.4f} ms)",
        ha="center",
        va="bottom",
        fontsize=8.5,
        fontweight="bold",
    )

ax2.set_ylim(0.5, 500)

plt.tight_layout()
output_path = "assets/benchmark_comparison.png"
plt.savefig(output_path, bbox_inches="tight")
print(f"Chart successfully saved to: {output_path}")

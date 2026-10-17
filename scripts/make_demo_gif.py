"""Generate a high-resolution, terminal-rendered demo GIF for WAVoice README."""

import os
import subprocess
from PIL import Image, ImageDraw, ImageFont

WIDTH = 900
HEIGHT = 580
BG_COLOR = (13, 17, 23)        # GitHub Dark Dimmed
HEADER_COLOR = (22, 27, 34)    # Terminal top bar
BORDER_COLOR = (48, 54, 61)
TEXT_WHITE = (230, 237, 243)
TEXT_DIM = (139, 148, 158)
TEXT_GREEN = (63, 185, 80)
TEXT_CYAN = (88, 166, 255)
TEXT_YELLOW = (210, 153, 34)
TEXT_MAGENTA = (188, 140, 255)

FONT_PATH = "/System/Library/Fonts/Menlo.ttc"
FONT_SIZE = 14
LINE_HEIGHT = 22

try:
    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    bold_font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
except Exception:
    font = ImageFont.load_default()
    bold_font = font


def draw_window_frame(draw: ImageDraw.ImageDraw, title: str = "wavoice init — 90s Setup"):
    # Window background
    draw.rectangle([(0, 0), (WIDTH, HEIGHT)], fill=BG_COLOR)
    # Header bar
    draw.rectangle([(0, 0), (WIDTH, 36)], fill=HEADER_COLOR)
    draw.line([(0, 36), (WIDTH, 36)], fill=BORDER_COLOR, width=1)

    # Window control dots
    draw.ellipse([(14, 12), (26, 24)], fill=(255, 95, 86))    # Red
    draw.ellipse([(34, 12), (46, 24)], fill=(255, 189, 46))   # Yellow
    draw.ellipse([(54, 12), (66, 24)], fill=(39, 201, 63))    # Green

    # Window title
    draw.text((WIDTH // 2 - 90, 10), title, font=font, fill=TEXT_DIM)


def render_frame(lines: list[list[tuple[str, tuple]]]) -> Image.Image:
    img = Image.new("RGB", (WIDTH, HEIGHT), color=BG_COLOR)
    draw = ImageDraw.Draw(img)
    draw_window_frame(draw)

    y = 52
    for line_parts in lines:
        x = 24
        for text, color in line_parts:
            draw.text((x, y), text, font=font, fill=color)
            bbox = font.getbbox(text)
            text_width = bbox[2] - bbox[0]
            x += text_width
        y += LINE_HEIGHT
    return img


def main():
    os.makedirs("assets", exist_ok=True)
    frames_dir = "/tmp/wavoice_frames"
    os.makedirs(frames_dir, exist_ok=True)

    # Script sequence of events
    timeline = []

    # Scene 1: Command typing
    base = []
    timeline.append((base + [[("$ ", TEXT_GREEN), ("uvx wavoice init", TEXT_WHITE)]], 10))

    # Scene 2: Banner display
    banner = [
        [("$ ", TEXT_GREEN), ("uvx wavoice init", TEXT_WHITE)],
        [("╦ ╦╔═╗╦  ╦╔═╗╦╔═╗╔═╗   WAVoice v0.2.0", TEXT_CYAN)],
        [("║║║╠═╣╚╗╔╝║ ║║║  ║╣    One-command WhatsApp Voice AI runtime", TEXT_CYAN)],
        [("╚╩╝╩ ╩ ╚╝ ╚═╝╩╚═╝╚═╝", TEXT_CYAN)],
        [("─" * 68, TEXT_DIM)],
    ]
    timeline.append((banner, 8))

    # Scene 3: Inputs
    inputs = banner + [
        [("1. Meta System User Access Token: ", TEXT_WHITE), ("EAAN3A...ZDZD", TEXT_YELLOW)],
        [("   Validating token with Meta Graph API... ", TEXT_DIM), ("✓ Active & verified!", TEXT_GREEN)],
        [("2. Meta App Secret: ", TEXT_WHITE), ("••••••••••••••••••••••••••••••••", TEXT_DIM)],
        [("3. Gemini API Key: ", TEXT_WHITE), ("••••••••••••••••••••••••••••••••", TEXT_DIM)],
        [("", TEXT_WHITE)],
        [("🚀 Initiating zero-friction setup...", TEXT_YELLOW)],
    ]
    timeline.append((inputs, 12))

    # Scene 4: Auto-discovery
    discovery = inputs + [
        [("1/4 Auto-discovering WhatsApp account... ", TEXT_CYAN), ("✓ WABA: 2349713195497707", TEXT_GREEN)],
        [("    Verified Number: ", TEXT_DIM), ("+1 555-188-2279 (Test Number)", TEXT_WHITE)],
        [("2/4 Checking WhatsApp Voice Calling... ", TEXT_CYAN), ("✓ ENABLED", TEXT_GREEN)],
        [("3/4 Starting Cloudflare Quick Tunnel... ", TEXT_CYAN), ("✓ https://wavoice.trycloudflare.com", TEXT_GREEN)],
        [("4/4 Syncing 3-tier Meta webhooks... ", TEXT_CYAN), ("✓ Challenge Verified (200 OK)", TEXT_GREEN)],
        [("", TEXT_WHITE)],
        [("🎉 WhatsApp Voice Server is live and listening!", TEXT_GREEN)],
    ]
    timeline.append((discovery, 16))

    # Scene 5: Incoming Live WhatsApp Call
    live_call = discovery + [
        [("─" * 68, TEXT_DIM)],
        [("[22:15:02] ", TEXT_DIM), ("📞 INBOUND CALL: ", TEXT_YELLOW), ("wacid.94a7e2... from +1 555-0192", TEXT_WHITE)],
        [("[22:15:02] ", TEXT_DIM), ("⚡ WebRTC Bridge: ", TEXT_CYAN), ("Answered in 240ms (SRTP Connected)", TEXT_GREEN)],
        [("[22:15:03] ", TEXT_DIM), ("🤖 AI Agent: ", TEXT_MAGENTA), ('"Hello! You have successfully connected WhatsApp AI calling."', TEXT_WHITE)],
        [("[22:15:05] ", TEXT_DIM), ("👤 Caller: ", TEXT_CYAN), ('"Hey! Can you hear me clearly?"', TEXT_WHITE)],
        [("[22:15:06] ", TEXT_DIM), ("🤖 AI Agent: ", TEXT_MAGENTA), ('"Yes! I hear you loud and clear. Your setup is 100% working."', TEXT_GREEN)],
    ]
    timeline.append((live_call, 25))

    frame_idx = 0
    for scene_lines, duration_ticks in timeline:
        img = render_frame(scene_lines)
        for _ in range(duration_ticks):
            img.save(f"{frames_dir}/frame_{frame_idx:04d}.png")
            frame_idx += 1

    print(f"Generated {frame_idx} frames. Compiling with ffmpeg...")
    gif_path = "assets/demo.gif"
    
    # Use ffmpeg with two-pass palettegen for crisp small GIF
    cmd = (
        f'ffmpeg -y -framerate 8 -i "{frames_dir}/frame_%04d.png" '
        f'-vf "fps=8,split[s0][s1];[s0]palettegen=max_colors=64:reserve_transparent=0[p];[s1][p]paletteuse=dither=bayer:bayer_scale=3" '
        f'"{gif_path}"'
    )
    subprocess.run(cmd, shell=True, check=True)
    print(f"✓ Successfully generated {gif_path} ({os.path.getsize(gif_path) / 1024:.1f} KB)")


if __name__ == "__main__":
    main()

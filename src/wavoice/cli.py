"""CLI entry point for wavoice (init, doctor, start)."""

import asyncio
from pathlib import Path
import secrets
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from wavoice.core.config import settings
from wavoice.core.meta import MetaGraphClient

cli = typer.Typer(
    name="wavoice",
    help="One-command WhatsApp Voice AI setup with Pipecat.",
    add_completion=False,
)
console = Console()

BANNER_HEADER = """
[bold cyan]╦ ╦╔═╗╦  ╦╔═╗╦╔═╗╔═╗[/bold cyan]   [bold green]WAVoice[/bold green] [dim]v0.1.0[/dim]
[bold cyan]║║║╠═╣╚╗╔╝║ ║║║  ║╣ [/bold cyan]   [dim]One-command WhatsApp Voice AI runtime[/dim]
[bold cyan]╚╩╝╩ ╩ ╚╝ ╚═╝╩╚═╝╚═╝[/bold cyan]
"""

CREDITS_FOOTER = Panel.fit(
    "[bold white]Built with ❤️ by [cyan]@amitbhakt[/cyan][/bold white] • [dim]https://github.com/amitbhakt/wavoice[/dim]",
    border_style="dim",
)


@cli.command()
def init(
    launch: bool = typer.Option(False, "--launch", "-l", help="Automatically start the server after setup"),
    no_telemetry: bool = typer.Option(False, "--no-telemetry", help="Opt out of anonymous usage telemetry"),
):
    """Interactive wizard: input credentials, auto-discover IDs, configure Meta, and launch."""
    console.print(BANNER_HEADER)
    console.print(
        Panel.fit(
            "[bold green]WhatsApp Voice AI Setup Wizard[/bold green]\n"
            "Enter your Meta & AI credentials below to configure everything automatically.",
            border_style="green",
        )
    )

    env_path = Path(".env")
    
    # Loop to ensure token is valid and not expired
    waba_id = settings.whatsapp_waba_id or ""
    phone_id = settings.whatsapp_phone_number_id or ""

    while True:
        existing_token = token if 'token' in locals() else settings.whatsapp_token
        if existing_token:
            masked_token = f"{existing_token[:6]}...{existing_token[-4:]}"
            console.print(f"[dim]Current Token: {masked_token}[/dim]")
            token_input = typer.prompt("1. Meta System User Access Token (paste new value, or press Enter to keep current)", default="", show_default=False, hide_input=False)
            token = token_input.strip() if token_input.strip() else existing_token
        else:
            token = typer.prompt("1. Meta System User Access Token", hide_input=False).strip()

        if not token:
            console.print("[red]A Meta System User Access Token is required.[/red]")
            continue

        # Inspect token health
        console.print("[cyan]Validating token with Meta Graph API...[/cyan]")
        async def _check_token():
            client = MetaGraphClient(token)
            try:
                info = await client.inspect_token()
                return info
            finally:
                await client.close()

        try:
            token_info = asyncio.run(_check_token())
            if not token_info or token_info.get("error"):
                err_msg = token_info.get("error", "Invalid token")
                if "expire" in str(err_msg).lower():
                    console.print("[bold red]❌ Token expired![/bold red] [yellow]Your Meta System User Access Token has expired.[/yellow]")
                elif "malformed" in str(err_msg).lower():
                    console.print("[bold red]❌ Token malformed![/bold red] [yellow]The access token format is invalid (pasted multiple times or has extra spaces).[/yellow]")
                else:
                    console.print(f"[bold red]❌ Token invalid:[/bold red] {err_msg}")
                console.print("[yellow]Please enter a valid, active Meta System User Access Token.[/yellow]\n")
                token = ""
                continue
            console.print("[green]✓ Token is valid and active![/green]")
            break
        except Exception as e:
            err_str = str(e).lower()
            if "expire" in err_str:
                console.print("[bold red]❌ Token expired![/bold red] [yellow]Your Meta System User Access Token has expired.[/yellow]")
            elif "malformed" in err_str:
                console.print("[bold red]❌ Token malformed![/bold red] [yellow]The access token format is invalid.[/yellow]")
            else:
                console.print(f"[bold red]❌ Token verification error:[/bold red] {e}")
            console.print("[yellow]Please enter a valid, active Meta System User Access Token.[/yellow]\n")
            token = ""
            continue

    existing_secret = settings.whatsapp_app_secret
    if existing_secret:
        masked_secret = f"{existing_secret[:4]}...{existing_secret[-2:]}"
        console.print(f"[dim]Current App Secret: {masked_secret}[/dim]")
        secret_input = typer.prompt("2. Meta App Secret (paste new value, or press Enter to keep current)", default="", show_default=False, hide_input=False)
        app_secret = secret_input.strip() if secret_input.strip() else existing_secret
    else:
        app_secret = typer.prompt("2. Meta App Secret", hide_input=False).strip()

    existing_gemini = settings.gemini_api_key
    if existing_gemini:
        masked_gemini = f"{existing_gemini[:4]}...{existing_gemini[-4:]}"
        console.print(f"[dim]Current Gemini Key: {masked_gemini}[/dim]")
        gemini_input = typer.prompt("3. Google Gemini API Key (paste new value, or press Enter to keep current)", default="", show_default=False, hide_input=False)
        gemini_key = gemini_input.strip() if gemini_input.strip() else existing_gemini
    else:
        gemini_key = typer.prompt("3. Google Gemini API Key", hide_input=False).strip()

    # Auto-discover WABA ID and Phone Number ID using the validated token
    console.print("\n[cyan]Auto-discovering your WhatsApp account details via Meta Graph API...[/cyan]")

    async def _discover_and_enable():
        client = MetaGraphClient(token)
        try:
            disc_waba = await client.discover_waba_id()
            disc_phone = await client.discover_phone_number_id(disc_waba) if disc_waba else None
            phone_info = {}
            calling_enabled = False
            if disc_phone:
                try:
                    phone_info = await client.verify_phone_number(disc_phone)
                    calling_settings = await client.get_calling_settings(disc_phone)
                    if calling_settings.get("status") != "ENABLED":
                        calling_enabled = await client.enable_voice_calling(disc_phone)
                    else:
                        calling_enabled = True
                except Exception as err:
                    logger.debug(f"Calling settings error: {err}")
            return disc_waba, disc_phone, phone_info, calling_enabled
        finally:
            await client.close()

    try:
        disc_waba, disc_phone, phone_info, calling_enabled = asyncio.run(_discover_and_enable())
        if disc_waba:
            waba_id = disc_waba
            console.print(f"[green]✓ Found WhatsApp Business Account (WABA ID):[/green] {waba_id}")
        if disc_phone:
            phone_id = disc_phone
            display = phone_info.get("display_phone_number", phone_id)
            name = phone_info.get("verified_name", "Verified")
            console.print(f"[green]✓ Found Phone Number:[/green] {display} ({name}) [dim]ID: {phone_id}[/dim]")
        if calling_enabled:
            console.print("[green]✓ WhatsApp Voice Calling is ENABLED on this number[/green]")
    except Exception as e:
        console.print(f"[yellow]Auto-discovery warning: {e}[/yellow]")

    if not phone_id:
        phone_id = typer.prompt("Phone Number ID (could not auto-discover)", default="")
    if not waba_id:
        waba_id = typer.prompt("WABA ID (optional)", default="")

    # Telemetry is default on; only disabled if user explicitly runs with --no-telemetry or set WAVOICE_TELEMETRY=false
    telemetry_enabled = False if no_telemetry else settings.telemetry_enabled

    verify_token = settings.whatsapp_verify_token or secrets.token_hex(16)
    env_content = f"""# Generated by WAVoice init
WHATSAPP_TOKEN={token}
WHATSAPP_PHONE_NUMBER_ID={phone_id}
WHATSAPP_WABA_ID={waba_id}
WHATSAPP_APP_SECRET={app_secret}
GEMINI_API_KEY={gemini_key}
WHATSAPP_WEBHOOK_VERIFY_TOKEN={verify_token}
WAVOICE_TELEMETRY={'true' if telemetry_enabled else 'false'}
"""
    env_path.write_text(env_content, encoding="utf-8")
    console.print("\n[bold green]✓ Configuration saved to .env![/bold green]")
    from wavoice.core.telemetry import track_event
    track_event("init_completed", {"telemetry": telemetry_enabled})

    # Check if user wants to start right away
    console.print()
    console.print(CREDITS_FOOTER)
    console.print()
    should_start = launch or typer.confirm("Do you want to start the WAVoice AI server now?", default=True)
    if should_start:
        console.print("\n[bold green]Starting WAVoice...[/bold green]")
        # Reload settings in memory with the newly saved env
        from wavoice.core.config import Settings
        from wavoice.sdk import WhatsAppVoiceApp
        app = WhatsAppVoiceApp(config=Settings())
        app.run(tunnel=True, port=settings.port)
    else:
        console.print("\nRun [cyan]wavoice start[/cyan] whenever you are ready to launch!")


@cli.command()
def doctor():
    """Run pre-flight diagnostics on your Meta credentials and voice calling setup."""
    console.print(BANNER_HEADER)
    console.print(Panel.fit("[bold cyan]WAVoice Pre-Flight Diagnostics[/bold cyan]", border_style="cyan"))

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Check", style="dim", width=30)
    table.add_column("Status", width=12)
    table.add_column("Details")

    # 1. Config presence
    has_token = bool(settings.whatsapp_token)
    has_phone = bool(settings.whatsapp_phone_number_id)

    if has_token and has_phone:
        table.add_row("Meta Credentials", "[green]PASS[/green]", "Token & Phone Number ID configured")
    else:
        table.add_row("Meta Credentials", "[red]FAIL[/red]", "Run 'wavoice init' to configure .env")

    # 2. Live Meta API test & token diagnostics
    if has_token and has_phone:
        async def _test_meta():
            client = MetaGraphClient(settings.whatsapp_token)
            results = {}
            try:
                # Phone verification
                info = await client.verify_phone_number(settings.whatsapp_phone_number_id)
                display = info.get("display_phone_number", "Unknown")
                name = info.get("verified_name", "Verified")
                results["phone"] = (True, f"Verified number: {display} ({name})")

                # Inspect token scopes
                token_data = await client.inspect_token()
                if "scopes" in token_data:
                    scopes = ", ".join(token_data.get("scopes", []))
                    results["token"] = (True, f"Scopes: {scopes}")
                elif "is_valid" in token_data:
                    results["token"] = (token_data.get("is_valid", False), "Token valid (System User)")
                else:
                    results["token"] = (True, "System User token active")

                # Voice Calling settings inspection & auto-enable
                calling_settings = await client.get_calling_settings(settings.whatsapp_phone_number_id)
                status = calling_settings.get("status")
                if status == "ENABLED":
                    results["calling"] = (True, "Voice calling is ENABLED")
                else:
                    # Attempt to enable it automatically via API!
                    enabled = await client.enable_voice_calling(settings.whatsapp_phone_number_id)
                    if enabled:
                        results["calling"] = (True, "Voice calling auto-enabled via Graph API!")
                    else:
                        results["calling"] = (False, f"Status: {status or 'DISABLED'}. Enable in WhatsApp Manager -> Call settings")

                # 3-Tier Webhook diagnostics
                webhook_diag = await client.get_webhook_diagnostics(
                    phone_number_id=settings.whatsapp_phone_number_id,
                    waba_id=settings.whatsapp_waba_id,
                    app_secret=settings.whatsapp_app_secret,
                )
                results["webhooks"] = (True, webhook_diag)
            except Exception as e:
                results["phone"] = (False, str(e))
            finally:
                await client.close()
            return results

        diag = asyncio.run(_test_meta())
        if "phone" in diag:
            ok, det = diag["phone"]
            table.add_row("Phone Number Reachability", "[green]PASS[/green]" if ok else "[red]FAIL[/red]", det)
        if "token" in diag:
            ok, det = diag["token"]
            table.add_row("Token Scopes & Permissions", "[green]PASS[/green]" if ok else "[yellow]WARN[/yellow]", det)
        if "calling" in diag:
            ok, det = diag["calling"]
            table.add_row("WhatsApp Voice Calling API", "[green]PASS[/green]" if ok else "[red]FAIL[/red]", det)

        # 3-Tier Webhook Status
        if "webhooks" in diag:
            ok, wh = diag["webhooks"]
            p_sub = wh.get("phone_level") or "Not set"
            w_sub = ", ".join(wh.get("waba_level") or []) or "Not set"
            a_sub = ", ".join(wh.get("app_level") or []) or "Not set"
            table.add_row("Tier 1: Phone Override", "[green]ACTIVE[/green]" if wh.get("phone_level") else "[yellow]NONE[/yellow]", f"{p_sub}")
            table.add_row("Tier 2: WABA Subscription", "[green]ACTIVE[/green]" if wh.get("waba_level") else "[yellow]NONE[/yellow]", f"{w_sub}")
            table.add_row("Tier 3: App Subscriptions", "[green]ACTIVE[/green]" if wh.get("app_level") else "[yellow]NONE[/yellow]", f"{a_sub}")

    # 4. Default AI Agent
    if settings.gemini_api_key:
        table.add_row("Default AI Agent", "[green]PASS[/green]", "Gemini 2.0 Flash Live ready")
    else:
        table.add_row("Default AI Agent", "[yellow]WARN[/yellow]", "GEMINI_API_KEY unset; add it to use default agent")

    console.print(table)
    from wavoice.core.telemetry import track_event
    track_event("doctor_run")
    console.print()
    console.print(CREDITS_FOOTER)


@cli.command()
def start(
    port: int = typer.Option(8000, "--port", "-p", help="Local server port"),
    no_tunnel: bool = typer.Option(False, "--no-tunnel", help="Disable automated Cloudflare tunnel"),
    no_telemetry: bool = typer.Option(False, "--no-telemetry", help="Opt out of anonymous usage telemetry"),
):
    """Start the WhatsApp Voice AI server and launch the default voice agent."""
    console.print(BANNER_HEADER)
    console.print(
        Panel.fit(
            "[bold green]Starting WAVoice Server...[/bold green]\n"
            "Waiting for incoming calls on your WhatsApp number.",
            border_style="green",
        )
    )
    console.print(CREDITS_FOOTER)
    console.print()
    if no_telemetry:
        import os
        os.environ["WAVOICE_TELEMETRY"] = "false"
        settings.telemetry_enabled = False
    from wavoice.core.telemetry import track_event
    track_event("start_server", {"tunnel": not no_tunnel, "port": port})
    from wavoice.sdk import WhatsAppVoiceApp
    app = WhatsAppVoiceApp()
    app.run(tunnel=not no_tunnel, port=port)


if __name__ == "__main__":
    cli()

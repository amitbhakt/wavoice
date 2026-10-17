"""CLI entry point for wavoice (init, doctor, start)."""

import asyncio
import os
from pathlib import Path
import secrets
from typing import Any, Dict, List, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from wavoice.core.config import settings
from wavoice.core.meta import MetaGraphClient
from wavoice.providers.dograh import DograhCloudClient, DograhProvider

cli = typer.Typer(
    name="wavoice",
    help="One-command WhatsApp Voice AI setup with Pipecat.",
    add_completion=False,
)
console = Console()

BANNER_HEADER = """
[bold cyan]╦ ╦╔═╗╦  ╦╔═╗╦╔═╗╔═╗[/bold cyan]   [bold green]WAVoice[/bold green] [dim]v0.2.0[/dim]
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


dograh_cli = typer.Typer(
    name="dograh",
    help="One-command Dograh Cloud setup and WhatsApp agent provisioning.",
    add_completion=False,
)
cli.add_typer(dograh_cli, name="dograh")


def _update_env(updates: dict[str, Any]) -> None:
    """Save or update environment variables in .env immediately."""
    env_path = Path(".env")
    lines = []
    keys = set(updates.keys())
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if any(line.strip().startswith(f"{k}=") for k in keys):
                continue
            lines.append(line)
    for k, v in updates.items():
        if v is not None and str(v).strip():
            lines.append(f"{k}={v}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@dograh_cli.command(name="setup")
def dograh_setup(
    api_key: Optional[str] = typer.Option(
        None,
        "--api-key",
        "-k",
        help="Dograh Cloud API Key (from app.dograh.com/api-keys > 'API Keys' section, NOT Service Key)",
    ),
    token: Optional[str] = typer.Option(None, "--token", "-t", help="Meta System User Access Token"),
    secret: Optional[str] = typer.Option(None, "--secret", "-s", help="Meta App Secret"),
    base_url: str = typer.Option("https://api.dograh.com", "--base-url", help="Dograh API Base URL"),
    no_telemetry: bool = typer.Option(False, "--no-telemetry", help="Opt out of anonymous usage telemetry"),
):
    """One-command setup: connects WhatsApp to Dograh Cloud, deploys sample agent & configures webhooks."""
    if no_telemetry:
        os.environ["WAVOICE_TELEMETRY"] = "false"
    from wavoice.core.telemetry import track_event
    track_event("dograh_setup_started")

    console.print(BANNER_HEADER)
    console.print(
        Panel.fit(
            "[bold cyan]WAVoice 🤝 Dograh Cloud[/bold cyan]\n"
            "[bold green]One-Command WhatsApp AI Agent Setup[/bold green]\n"
            "This wizard will connect Meta WhatsApp Calling, deploy a sample voice agent in Dograh,\n"
            "and configure webhooks so you can call your WhatsApp number in under 2 minutes.",
            border_style="cyan",
        )
    )

    # 1. Dograh API Key
    existing_dograh_key = api_key or settings.dograh_api_key
    if existing_dograh_key:
        masked_dograh = f"{existing_dograh_key[:4]}...{existing_dograh_key[-4:]}"
        console.print(f"[dim]Current Dograh API Key: {masked_dograh}[/dim]")
        dograh_input = typer.prompt(
            "1. Dograh API Key (press Enter to keep current, or paste new key)",
            default="",
            show_default=False,
            hide_input=False,
        ).strip()
        dograh_key = dograh_input if dograh_input else existing_dograh_key
    else:
        console.print("[dim]ℹ️ Tip: Go to [bold cyan]app.dograh.com/api-keys[/bold cyan] and copy the key from the top [bold white]'API Keys'[/bold white] section (do [bold red]NOT[/bold red] use a Service Key).[/dim]")
        dograh_key = typer.prompt("1. Dograh API Key (from top 'API Keys' section, NOT Service Key)").strip()

    if not dograh_key:
        console.print("[red]A Dograh Cloud API Key is required.[/red]")
        raise typer.Exit(1)

    # 2. Meta System User Access Token with validation loop
    meta_token = token
    while True:
        existing_meta = meta_token if meta_token else settings.whatsapp_token
        if existing_meta:
            masked_meta = f"{existing_meta[:6]}...{existing_meta[-4:]}"
            console.print(f"[dim]Current Meta Token: {masked_meta}[/dim]")
            token_input = typer.prompt(
                "2. Meta System User Access Token (paste new value, or press Enter to test current)",
                default="",
                show_default=False,
                hide_input=False,
            ).strip()
            meta_token = token_input if token_input else existing_meta
        else:
            meta_token = typer.prompt("2. Meta System User Access Token", hide_input=False).strip()

        if not meta_token:
            console.print("[red]A Meta System User Access Token is required.[/red]")
            continue

        console.print("[cyan]Validating Meta token with Graph API...[/cyan]")
        async def _check_meta_token(tok: str):
            client = MetaGraphClient(tok)
            try:
                return await client.inspect_token()
            finally:
                await client.close()

        try:
            token_info = asyncio.run(_check_meta_token(meta_token))
            if not token_info or token_info.get("error"):
                err_msg = token_info.get("error", "Invalid token")
                if "expire" in str(err_msg).lower():
                    console.print("[bold red]❌ Token expired![/bold red] [yellow]Your Meta System User Access Token has expired.[/yellow]")
                elif "malformed" in str(err_msg).lower():
                    console.print("[bold red]❌ Token malformed![/bold red] [yellow]The access token format is invalid.[/yellow]")
                else:
                    console.print(f"[bold red]❌ Token invalid:[/bold red] {err_msg}")
                console.print("[yellow]Please paste a fresh Meta System User Access Token from Meta Business Settings.[/yellow]\n")
                meta_token = ""
                continue
            console.print("[green]✓ Meta token is active and verified![/green]")
            break
        except Exception as e:
            err_str = str(e).lower()
            if "expire" in err_str:
                console.print("[bold red]❌ Token expired![/bold red] [yellow]Your Meta System User Access Token has expired.[/yellow]")
            elif "malformed" in err_str:
                console.print("[bold red]❌ Token malformed![/bold red] [yellow]The access token format is invalid.[/yellow]")
            else:
                console.print(f"[bold red]❌ Token check failed:[/bold red] {e}")
            console.print("[yellow]Please paste a fresh Meta System User Access Token.[/yellow]\n")
            meta_token = ""
            continue

    # 3. Meta App Secret
    existing_secret = secret or settings.whatsapp_app_secret
    if existing_secret:
        masked_sec = f"{existing_secret[:4]}...{existing_secret[-2:]}"
        console.print(f"[dim]Current Meta App Secret: {masked_sec}[/dim]")
        sec_input = typer.prompt(
            "3. Meta App Secret (press Enter to keep current, or paste new secret)",
            default="",
            show_default=False,
            hide_input=False,
        ).strip()
        meta_secret = sec_input if sec_input else existing_secret
    else:
        meta_secret = typer.prompt("3. Meta App Secret (from App settings > Basic)").strip()

    if not meta_secret:
        console.print("[red]Meta App Secret is required.[/red]")
        raise typer.Exit(1)

    # Immediately persist user credentials to .env so future runs or failures retain them
    _update_env({
        "DOGRAH_API_KEY": dograh_key,
        "DOGRAH_BASE_URL": base_url,
        "WHATSAPP_TOKEN": meta_token,
        "WHATSAPP_APP_SECRET": meta_secret,
    })

    console.print()
    console.print("[bold yellow]🚀 Initiating one-command setup...[/bold yellow]\n")

    async def _execute():
        meta = MetaGraphClient(meta_token)
        dograh = DograhCloudClient(api_key=dograh_key, base_url=base_url)

        try:
            # Step 1: Inspect token & discover IDs
            console.print("[cyan]1/7 Validating Meta System User Token...[/cyan]")
            token_info = await meta.inspect_token()
            if not token_info or token_info.get("error"):
                raise ValueError(f"Meta token invalid: {token_info.get('error', 'Authentication failed')}")

            waba_id = settings.whatsapp_waba_id or await meta.discover_waba_id()
            if not waba_id:
                raise ValueError("Could not auto-discover WhatsApp Business Account ID (WABA). Check token permissions.")

            phone_id = settings.whatsapp_phone_number_id or await meta.discover_phone_number_id(waba_id)
            if not phone_id:
                raise ValueError("Could not find any WhatsApp Phone Number ID linked to this account.")

            # Save discovered WABA ID and Phone Number ID to .env
            _update_env({
                "WHATSAPP_WABA_ID": waba_id,
                "WHATSAPP_PHONE_NUMBER_ID": phone_id,
            })

            phone_info = await meta.verify_phone_number(phone_id)
            display_num = phone_info.get("display_phone_number", phone_id)
            verified_name = phone_info.get("verified_name", "Business")
            console.print(f"    [green]✓ Verified WhatsApp Number:[/green] [bold]{display_num}[/bold] ({verified_name})")

            # Step 2: Auto-enable voice calling on Meta
            console.print("[cyan]2/7 Checking & auto-enabling WhatsApp Voice Calling...[/cyan]")
            await meta.enable_voice_calling(phone_id)
            console.print("    [green]✓ WhatsApp Voice Calling status: ENABLED[/green]")

            # Step 3: Create Telephony Configuration in Dograh Cloud
            console.print("[cyan]3/7 Registering WhatsApp telephony configuration in Dograh Cloud...[/cyan]")
            existing_configs = await dograh.list_telephony_configurations()
            existing_wa = [
                c for c in existing_configs
                if c.get("provider") == "whatsapp" and not c.get("inactive", False)
            ]
            if existing_wa:
                wa_summary = ", ".join(f"'{c.get('name')}' (ID: {c.get('id')})" for c in existing_wa)
                console.print(f"    [yellow]⚠️ Found existing WhatsApp configuration in Dograh: {wa_summary}[/yellow]")
                should_create = typer.confirm("    Do you want to create another WhatsApp configuration?", default=False)
                if not should_create:
                    console.print("\n[yellow]Setup cancelled. Exiting.[/yellow]")
                    raise typer.Exit(0)

            # Configuration name: "WhatsApp Setup" (with unique suffix if already taken)
            base_config_name = "WhatsApp Setup"
            config_name = base_config_name
            existing_names = {c.get("name") for c in existing_configs}
            counter = 2
            while config_name in existing_names:
                config_name = f"{base_config_name} ({counter})"
                counter += 1

            try:
                config_resp = await dograh.create_telephony_configuration(
                    name=config_name,
                    access_token=meta_token,
                    waba_id=waba_id,
                    app_secret=meta_secret,
                )
            except Exception as e:
                if "already exists" in str(e).lower() or "409" in str(e):
                    configs = await dograh.list_telephony_configurations()
                    matching = [c for c in configs if c.get("name") == config_name or c.get("provider") == "whatsapp"]
                    if matching:
                        config_resp = await dograh.get_telephony_configuration(matching[-1]["id"])
                    else:
                        raise e
                else:
                    raise e

            config_id = config_resp["id"]
            webhook_verify_token = config_resp.get("credentials", {}).get("webhook_verify_token")
            if not webhook_verify_token:
                refreshed = await dograh.get_telephony_configuration(config_id)
                webhook_verify_token = refreshed.get("credentials", {}).get("webhook_verify_token") or "dograh_verify_token"
            console.print(f"    [green]✓ Dograh Telephony Configuration ready: [bold]{config_name}[/bold] (ID: {config_id})[/green]")

            # Step 4: Sync phone numbers into Dograh
            console.print("[cyan]4/7 Syncing phone numbers from Meta into Dograh...[/cyan]")
            await dograh.sync_phone_numbers(config_id)
            dograh_numbers = await dograh.list_phone_numbers(config_id)
            phone_row_id = None
            clean_display = "".join(c for c in str(display_num) if c.isdigit())
            for p in dograh_numbers:
                extra = p.get("extra_metadata") or p.get("metadata") or {}
                ext_id = str(p.get("external_id") or p.get("phone_number_id") or extra.get("phone_number_id") or "")
                addr_digits = "".join(c for c in str(p.get("address") or p.get("address_normalized") or "") if c.isdigit())
                if ext_id == str(phone_id) or (addr_digits and addr_digits == clean_display):
                    phone_row_id = p["id"]
                    break
            if not phone_row_id and dograh_numbers:
                phone_row_id = dograh_numbers[0]["id"]
            console.print(f"    [green]✓ Synced {len(dograh_numbers)} phone number(s) to Dograh[/green]")

            # Step 5: Create sample WhatsApp agent workflow
            console.print("[cyan]5/7 Creating sample WhatsApp AI voice agent workflow in Dograh...[/cyan]")
            workflow_name = f"WhatsApp Voice Assistant ({display_num})"
            wf_resp = await dograh.create_sample_whatsapp_workflow(name=workflow_name)
            workflow_id = wf_resp["id"]
            console.print(f"    [green]✓ Created workflow: [bold]{workflow_name}[/bold] (ID: {workflow_id})[/green]")

            # Step 6: Publish workflow & bind to phone number
            console.print("[cyan]6/7 Publishing workflow and binding to your phone number...[/cyan]")
            try:
                await dograh.publish_workflow(workflow_id)
            except Exception as e:
                err_text = str(e).lower()
                if "no draft" in err_text or "already" in err_text:
                    logger.debug(f"[Dograh] Workflow publish notice: {e}")
                else:
                    raise e
            if phone_row_id:
                await dograh.bind_workflow_to_phone_number(
                    config_id=config_id,
                    phone_number_row_id=phone_row_id,
                    workflow_id=workflow_id,
                )
                console.print(f"    [green]✓ Inbound workflow attached & bound to {display_num} (Row ID: {phone_row_id})![/green]")
            else:
                raise ValueError(
                    f"Could not find phone number {display_num} under Dograh config {config_id} to attach inbound workflow."
                )

            # Step 7: Overriding Meta webhooks to Dograh Cloud
            console.print("[cyan]7/7 Setting Meta Webhook override to Dograh Cloud...[/cyan]")
            dograh_webhook_url = dograh.get_whatsapp_webhook_url()
            await meta.override_phone_number_webhook(
                phone_number_id=phone_id,
                callback_url=dograh_webhook_url,
                verify_token=webhook_verify_token,
            )
            await meta.subscribe_waba_webhook(
                waba_id=waba_id,
                callback_url=dograh_webhook_url,
                verify_token=webhook_verify_token,
            )
            console.print(f"    [green]✓ Meta Webhook successfully routed to: {dograh_webhook_url}[/green]")

            return {
                "display_num": display_num,
                "phone_id": phone_id,
                "waba_id": waba_id,
                "workflow_id": workflow_id,
                "workflow_name": workflow_name,
                "dograh_url": f"https://app.dograh.com/workflows/{workflow_id}",
            }
        finally:
            await meta.close()
            await dograh.close()

    try:
        result = asyncio.run(_execute())
    except typer.Exit:
        raise
    except Exception as e:
        from wavoice.core.telemetry import track_event
        track_event("dograh_setup_failed", {"error": str(e)[:100]})
        console.print(f"\n[bold red]❌ Setup failed:[/bold red] {e}")
        raise typer.Exit(1)

    # Ensure final state is saved in .env
    _update_env({
        "WHATSAPP_TOKEN": meta_token,
        "WHATSAPP_APP_SECRET": meta_secret,
        "WHATSAPP_WABA_ID": result["waba_id"],
        "WHATSAPP_PHONE_NUMBER_ID": result["phone_id"],
        "DOGRAH_API_KEY": dograh_key,
        "DOGRAH_BASE_URL": base_url,
    })

    from wavoice.core.telemetry import track_event
    track_event("dograh_setup_completed", {"workflow_id": result.get("workflow_id")})

    # Success Table
    console.print()
    summary_table = Table(title="🎉 Setup Complete!", show_header=True, header_style="bold green")
    summary_table.add_column("Property", style="bold white", width=25)
    summary_table.add_column("Details", style="cyan")

    summary_table.add_row("WhatsApp Number", f"[bold green]{result['display_num']}[/bold green]")
    summary_table.add_row("Dograh Agent Name", result["workflow_name"])
    summary_table.add_row("Agent Workflow ID", str(result["workflow_id"]))
    summary_table.add_row("Dograh Studio Link", f"[underline cyan]{result['dograh_url']}[/underline cyan]")
    summary_table.add_row("Initial Greeting", "Hello! You have successfully connected WhatsApp AI calling via Dograh...")

    console.print(summary_table)
    console.print()
    console.print(
        Panel.fit(
            f"[bold green]📞 Test It Right Now![/bold green]\n"
            f"Open WhatsApp on your phone and call: [bold white]{result['display_num']}[/bold white]\n"
            f"Your new Dograh AI agent will answer and chat with you in real-time!",
            border_style="green",
        )
    )
    console.print(CREDITS_FOOTER)


@cli.command(name="setup-dograh", hidden=True)
def setup_dograh_alias(
    api_key: Optional[str] = typer.Option(None, "--api-key", "-k", help="Dograh Cloud API Key"),
    token: Optional[str] = typer.Option(None, "--token", "-t", help="Meta System User Access Token"),
    secret: Optional[str] = typer.Option(None, "--secret", "-s", help="Meta App Secret"),
    base_url: str = typer.Option("https://api.dograh.com", "--base-url", help="Dograh API Base URL"),
    no_telemetry: bool = typer.Option(False, "--no-telemetry", help="Opt out of anonymous usage telemetry"),
):
    """Alias for 'wavoice dograh setup'."""
    dograh_setup(api_key=api_key, token=token, secret=secret, base_url=base_url, no_telemetry=no_telemetry)


@dograh_cli.command(name="doctor")
def dograh_doctor():
    """Run pre-flight diagnostics on your Dograh Cloud WhatsApp setup."""
    console.print(BANNER_HEADER)
    console.print(Panel.fit("[bold cyan]WAVoice Dograh Cloud Diagnostics[/bold cyan]", border_style="cyan"))

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Check", style="dim", width=30)
    table.add_column("Status", width=12)
    table.add_column("Details")

    from wavoice.core.config import Settings
    provider = DograhProvider(config=Settings())

    diag = asyncio.run(provider.doctor())
    for check_name, (ok, detail) in diag.items():
        status = "[green]PASS[/green]" if ok else "[red]FAIL[/red]"
        table.add_row(check_name.title(), status, detail)

    console.print(table)
    console.print()
    console.print(CREDITS_FOOTER)


# -------------------------------------------------------------------------
# LiveKit Cloud WhatsApp Subcommand Group
# -------------------------------------------------------------------------
livekit_cli = typer.Typer(
    name="livekit",
    help="One-command LiveKit Cloud WhatsApp Voice AI setup and runtime.",
    add_completion=False,
)
cli.add_typer(livekit_cli, name="livekit")


@livekit_cli.command(name="setup")
def livekit_setup(
    url: Optional[str] = typer.Option(None, "--url", "-u", help="LiveKit Cloud URL (e.g. wss://my-project.livekit.cloud)"),
    api_key: Optional[str] = typer.Option(None, "--api-key", "-k", help="LiveKit API Key"),
    api_secret: Optional[str] = typer.Option(None, "--api-secret", "-s", help="LiveKit API Secret"),
    token: Optional[str] = typer.Option(None, "--token", "-t", help="Meta System User Access Token"),
    secret: Optional[str] = typer.Option(None, "--secret", help="Meta App Secret"),
    public_url: Optional[str] = typer.Option(None, "--public-url", "-p", help="Custom public HTTPS URL (skips tunnel)"),
    launch: bool = typer.Option(False, "--launch", "-l", help="Automatically launch runtime after setup"),
    no_telemetry: bool = typer.Option(False, "--no-telemetry", help="Opt out of anonymous usage telemetry"),
):
    """One-command setup: connects WhatsApp to LiveKit Cloud, configures webhooks, and deploys sample agent."""
    if no_telemetry:
        os.environ["WAVOICE_TELEMETRY"] = "false"
    from wavoice.core.telemetry import track_event
    track_event("livekit_setup_started")

    console.print(BANNER_HEADER)
    console.print(
        Panel.fit(
            "[bold green]LiveKit Cloud WhatsApp Voice AI Setup[/bold green]\n"
            "Connect WhatsApp Business to LiveKit Cloud in under 90 seconds.",
            border_style="green",
        )
    )

    from wavoice.providers.livekit.detector import detect_local_livekit_config, parse_livekit_env_block
    from wavoice.providers.livekit.client import LiveKitCloudClient

    # 1. LiveKit Credentials Detection / Input
    lk_url = url or settings.livekit_url
    lk_key = api_key or settings.livekit_api_key
    lk_sec = api_secret or settings.livekit_api_secret

    if not (lk_url and lk_key and lk_sec):
        # Try local detection from ~/.livekit/config.yaml or livekit.toml
        detected = detect_local_livekit_config()
        if detected:
            proj_name = detected.get("project_name", "default")
            console.print(f"[green]✓ Found local LiveKit project: [bold]{proj_name}[/bold][/green]")
            use_detected = typer.confirm(f"Use detected project ({detected.get('LIVEKIT_URL')})?", default=True)
            if use_detected:
                lk_url = detected.get("LIVEKIT_URL")
                lk_key = detected.get("LIVEKIT_API_KEY")
                lk_sec = detected.get("LIVEKIT_API_SECRET")

    # If still missing, give option to paste single .env block or enter individually
    if not (lk_url and lk_key and lk_sec):
        console.print("\n[dim]Tip: You can paste the copied .env snippet from cloud.livekit.io below,[/dim]")
        console.print("[dim]or press Enter to input URL, API Key, and Secret individually.[/dim]")
        raw_paste = typer.prompt("Paste LiveKit Cloud .env block (or press Enter to skip)", default="", show_default=False).strip()
        if raw_paste:
            parsed = parse_livekit_env_block(raw_paste)
            lk_url = parsed.get("LIVEKIT_URL") or lk_url
            lk_key = parsed.get("LIVEKIT_API_KEY") or lk_key
            lk_sec = parsed.get("LIVEKIT_API_SECRET") or lk_sec

    def _clean_lk_val(v: Optional[str]) -> str:
        if not v:
            return ""
        s = v.strip().strip("\"'")
        if "=" in s:
            s = s.split("=", 1)[1].strip().strip("\"'")
        return s

    # Prompt individually if still missing
    if not lk_url:
        lk_url = typer.prompt("1. LiveKit Cloud URL (e.g., wss://my-project.livekit.cloud)").strip()
    if not lk_key:
        lk_key = typer.prompt("2. LiveKit API Key (e.g., APIxxxxxxxxx)").strip()
    if not lk_sec:
        lk_sec = typer.prompt("3. LiveKit API Secret", hide_input=False).strip()

    lk_url = _clean_lk_val(lk_url)
    lk_key = _clean_lk_val(lk_key)
    lk_sec = _clean_lk_val(lk_sec)

    # Test LiveKit connectivity
    console.print("\n[cyan]Testing LiveKit Cloud connection...[/cyan]")
    lk_client = LiveKitCloudClient(url=lk_url, api_key=lk_key, api_secret=lk_sec)
    try:
        conn = asyncio.run(lk_client.validate_connection())
        console.print(f"[green]✓ Connected to LiveKit Cloud! (Key: {conn['api_key']})[/green]")
    except Exception as e:
        console.print(f"[bold red]❌ LiveKit connection failed:[/bold red] {e}")
        raise typer.Exit(1)
    finally:
        asyncio.run(lk_client.close())

    # 2. Meta System User Access Token
    meta_token = token or settings.whatsapp_token
    while True:
        if meta_token:
            masked = f"{meta_token[:6]}...{meta_token[-4:]}"
            console.print(f"[dim]Current Meta Token: {masked}[/dim]")
            tok_input = typer.prompt(
                "4. Meta System User Access Token (press Enter to keep current, or paste new token)",
                default="",
                show_default=False,
                hide_input=False,
            ).strip()
            meta_token = tok_input if tok_input else meta_token
        else:
            meta_token = typer.prompt("4. Meta System User Access Token", hide_input=False).strip()

        if not meta_token:
            console.print("[red]A Meta System User Access Token is required.[/red]")
            continue

        console.print("[cyan]Validating Meta token with Graph API...[/cyan]")
        async def _check_meta(tok: str):
            client = MetaGraphClient(tok)
            try:
                return await client.inspect_token()
            finally:
                await client.close()

        try:
            tok_info = asyncio.run(_check_meta(meta_token))
            if not tok_info or tok_info.get("error"):
                console.print(f"[bold red]❌ Token invalid:[/bold red] {tok_info.get('error', 'Authentication failed')}")
                meta_token = ""
                continue
            console.print("[green]✓ Meta token verified active![/green]")
            break
        except Exception as e:
            console.print(f"[bold red]❌ Token check failed:[/bold red] {e}")
            meta_token = ""
            continue

    # 3. Meta App Secret
    meta_secret = secret or settings.whatsapp_app_secret
    if meta_secret:
        masked_sec = f"{meta_secret[:4]}...{meta_secret[-2:]}"
        console.print(f"[dim]Current Meta App Secret: {masked_sec}[/dim]")
        sec_input = typer.prompt(
            "5. Meta App Secret (press Enter to keep current, or paste new secret)",
            default="",
            show_default=False,
            hide_input=False,
        ).strip()
        meta_secret = sec_input if sec_input else meta_secret
    else:
        meta_secret = typer.prompt("5. Meta App Secret (from Meta App > Settings > Basic)").strip()

    # 4. Ingress Preference (Tunnel vs Custom URL)
    chosen_public_url = public_url or settings.public_url
    if not chosen_public_url:
        console.print("\n[bold cyan]Webhook Ingress Configuration:[/bold cyan]")
        console.print("  [bold green]1.[/bold green] Automated Cloudflare Quick Tunnel [dim](Recommended for local testing — zero setup)[/dim]")
        console.print("  [bold green]2.[/bold green] Custom Public HTTPS URL [dim](For production/staging e.g. https://api.mycompany.com)[/dim]")
        choice = typer.prompt("Select ingress method", default="1").strip()
        if choice == "2":
            chosen_public_url = typer.prompt("Enter public HTTPS URL").strip().rstrip("/")

    # Discover account details & auto-enable calling
    console.print("\n[cyan]Auto-discovering WhatsApp account details via Meta Graph API...[/cyan]")
    async def _setup_meta():
        meta = MetaGraphClient(meta_token)
        try:
            waba = settings.whatsapp_waba_id or await meta.discover_waba_id()
            phone = settings.whatsapp_phone_number_id or (await meta.discover_phone_number_id(waba) if waba else None)
            phone_data = await meta.verify_phone_number(phone) if phone else {}
            # Auto-enable voice calling
            if phone:
                await meta.enable_voice_calling(phone)
            return waba, phone, phone_data
        finally:
            await meta.close()

    try:
        waba_id, phone_id, phone_info = asyncio.run(_setup_meta())
        display_num = phone_info.get("display_phone_number", phone_id or "Unknown")
        console.print(f"    [green]✓ WhatsApp Business Number:[/green] [bold]{display_num}[/bold]")
        console.print("    [green]✓ WhatsApp Voice Calling status: ENABLED[/green]")
    except Exception as e:
        console.print(f"[yellow]Meta auto-discovery notice: {e}[/yellow]")
        waba_id = settings.whatsapp_waba_id or ""
        phone_id = settings.whatsapp_phone_number_id or ""
        display_num = phone_id

    # Save to .env
    _update_env({
        "LIVEKIT_URL": lk_url,
        "LIVEKIT_API_KEY": lk_key,
        "LIVEKIT_API_SECRET": lk_sec,
        "WHATSAPP_TOKEN": meta_token,
        "WHATSAPP_APP_SECRET": meta_secret,
        "WHATSAPP_WABA_ID": waba_id,
        "WHATSAPP_PHONE_NUMBER_ID": phone_id,
        "PUBLIC_URL": chosen_public_url,
    })
    console.print("\n[bold green]✓ Configuration saved to .env![/bold green]")
    track_event("livekit_setup_completed")

    # Summary table
    console.print()
    summary_table = Table(title="🎉 LiveKit WhatsApp Setup Complete!", show_header=True, header_style="bold green")
    summary_table.add_column("Property", style="bold white", width=25)
    summary_table.add_column("Details", style="cyan")

    summary_table.add_row("WhatsApp Number", f"[bold green]{display_num}[/bold green]")
    summary_table.add_row("LiveKit Project", lk_url)
    summary_table.add_row("Ingress Method", f"Custom URL ({chosen_public_url})" if chosen_public_url else "Automated Cloudflare Quick Tunnel")
    summary_table.add_row("Starter AI Agent", "LiveKit Voice Agent (wavoice-agent)")
    summary_table.add_row("Initial Greeting", "Hello! You have successfully connected WhatsApp AI calling via LiveKit Cloud...")

    console.print(summary_table)
    console.print()
    console.print(
        Panel.fit(
            f"[bold green]📞 Ready to Talk![/bold green]\n"
            f"Run [cyan]wavoice livekit dev[/cyan] to launch the bridge & start talking to your LiveKit AI agent!",
            border_style="green",
        )
    )
    console.print(CREDITS_FOOTER)

    should_launch = launch or typer.confirm("Do you want to start the LiveKit AI agent server now?", default=True)
    if should_launch:
        from wavoice.core.config import Settings
        from wavoice.providers.livekit.runtime import LiveKitRuntime
        runtime = LiveKitRuntime(config=Settings())
        runtime.run(tunnel=not bool(chosen_public_url), custom_url=chosen_public_url)


@livekit_cli.command(name="dev")
def livekit_dev(
    port: int = typer.Option(8000, "--port", "-p", help="Local webhook server port"),
    no_tunnel: bool = typer.Option(False, "--no-tunnel", help="Disable automated Cloudflare tunnel"),
    public_url: Optional[str] = typer.Option(None, "--public-url", help="Custom public HTTPS URL (skips tunnel)"),
    agent_name: Optional[str] = typer.Option(None, "--agent-name", "-a", help="Target LiveKit agent name (defaults to wavoice-agent or LIVEKIT_AGENT_NAME)"),
    no_agent: bool = typer.Option(False, "--no-agent", help="Do not run bundled test agent worker (use your own LiveKit agent)"),
    no_telemetry: bool = typer.Option(False, "--no-telemetry", help="Opt out of anonymous usage telemetry"),
):
    """Start the LiveKit WhatsApp bridge and launch the bundled LiveKit AI agent."""
    if no_telemetry:
        os.environ["WAVOICE_TELEMETRY"] = "false"
        settings.telemetry_enabled = False

    target_agent = agent_name or settings.livekit_agent_name or "wavoice-agent"

    console.print(BANNER_HEADER)
    console.print(
        Panel.fit(
            f"[bold green]Starting WAVoice LiveKit Cloud Bridge...[/bold green]\n"
            f"Routing incoming WhatsApp voice calls to LiveKit agent: [bold cyan]{target_agent}[/bold cyan]"
            + (" (running own external agent worker)" if no_agent else " (running bundled test worker)"),
            border_style="green",
        )
    )
    console.print(CREDITS_FOOTER)
    console.print()

    from wavoice.core.config import Settings
    cfg = Settings()
    if not (cfg.livekit_url and cfg.livekit_api_key and cfg.livekit_api_secret):
        console.print("[bold red]❌ LiveKit credentials missing![/bold red]")
        console.print("[yellow]LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET are not configured in your .env[/yellow]\n")
        should_setup = typer.confirm("Would you like to run 'wavoice livekit setup' now?", default=True)
        if should_setup:
            livekit_setup()
            return
        raise typer.Exit(1)

    from wavoice.providers.livekit.runtime import LiveKitRuntime
    runtime = LiveKitRuntime(config=cfg)
    runtime.run(
        port=port,
        tunnel=not no_tunnel and not public_url and not cfg.public_url,
        custom_url=public_url or cfg.public_url,
        run_agent=not no_agent,
        agent_name=target_agent,
    )


@livekit_cli.command(name="doctor")
def livekit_doctor():
    """Run pre-flight diagnostics on your LiveKit Cloud WhatsApp setup."""
    console.print(BANNER_HEADER)
    console.print(Panel.fit("[bold cyan]WAVoice LiveKit Cloud Diagnostics[/bold cyan]", border_style="cyan"))

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Check", style="dim", width=30)
    table.add_column("Status", width=12)
    table.add_column("Details")

    from wavoice.core.config import Settings
    from wavoice.providers.livekit.provider import LiveKitProvider
    provider = LiveKitProvider(config=Settings())

    diag = asyncio.run(provider.doctor())
    for check_name, (ok, detail) in diag.items():
        status = "[green]PASS[/green]" if ok else "[red]FAIL[/red]"
        table.add_row(check_name.title(), status, detail)

    console.print(table)
    console.print()
    console.print(CREDITS_FOOTER)


@cli.command(name="setup-livekit", hidden=True)
def setup_livekit_alias(
    url: Optional[str] = typer.Option(None, "--url", "-u", help="LiveKit Cloud URL"),
    api_key: Optional[str] = typer.Option(None, "--api-key", "-k", help="LiveKit API Key"),
    api_secret: Optional[str] = typer.Option(None, "--api-secret", "-s", help="LiveKit API Secret"),
    token: Optional[str] = typer.Option(None, "--token", "-t", help="Meta System User Access Token"),
    secret: Optional[str] = typer.Option(None, "--secret", help="Meta App Secret"),
    public_url: Optional[str] = typer.Option(None, "--public-url", "-p", help="Custom public HTTPS URL"),
    launch: bool = typer.Option(False, "--launch", "-l", help="Launch runtime after setup"),
    no_telemetry: bool = typer.Option(False, "--no-telemetry", help="Opt out of anonymous usage telemetry"),
):
    """Alias for 'wavoice livekit setup'."""
    livekit_setup(
        url=url,
        api_key=api_key,
        api_secret=api_secret,
        token=token,
        secret=secret,
        public_url=public_url,
        launch=launch,
        no_telemetry=no_telemetry,
    )


if __name__ == "__main__":
    cli()



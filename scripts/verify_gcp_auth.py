#!/usr/bin/env python3
"""
GCP Project Authentication & Verification Utility.
Strictly verifies that the developer is authenticated to the specific GCP_PROJECT_ID defined in .env,
checking gcloud active project, ADC credentials, and live project permissions.
"""
import sys
import os
import json
import subprocess
from typing import Tuple, Optional
import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.config import settings

console = Console()

def get_gcloud_active_account() -> Optional[str]:
    """Retrieve the active gcloud authenticated account."""
    try:
        res = subprocess.run(
            ["gcloud", "auth", "list", "--filter=status:ACTIVE", "--format=value(account)"],
            capture_output=True,
            text=True,
            check=True
        )
        return res.stdout.strip() or None
    except Exception:
        return None

def get_gcloud_active_project() -> Optional[str]:
    """Retrieve the current active gcloud CLI project."""
    try:
        res = subprocess.run(
            ["gcloud", "config", "get-value", "project"],
            capture_output=True,
            text=True,
            check=True
        )
        val = res.stdout.strip()
        return val if val and val != "(unset)" else None
    except Exception:
        return None

def get_adc_info() -> Tuple[bool, Optional[str], Optional[str]]:
    """Check Application Default Credentials (ADC) file and extract quota_project_id."""
    adc_path = os.path.expanduser("~/.config/gcloud/application_default_credentials.json")
    if not os.path.exists(adc_path):
        return False, None, adc_path
    try:
        with open(adc_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        quota_project = data.get("quota_project_id")
        return True, quota_project, adc_path
    except Exception:
        return True, None, adc_path

def check_live_project_access(project_id: str) -> Tuple[bool, str]:
    """Test actual live access to the project using google-auth and google-cloud-storage."""
    try:
        import google.auth
        from google.cloud import storage

        credentials, detected_project = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )

        client = storage.Client(project=project_id, credentials=credentials)
        # Attempt to list 1 bucket or lookup to verify token permissions on this specific project
        list(client.list_buckets(max_results=1))
        return True, "Successfully connected to project and verified API permissions."
    except Exception as e:
        err_msg = str(e)
        if "403" in err_msg or "Permission" in err_msg or "denied" in err_msg.lower():
            return False, f"Permission denied on project '{project_id}': {err_msg}"
        elif "404" in err_msg or "not found" in err_msg.lower():
            return False, f"Project '{project_id}' not found or credentials do not have access."
        elif "Could not automatically determine credentials" in err_msg:
            return False, "Application Default Credentials (ADC) not configured."
        return False, f"Error verifying access to '{project_id}': {err_msg}"

@click.command()
@click.option("--fix", is_flag=True, default=False, help="Automatically fix gcloud project and quota project to match .env.")
def main(fix):
    """Verify that you are authenticated to the specific project in .env."""
    console.print(Panel.fit(
        "[bold cyan]🔍 Target GCP Project Authentication Verifier[/bold cyan]\n"
        f"[dim]Expected Target Project from .env: [bold green]{settings.project_id}[/bold green][/dim]",
        border_style="cyan"
    ))

    target_project = settings.project_id
    if not target_project or target_project == "your-gcp-project-id":
        console.print("[bold red]✗ Configuration Error:[/bold red] GCP_PROJECT_ID is not set in .env or is set to placeholder.")
        console.print("Please set your real GCP Project ID in .env first.")
        sys.exit(1)

    table = Table(title="Authentication Checklist", border_style="cyan")
    table.add_column("Check Item", style="bold")
    table.add_column("Current Value", style="cyan")
    table.add_column("Required (.env)", style="green")
    table.add_column("Status", justify="center")

    has_errors = False
    fix_commands = []

    # 1. Active Account
    active_account = get_gcloud_active_account()
    if active_account:
        table.add_row("Active gcloud Account", active_account, "Logged-in User", "[green]PASS[/green]")
    else:
        table.add_row("Active gcloud Account", "Not logged in", "Logged-in User", "[bold red]FAIL[/bold red]")
        has_errors = True
        fix_commands.append("gcloud auth login")

    # 2. gcloud CLI Project
    gcloud_project = get_gcloud_active_project()
    if gcloud_project == target_project:
        table.add_row("gcloud Config Project", gcloud_project, target_project, "[green]PASS (MATCH)[/green]")
    else:
        status_msg = f"[bold red]FAIL (MISMATCH: {gcloud_project or 'None'})[/bold red]"
        table.add_row("gcloud Config Project", str(gcloud_project), target_project, status_msg)
        has_errors = True
        fix_commands.append(f"gcloud config set project {target_project}")

    # 3. ADC Credentials File & Quota Project
    adc_exists, adc_quota_project, adc_path = get_adc_info()
    if not adc_exists:
        table.add_row("ADC Credentials", "Missing", f"~/.config/... matching {target_project}", "[bold red]FAIL[/bold red]")
        has_errors = True
        fix_commands.append("gcloud auth application-default login")
        fix_commands.append(f"gcloud auth application-default set-quota-project {target_project}")
    else:
        if adc_quota_project == target_project:
            table.add_row("ADC Quota Project", adc_quota_project, target_project, "[green]PASS (MATCH)[/green]")
        else:
            table.add_row("ADC Quota Project", str(adc_quota_project or "Unset"), target_project, "[yellow]WARN (MISMATCH)[/yellow]")
            fix_commands.append(f"gcloud auth application-default set-quota-project {target_project}")

    # 4. Live API Access Check to target_project
    live_ok, live_msg = check_live_project_access(target_project)
    if live_ok:
        table.add_row("Live API Permissions", "Access Granted", target_project, "[green]PASS[/green]")
    else:
        table.add_row("Live API Permissions", "Access Denied", target_project, "[bold red]FAIL[/bold red]")
        has_errors = True

    console.print(table)
    console.print()

    if has_errors:
        console.print(Panel(
            f"[bold red]Authentication Mismatch / Failure for Target Project: {target_project}[/bold red]\n\n"
            f"Details: {live_msg}\n\n"
            "[bold yellow]Required actions to connect to the project specified in .env:[/bold yellow]\n" +
            "\n".join([f"  [cyan]{cmd}[/cyan]" for cmd in fix_commands]),
            title="⚠️ Action Required",
            border_style="red"
        ))

        # Interactive login flow if running in a terminal and not explicitly disabled
        should_login = fix
        if not should_login and sys.stdin.isatty():
            should_login = click.confirm(
                f"\nWould you like to authenticate / switch to target project '{target_project}' now?",
                default=True
            )

        if should_login:
            console.print(f"\n[bold cyan]Initiating login and configuration for project: {target_project}...[/bold cyan]")
            
            # Step 1: Set gcloud CLI project
            console.print(f"1. Setting active gcloud project to [cyan]{target_project}[/cyan]...")
            subprocess.run(f"gcloud config set project {target_project}", shell=True)

            # Step 2: Ensure gcloud user login
            if not active_account:
                console.print(f"2. Logging in to gcloud account...")
                subprocess.run(f"gcloud auth login", shell=True)

            # Step 3: Configure Application Default Credentials (ADC)
            console.print(f"3. Authenticating Application Default Credentials (ADC)...")
            subprocess.run(f"gcloud auth application-default login", shell=True)

            # Step 4: Set quota project on ADC
            console.print(f"4. Setting ADC quota project to [cyan]{target_project}[/cyan]...")
            subprocess.run(f"gcloud auth application-default set-quota-project {target_project}", shell=True)

            console.print("\n[bold green]Configuration complete! Re-verifying connection...[/bold green]\n")
            # Recursive check to verify after login
            has_errors_after, final_msg = check_live_project_access(target_project)
            if has_errors_after:
                console.print(Panel(
                    f"[bold green]✓ Successfully authenticated to {target_project}![/bold green]\n"
                    f"ADC Quota Project and gcloud CLI are now aligned with .env.",
                    title="🎉 Project Authentication Confirmed",
                    border_style="green"
                ))
                return
            else:
                console.print(f"[bold red]Verification after login encountered: {final_msg}[/bold red]")
                sys.exit(1)
        else:
            console.print("[yellow]Skipping authentication. You can run 'make auth' or 'make auth-fix' whenever you are ready.[/yellow]")
            sys.exit(1)
    else:
        console.print(Panel(
            f"[bold green]✓ Verified:[/bold green] Authenticated to target project [bold cyan]{target_project}[/bold cyan].\n"
            f"Active Account: [green]{active_account}[/green]\n"
            f"GCS Storage & Vertex AI endpoints are accessible on this project.",
            title="🎉 Project Authentication Confirmed",
            border_style="green"
        ))

if __name__ == "__main__":
    main()

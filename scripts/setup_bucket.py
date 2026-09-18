#!/usr/bin/env python3
"""
GCS Bucket Provisioning & Access Control Setup Script.
Provisions GCS bucket with 5-character random suffix, configures object lifecycle rules
(30-day retention default vs. 0 for no expiration), and displays IAM condition policies for prefix routing.
"""
import sys
import os
import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.config import settings
from src.storage.gcs_client import GCSStorageClient
from src.ai.personas import PERSONAS

console = Console()

@click.command()
@click.option("--bucket", "-b", default=None, help="Explicit bucket name (overrides .env GCS_BUCKET_NAME).")
@click.option("--base-name", default=None, help="Base bucket name (default: from .env GCS_BUCKET_BASE_NAME).")
@click.option("--expiration-days", "-e", default=None, type=int, help="Object expiration in days (0 = no expiration).")
@click.option("--info", is_flag=True, default=False, help="Inspect existing bucket and print prefix IAM condition templates without modifying.")
def main(bucket, base_name, expiration_days, info):
    """Provision and inspect GCS Audio Bucket with Lifecycle Rules and Audience Prefix Routing."""
    console.print(Panel.fit(
        "[bold cyan]🪣 Google Cloud Storage Bucket & Access Control Manager[/bold cyan]\n"
        f"[dim]Project: {settings.project_id} | Location: {settings.location} | Base: {base_name or settings.gcs_bucket_base_name}[/dim]",
        border_style="cyan"
    ))

    target_bucket_name = bucket or settings.gcs_bucket_name
    exp_days = settings.gcs_object_expiration_days if expiration_days is None else expiration_days

    client = GCSStorageClient(bucket_name=target_bucket_name)

    if info:
        if not target_bucket_name:
            console.print("[bold red]Error:[/bold red] No GCS_BUCKET_NAME set in .env or passed via --bucket. Run without --info to provision one.")
            sys.exit(1)

        try:
            b = client.client.lookup_bucket(target_bucket_name)
            if not b:
                console.print(f"[bold red]Bucket not found:[/bold red] '{target_bucket_name}' does not exist in project '{settings.project_id}'.")
                sys.exit(1)

            _render_bucket_status(b, exp_days)
            _render_prefix_table(target_bucket_name)
        except Exception as e:
            console.print(f"[bold red]GCS API Error:[/bold red] {e}")
            sys.exit(1)
        return

    # Provision or update bucket
    try:
        console.print("[cyan]Ensuring GCS bucket exists and lifecycle rules are enforced...[/cyan]")
        b = client.ensure_bucket_exists(bucket_name=target_bucket_name)
        
        # If user explicitly passed expiration days, apply it
        if expiration_days is not None:
            client.apply_lifecycle_rule(b, expiration_days=expiration_days)

        console.print(f"[bold green]✓ Bucket verified and ready:[/bold green] [cyan]{b.name}[/cyan]\n")
        _render_bucket_status(b, exp_days)
        _render_prefix_table(b.name)
    except Exception as e:
        console.print(f"[bold red]Error configuring GCS bucket:[/bold red] {e}")
        console.print("[yellow]Ensure you have authenticated to GCP using 'make auth' or 'gcloud auth application-default login'.[/yellow]")
        sys.exit(1)

def _render_bucket_status(bucket, configured_days: int):
    """Renders bucket configuration details."""
    table = Table(title="📦 GCS Bucket Properties & Lifecycle Rules", border_style="cyan")
    table.add_column("Property", style="bold")
    table.add_column("Configuration Value", style="green")

    table.add_row("Bucket Name", bucket.name)
    table.add_row("GCP Project", bucket.project_number or settings.project_id)
    table.add_row("Location", bucket.location)
    table.add_row("Storage Class", bucket.storage_class)
    
    ubla = getattr(bucket.iam_configuration, "uniform_bucket_level_access_enabled", False)
    table.add_row("Uniform Bucket-Level Access", "[green]Enabled[/green]" if ubla else "[yellow]Disabled[/yellow]")

    # Lifecycle rules check
    rules = list(bucket.lifecycle_rules or [])
    delete_rules = [r for r in rules if r.get("action", {}).get("type") == "Delete"]
    if delete_rules:
        age = delete_rules[0].get("condition", {}).get("age", "N/A")
        lifecycle_status = f"[green]Active (Delete objects older than {age} days)[/green]"
    else:
        lifecycle_status = "[yellow]No Delete Expiration Rule (Indefinite Retention)[/yellow]"
    table.add_row("Lifecycle Expiration Policy", lifecycle_status)
    table.add_row("Configured Env Flag", f"GCS_OBJECT_EXPIRATION_DAYS={configured_days}")

    console.print(table)
    console.print()

def _render_prefix_table(bucket_name: str):
    """Renders prefix key layout and sample IAM CEL condition expressions."""
    iam_conditions = GCSStorageClient.get_iam_condition_examples(bucket_name)

    table = Table(title="🔐 Audience Prefix Routing & IAM Condition Access Control", border_style="green")
    table.add_column("Audience", style="bold")
    table.add_column("Prefix Key", style="cyan")
    table.add_column("Personas Mapped", style="magenta")
    table.add_column("IAM CEL Condition Expression", style="dim")

    table.add_row(
        "External Customers",
        "external/audio/",
        "Retail Banking Guide\nWealth & Market Advisor",
        iam_conditions["external_public"]
    )
    table.add_row(
        "Internal Employees",
        "internal/audio/",
        "Regulatory & Policy Officer\nEmployee Enablement",
        iam_conditions["internal_restricted"]
    )
    table.add_row(
        "Both (Shared)",
        "shared/audio/",
        "Fraud & Security Alert",
        iam_conditions["shared_alerts"]
    )

    console.print(table)
    ext_cond = iam_conditions["external_public"]
    example_cmd = (
        f"gcloud storage buckets add-iam-policy-binding gs://{bucket_name} \\\n"
        f'  --member="group:bank-customers@example.com" \\\n'
        f'  --role="roles/storage.objectViewer" \\\n'
        f"  --condition='expression={ext_cond},title=\"External Audio Only\"'"
    )
    console.print(Panel(
        f"[bold]Tip for GCP IAM Policy Binding:[/bold]\n"
        f"You can attach conditional access roles to Service Accounts or Groups using:\n"
        f"[cyan]{example_cmd}[/cyan]",
        title="💡 Access Control Best Practice",
        border_style="yellow"
    ))

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
CLI Quickstart Runner for Knowledge Article to Speech & Multimodal Evaluation.
Generates Gemini Generative Speech, stores MP3 in GCS, and audits quality via Gemini Judge.
"""
import sys
import os
import time
import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.config import settings
from src.ai.generator import GeminiAudioGenerator
from src.ai.judge import MultimodalAudioJudge
from src.storage.gcs_client import GCSStorageClient
from src.ai.personas import PERSONAS
from src.db.models import JobRecord
from src.db.repository import get_job_repository
from src.ai.cost_calculator import TokenCostCalculator

console = Console()

@click.command()
@click.option("--text", "-t", default=None, help="Pasted raw article text or markdown.")
@click.option("--file", "-f", default=None, type=click.Path(exists=True), help="Path to article text/markdown file.")
@click.option("--persona", "-p", default="Retail Banking Guide", type=click.Choice(list(PERSONAS.keys())), help="Financial services voice persona.")
@click.option("--skip-judge", is_flag=True, default=False, help="Skip multimodal LLM evaluation.")
@click.option("--local-out", "-o", default=None, help="Optional local path to save the generated .mp3 file.")
@click.option("--bucket", "-b", default=None, help="Override GCS bucket name.")
def main(text, file, persona, skip_judge, local_out, bucket):
    """Knowledge-to-Speech & Multimodal LLM-as-a-Judge CLI Runner."""
    console.print(Panel.fit(
        "[bold cyan]🎙️ Knowledge Article to Speech & Multimodal Judge Platform[/bold cyan]\n"
        f"[dim]Project: {settings.project_id} | Voice: {settings.voice_model} | Judge: {settings.judge_model}[/dim]",
        border_style="cyan"
    ))

    # 1. Resolve Input Text
    article_text = ""
    if text:
        article_text = text.strip()
    elif file:
        with open(file, "r", encoding="utf-8") as f:
            article_text = f.read().strip()
    else:
        console.print("[yellow]No text or file provided. Using default sample article...[/yellow]")
        sample_path = os.path.join(os.path.dirname(__file__), "samples", "sample_article.md")
        if os.path.exists(sample_path):
            with open(sample_path, "r", encoding="utf-8") as f:
                article_text = f.read().strip()
        else:
            console.print("[bold red]Error:[/bold red] Please provide text via --text or --file.")
            sys.exit(1)

    word_count = len(article_text.split())
    char_count = len(article_text)
    console.print(f"📖 [bold]Input Article:[/bold] {word_count} words ({char_count} characters) | Persona: [magenta]{persona}[/magenta]\n")

    # 2. Synthesize Speech via Gemini Generative Voice
    generator = GeminiAudioGenerator()
    gcs_client = GCSStorageClient(bucket_name=bucket)

    t0 = time.time()
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        task1 = progress.add_task("[cyan]Generating speech with Gemini Generative Voice...", total=None)
        try:
            gen_result = generator.generate_speech(
                text=article_text,
                persona_name=persona
            )
            synth_time = time.time() - t0
            progress.update(task1, description=f"[green]✓ Speech generated in {synth_time:.2f}s ({len(gen_result.audio_bytes) / 1024:.1f} KB)")
        except Exception as e:
            progress.update(task1, description=f"[red]✗ Speech generation failed: {e}")
            console.print(f"\n[bold red]Error during synthesis:[/bold red] {e}")
            sys.exit(1)

        # 3. Upload Audio to GCS with Audience Prefix Routing
        task2 = progress.add_task("[cyan]Uploading MP3 to Google Cloud Storage...", total=None)
        prefix = gcs_client.get_prefix_for_persona(persona_name=persona)
        try:
            gcs_uri, signed_url = gcs_client.upload_audio_bytes(
                audio_bytes=gen_result.audio_bytes,
                job_id=gen_result.job_id,
                persona_name=persona,
                content_type="audio/mpeg",
                metadata={"persona": persona, "word_count": str(word_count)}
            )
            progress.update(task2, description=f"[green]✓ Audio stored under prefix [{prefix}/] at {gcs_uri}")
        except Exception as e:
            progress.update(task2, description=f"[red]✗ GCS upload failed: {e}")
            console.print(f"\n[bold red]GCS Error:[/bold red] {e}")
            bucket_name = gcs_client.bucket_name or settings.gcs_bucket_name or "tts-bank-audio"
            gcs_uri = f"gs://{bucket_name}/{prefix}/{gen_result.job_id}.mp3"
            signed_url = None

    # Save local copy if requested
    if local_out:
        with open(local_out, "wb") as f:
            f.write(gen_result.audio_bytes)
        console.print(f"💾 [green]Saved local MP3 to:[/green] {local_out}")

    persona_obj = PERSONAS.get(persona)
    audience = persona_obj.audience if persona_obj else "External Customers"
    retention_info = f"{settings.gcs_object_expiration_days} days" if settings.gcs_object_expiration_days > 0 else "Indefinite (no expiration)"

    console.print(Panel(
        f"[bold]Job ID:[/bold] {gen_result.job_id}\n"
        f"[bold]Target Audience:[/bold] [yellow]{audience}[/yellow]\n"
        f"[bold]GCS Prefix Key:[/bold] [cyan]{prefix}/[/cyan]\n"
        f"[bold]GCS Audio URI:[/bold] [link={gcs_uri}]{gcs_uri}[/link]\n"
        f"[bold]Lifecycle Retention:[/bold] {retention_info}\n"
        f"[bold]Signed URL (60m):[/bold] {signed_url or 'N/A'}\n"
        f"[bold]Audio Format:[/bold] MP3 24kHz @ 320kbps\n"
        f"[bold]Synthesis Latency:[/bold] {synth_time:.2f} seconds",
        title="🎉 Audio Artifact Ready",
        border_style="green"
    ))

    # 4. Multimodal LLM-as-a-Judge Quality Audit
    if not skip_judge:
        judge = MultimodalAudioJudge()
        t1 = time.time()
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
            task3 = progress.add_task("[cyan]Running Gemini Multimodal Quality Audit on GCS URI...", total=None)
            try:
                eval_result = judge.evaluate_audio_gcs(
                    gcs_audio_uri=gcs_uri,
                    reference_text=article_text,
                    persona_name=persona
                )
                judge_time = time.time() - t1
                progress.update(task3, description=f"[green]✓ Multimodal audit completed in {judge_time:.2f}s")
            except Exception as e:
                progress.update(task3, description=f"[red]✗ Multimodal evaluation failed: {e}")
                console.print(f"\n[bold red]Judge Evaluation Error:[/bold red] {e}")
                return

        # Render Quality Scorecard Table
        table = Table(title=f"⚖️ Multimodal Quality Scorecard (Overall Score: {eval_result.overall_score}/5.0)", border_style="cyan")
        table.add_column("Rubric Dimension", style="bold")
        table.add_column("Weight", justify="center")
        table.add_column("Score", justify="center")
        table.add_column("Rationale", style="dim")

        for name, metric in eval_result.metrics.items():
            color = "green" if metric.score >= 4.0 else ("yellow" if metric.score >= 3.0 else "red")
            table.add_row(
                name.replace("_", " ").title(),
                f"{int(metric.weight * 100)}%",
                f"[{color}]{metric.score:.1f} / 5.0[/{color}]",
                metric.rationale
            )

        console.print(table)

        # Render Actionable Feedback
        feedback_items = []
        if eval_result.overall_reasoning:
            feedback_items.append(f"[bold]Overall Score Rationale:[/bold]\n{eval_result.overall_reasoning}\n")
        if eval_result.actionable_feedback:
            feedback_items.append("[bold]Actionable Recommendations:[/bold]\n" + "\n".join([f"• {f}" for f in eval_result.actionable_feedback]))
        
        status_badge = "[bold green]PASSED QUALITY GATE[/bold green]" if eval_result.passed_rubric else "[bold red]NEEDS REVISION[/bold red]"
        console.print(Panel(
            f"[bold]Quality Verdict:[/bold] {status_badge}\n\n" + "\n".join(feedback_items),
            title="📝 LLM Judge Diagnostic Feedback & Reasoning",
            border_style="yellow"
        ))

    # 5. Token Usage & Cost Telemetry
    eval_usage = getattr(eval_result, "usage_metadata", None) if not skip_judge else None
    token_usage, cost = TokenCostCalculator.calculate_pipeline_cost(
        text=article_text,
        duration_seconds=gen_result.duration_seconds,
        tts_usage_metadata=getattr(gen_result, "usage_metadata", None),
        judge_usage_metadata=eval_usage,
        tts_model=settings.voice_model,
        judge_model=settings.judge_model if not skip_judge else ""
    )

    cost_table = Table(title="📊 Token Usage & Cost Telemetry", border_style="magenta")
    cost_table.add_column("Pipeline Stage", style="bold")
    cost_table.add_column("Model", style="cyan")
    cost_table.add_column("Input Tokens", justify="right")
    cost_table.add_column("Output Tokens", justify="right")
    cost_table.add_column("Estimated Cost", justify="right", style="green")

    cost_table.add_row(
        "Speech Generation",
        settings.voice_model,
        f"{token_usage.input_text_tokens:,}",
        f"{token_usage.audio_output_tokens:,} (audio)",
        f"${cost.tts_cost_usd:.6f}"
    )
    if not skip_judge:
        cost_table.add_row(
            "Multimodal Judge",
            settings.judge_model,
            f"{token_usage.judge_input_tokens:,}",
            f"{token_usage.judge_output_tokens:,}",
            f"${cost.judge_cost_usd:.6f}"
        )
    cost_table.add_row(
        "[bold]Total Pipeline[/bold]",
        "-",
        "-",
        f"[bold]{token_usage.total_tokens:,}[/bold]",
        f"[bold green]${cost.total_cost_usd:.6f} USD[/bold green]"
    )
    console.print(cost_table)

    # 6. Persist Job Record to Repository (Cloud Firestore / SQLite)
    repo = get_job_repository()
    job_record = JobRecord(
        job_id=gen_result.job_id,
        persona=persona,
        audience=audience,
        voice_name=persona_obj.voice_name if persona_obj else "Sulafat",
        article_title=article_text.split("\n")[0][:80].strip("#* "),
        transcript=article_text,
        word_count=word_count,
        char_count=char_count,
        gcs_uri=gcs_uri,
        signed_url=signed_url,
        audio_format="MP3 24kHz @ 320kbps",
        duration_seconds=gen_result.duration_seconds,
        synthesis_latency_sec=synth_time,
        status="COMPLETED",
        token_usage=token_usage,
        cost=cost,
        overall_score=eval_result.overall_score if not skip_judge else None,
        passed_rubric=eval_result.passed_rubric if not skip_judge else None,
        rubric_metrics={name: metric.model_dump() for name, metric in eval_result.metrics.items()} if not skip_judge else None,
        actionable_feedback=eval_result.actionable_feedback if not skip_judge else None,
        judge_model=settings.judge_model if not skip_judge else None,
        judge_latency_sec=judge_time if not skip_judge else None
    )
    repo.save_job(job_record)
    console.print(f"🗄️ [dim]Job tracking saved to repository ([bold]{type(repo).__name__}[/bold]) for ID: [cyan]{gen_result.job_id}[/cyan][/dim]\n")

if __name__ == "__main__":
    main()

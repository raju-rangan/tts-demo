"""Gemini Generative AI Audio Generator aligned with official Google AI Speech Generation API."""
import io
import os
import re
import time
import uuid
import wave
import logging
import math
import array
import base64
import subprocess
from dataclasses import dataclass
from typing import Optional, Tuple, Any, List
from google import genai
from google.genai import types

# Optional pydub import with fallback for Python 3.13+ (PEP 594 audioop removal)
try:
    from pydub import AudioSegment
except Exception:
    AudioSegment = None

# Optional lameenc for fast in-memory MP3 encoding (zero OS-level dependencies, Cloud Run optimized)
try:
    import lameenc
except Exception:
    lameenc = None

from pydantic import BaseModel, Field
from src.config import settings
from src.ai.personas import get_persona, VoicePersona

logger = logging.getLogger(__name__)

class PodcastTurn(BaseModel):
    speaker: str = Field(..., description="Name of the speaking co-host (e.g. Joe, Jane, Alex, Maya)")
    text: str = Field(..., description="The spoken dialogue line for this turn, without stage directions or brackets")
    style: Optional[str] = Field(default="natural and conversational", description="Speaking style, emotion, or delivery nuance")

class PodcastScript(BaseModel):
    title: str = Field(..., description="An engaging, catchy podcast episode title")
    turns: List[PodcastTurn] = Field(..., min_length=2, description="Ordered dialogue turns between the two co-hosts")

@dataclass
class AggregatedUsageMetadata:
    prompt_token_count: int = 0
    candidates_token_count: int = 0
    total_token_count: int = 0

@dataclass
class GenerationResult:
    job_id: str
    audio_bytes: bytes
    audio_format: str
    duration_seconds: float
    persona_used: str
    model_used: str
    usage_metadata: Optional[Any] = None
    transcript: Optional[str] = None
    title: Optional[str] = None


def split_text_into_chunks(text: str, target_words: Optional[int] = None) -> List[str]:
    """
    Splits text into cohesive, complete-sentence units targeting ~400 words per chunk.
    Never cuts in the middle of a sentence, bullet point, or paragraph.
    Preserves intra-paragraph sentence spaces and inter-paragraph line breaks.
    """
    limit = target_words or settings.tts_chunk_word_limit
    words = len(text.split())
    if words <= limit:
        return [text]

    # Split into paragraphs first to preserve document structural integrity
    paragraphs = text.split("\n\n")
    units: List[Tuple[str, bool]] = []
    for p in paragraphs:
        p_stripped = p.strip()
        if not p_stripped:
            continue
        # Split paragraph into sentences on terminal punctuation (.?!) followed by space and capital/quote/number
        sentences = re.split(r'(?<=[.?!])\s+(?=[A-Z0-9\"\'\‘\“])', p_stripped)
        for idx, s in enumerate(sentences):
            s_clean = s.strip()
            if s_clean:
                units.append((s_clean, idx == 0))

    chunks: List[str] = []
    current_units: List[Tuple[str, bool]] = []
    current_word_count = 0

    for text_unit, is_new_para in units:
        unit_words = len(text_unit.split())
        # If adding this unit exceeds target and we already have accumulated sentences
        if (current_word_count + unit_words > limit) and current_word_count > 0:
            chunks.append(_join_chunk_units(current_units))
            current_units = [(text_unit, True)]  # Start new chunk clean
            current_word_count = unit_words
        else:
            current_units.append((text_unit, is_new_para))
            current_word_count += unit_words

    if current_units:
        chunks.append(_join_chunk_units(current_units))

    return chunks


def _join_chunk_units(units: List[Tuple[str, bool]]) -> str:
    """Reconstructs text units into formatted text with appropriate spacing."""
    parts = []
    for text_unit, is_new_para in units:
        if not parts:
            parts.append(text_unit)
        elif is_new_para:
            parts.append("\n\n" + text_unit)
        else:
            parts.append(" " + text_unit)
    return "".join(parts)


def normalize_chunk_rms(pcm_bytes: bytes, target_rms: float = 3000.0) -> bytes:
    """
    Normalizes 24kHz 16-bit signed mono PCM samples to an identical target RMS loudness.
    Eliminates perceptual volume jumps between independently generated multi-turn chunks.
    Includes soft limiting to prevent digital clipping at +/-32767.
    """
    if not pcm_bytes:
        return pcm_bytes

    samples = array.array("h", pcm_bytes)
    if len(samples) == 0:
        return pcm_bytes

    sum_squares = sum(s * s for s in samples)
    current_rms = math.sqrt(sum_squares / len(samples))

    if current_rms < 100.0:  # Avoid amplifying silent audio
        return pcm_bytes

    gain = target_rms / current_rms
    # Restrict gain adjustment range to avoid extreme amplification or suppression
    gain = max(0.4, min(2.5, gain))

    for i in range(len(samples)):
        scaled = int(samples[i] * gain)
        if scaled > 32767:
            scaled = 32767
        elif scaled < -32768:
            scaled = -32768
        samples[i] = scaled

    return samples.tobytes()


def apply_micro_fades(pcm_bytes: bytes, fade_samples: int = 960) -> bytes:
    """
    Applies a smooth raised-cosine fade-in at the start and fade-out at the end
    of a 16-bit mono PCM chunk (960 samples = 40ms at 24kHz).
    Prevents DC-offset clicks and smooths ambient noise-floor transitions between turns.
    """
    if not pcm_bytes:
        return pcm_bytes

    samples = array.array("h", pcm_bytes)
    total_samples = len(samples)
    if total_samples < fade_samples * 2:
        return pcm_bytes

    # Raised cosine fade-in: 0.5 * (1 - cos(pi * i / fade_samples))
    for i in range(fade_samples):
        multiplier = 0.5 * (1.0 - math.cos(math.pi * i / fade_samples))
        samples[i] = int(samples[i] * multiplier)

    # Raised cosine fade-out: 0.5 * (1 + cos(pi * (fade_samples - 1 - i) / fade_samples))
    for i in range(fade_samples):
        idx = total_samples - fade_samples + i
        multiplier = 0.5 * (1.0 + math.cos(math.pi * i / fade_samples))
        samples[idx] = int(samples[idx] * multiplier)

    return samples.tobytes()


class GeminiAudioGenerator:
    """Synthesizes human-like spoken audio from article text using Gemini TTS API."""

    def __init__(self, project_id: Optional[str] = None, location: Optional[str] = None, model: Optional[str] = None):
        self.project_id = project_id or settings.project_id
        self.location = location or settings.location
        # Default to official Gemini TTS model if not explicitly overridden
        self.model = model or os.getenv("GEMINI_VOICE_MODEL", "gemini-3.1-flash-tts-preview")
        self.multi_speaker_model = os.getenv("GEMINI_MULTI_SPEAKER_VOICE_MODEL", self.model)
        self.podcast_script_model = os.getenv("GEMINI_PODCAST_SCRIPT_MODEL", settings.judge_model)
        self._client: Optional[genai.Client] = None

    @property
    def client(self) -> genai.Client:
        """Lazy-initialized Google Gen AI Client."""
        if self._client is None:
            api_key = os.getenv("GEMINI_API_KEY")
            http_opts = types.HttpOptions(timeout=600000)  # 10 minute timeout for long audio generation
            if api_key:
                self._client = genai.Client(api_key=api_key, http_options=http_opts)
            else:
                self._client = genai.Client(
                    vertexai=bool(self.project_id and self.project_id != "tts-demo-project"),
                    project=self.project_id if self.project_id != "tts-demo-project" else None,
                    location=self.location if self.project_id != "tts-demo-project" else None,
                    http_options=http_opts
                )
        return self._client

    def _generate_single_chunk(
        self,
        chunk_text: str,
        persona: VoicePersona,
        job_id: str,
        chunk_index: int = 1,
        total_chunks: int = 1,
        voice_customization: Optional[str] = None,
        speed: float = 1.0,
        critique_feedback: Optional[str] = None
    ) -> Tuple[bytes, Optional[Any]]:
        """
        Executes single-turn Gemini TTS synthesis for a text chunk.
        Returns raw PCM bytes (24kHz 16-bit mono) and usage_metadata.
        """
        turn_label = f" (turn {chunk_index}/{total_chunks})" if total_chunks > 1 else ""
        logger.info(f"Synthesizing{turn_label} for job {job_id} using persona '{persona.name}', voice '{persona.voice_name}', speed {speed:.2f}x | Critique: {bool(critique_feedback)}")

        turn_context = ""
        if total_chunks > 1:
            if chunk_index == 1:
                turn_context = (
                    "AUDIO CONTINUITY DIRECTIVE (PART 1 OF MULTI-PART RECORDING):\n"
                    f"This is Part 1 of {total_chunks}. Deliver speech with a clean, neutral, dry studio acoustic baseline and consistent vocal energy.\n\n"
                )
            else:
                turn_context = (
                    f"AUDIO CONTINUITY DIRECTIVE (PART {chunk_index} OF {total_chunks}):\n"
                    "This is a direct, seamless continuation of the previous section. You MUST maintain the exact same pitch baseline, "
                    "vocal energy, speaking cadence, microphone distance, and dry studio acoustic space so this segment splices seamlessly into the preceding recording.\n\n"
                )

        speed_block = ""
        if abs(speed - 1.0) >= 0.05:
            if speed < 0.95:
                speed_block = (
                    f"SPEED & PACING DIRECTIVE (Delivery Rate: {speed:.2f}x):\n"
                    f"Deliver the speech at a deliberate, measured, and unhurried pace ({speed:.2f}x standard tempo). "
                    "Pause naturally between clauses, complex financial figures, and regulatory disclosures to maximize clarity and customer comprehension.\n\n"
                )
            elif speed <= 1.30:
                speed_block = (
                    f"SPEED & PACING DIRECTIVE (Delivery Rate: {speed:.2f}x):\n"
                    f"Deliver the speech at a brisk, energetic speaking rate ({speed:.2f}x standard tempo). "
                    "Narrate with swift transitions between sentences while retaining crisp, professional enunciation.\n\n"
                )
            else:
                speed_block = (
                    f"SPEED & PACING DIRECTIVE (Delivery Rate: {speed:.2f}x):\n"
                    f"Deliver the speech at a high-tempo, accelerated rate ({speed:.2f}x standard tempo), suitable for rapid regulatory disclosures and fast-paced bulletins. "
                    "Maintain rapid, fluid delivery with minimal pauses while ensuring articulation remains distinct.\n\n"
                )

        script_adherence_block = (
            "VERBATIM SCRIPT ADHERENCE DIRECTIVE:\n"
            "- Teleprompter Mode: You are reading from an electronic broadcast teleprompter. Read ONLY the text enclosed inside <teleprompter_script> tags aloud from beginning to end.\n"
            "- 100% Word-for-Word Fidelity: You MUST read the reference text enclosed inside <teleprompter_script> tags exactly as written. Do NOT omit, skip, summarize, paraphrase, or add any words.\n"
            "- Titles & Headlines: If the text begins with a title or headline (including markdown '#' or article titles), you MUST clearly read the title aloud before narrating the body text.\n"
            "- Section Headers & Bullet Points: Speak every section header and every numbered or bulleted list item completely in sequence. Do not skip list items.\n"
            "- Exact Left-to-Right Word Order: Speak words and acronyms in the exact sequence they appear in the text. For example, 'Annual Percentage Yield (APY)' must be read in that exact left-to-right order ('Annual Percentage Yield, A-P-Y'). NEVER invert the order (e.g. do NOT say 'APY, Annual Percentage Yield').\n"
            "- Parenthetical Expressions: Read all parenthetical expressions, acronyms, and expansions (e.g., '(CDs)', '(HYSA)', '(FDIC)', '(APR)') out loud as part of the natural spoken narrative.\n"
            "- No Retroactive or Unscripted Injections: NEVER add abbreviations or terms into headers or sentences where they are not written (e.g. if a header says 'Certificates of Deposit', do NOT insert 'CDs' unless '(CDs)' is explicitly written in that header).\n"
            "- Exact Product Names & Singular/Plural Integrity: Never substitute compound terms (e.g. 'High-Yield' must be read as 'high yield', NEVER 'high quality'). Preserve singular vs plural forms precisely ('Certificates of Deposit', not 'Deposits'; 'HYSAs', not 'HYSA').\n"
            "- No Conversational Additions: Do not add conversational lead-ins (e.g., 'Welcome to...', 'Sure, here is...'), improvised transitions, or unscripted concluding remarks.\n\n"
        )

        customization_block = ""
        if voice_customization and voice_customization.strip():
            customization_block = (
                "USER VOICE CUSTOMIZATION & DELIVERY DIRECTIVES:\n"
                "Strictly adhere to the following vocal style, tone, pacing, and emotional delivery instructions:\n"
                f"\"{voice_customization.strip()}\"\n\n"
            )

        remediation_block = ""
        if critique_feedback and critique_feedback.strip():
            remediation_block = (
                "======================================================================\n"
                "AUDITOR CRITIQUE & MANDATORY DEFECT REMEDIATION (RE-TAKE / RETRY):\n"
                "The previous recording of this transcript was audited and flagged for defects.\n"
                "You are re-recording this audio. Strictly remediate the auditor's findings:\n"
                f"{critique_feedback.strip()}\n"
                "======================================================================\n\n"
            )

        full_prompt = (
            f"SYSTEM DIRECTIVES & PERSONA GUIDELINES:\n{persona.system_instruction}\n\n"
            f"{speed_block}"
            f"{script_adherence_block}"
            f"{customization_block}"
            f"{remediation_block}"
            f"{turn_context}"
            f"INSTRUCTION:\nYou are reading from an electronic broadcast teleprompter. Read ONLY the text enclosed inside <teleprompter_script> tags aloud from beginning to end with 100% exact word-for-word accuracy. Adhere strictly to your assigned persona, tempo, and financial pronunciation directives:\n\n"
            f"<teleprompter_script>\n{chunk_text}\n</teleprompter_script>"
        )

        max_attempts = 2
        for attempt in range(1, max_attempts + 1):
            try:
                speech_config = types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=persona.voice_name
                        )
                    )
                )
                config = types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=speech_config,
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
                )
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=full_prompt,
                    config=config
                )
                raw_audio_bytes, _ = self._extract_audio_from_response(response)
                usage_metadata = getattr(response, "usage_metadata", None)
                return raw_audio_bytes, usage_metadata
            except Exception as e:
                if attempt < max_attempts:
                    logger.warning(f"client.models.generate_content attempt {attempt}/{max_attempts} failed{turn_label}: {e}. Retrying with backoff in 3.0s...")
                    time.sleep(3.0)
                else:
                    logger.error(f"client.models.generate_content failed{turn_label} after {max_attempts} attempts: {e}", exc_info=True)
                    raise RuntimeError(f"Could not generate audio using model '{self.model}'{turn_label} ({e}). Verify Vertex AI quota and model availability.")

    def generate_podcast_script(
        self,
        text: str,
        persona: VoicePersona,
        director_notes: Optional[str] = None,
        job_id: Optional[str] = None
    ) -> PodcastScript:
        """
        Uses Gemini to generate an engaging, balanced 2-person podcast dialogue script
        based on the source text, the selected co-host persona profiles, and director's notes.
        """
        job_label = f"[{job_id}] " if job_id else ""
        logger.info(f"▶ {job_label}Generating 2-person podcast script for persona '{persona.name}' using model '{self.podcast_script_model}'...")

        speakers = persona.speakers or (
            {"speaker": "Joe", "voice_name": "Puck", "gender": "male", "role": "Host"},
            {"speaker": "Jane", "voice_name": "Kore", "gender": "female", "role": "Co-host"},
        )
        s1 = speakers[0]
        s2 = speakers[1]

        customization_section = ""
        if director_notes and director_notes.strip():
            customization_section = (
                "======================================================================\n"
                "DIRECTOR'S NOTES & PODCAST CUSTOMIZATION DIRECTIVES (MANDATORY):\n"
                "The director has provided the following specific instructions on what the podcast must cover, "
                "the host dynamics, tone, topics to emphasize, or questions to address:\n"
                f"\"{director_notes.strip()}\"\n"
                "You MUST ensure these directives are prominently incorporated into the discussion.\n"
                "======================================================================\n\n"
            )

        prompt = f"""
You are an expert executive podcast producer and scriptwriter for a premier financial services show.
Your task is to transform the provided source document into a vibrant, natural, 2-person podcast conversation between two knowledgeable co-hosts: {s1['speaker']} and {s2['speaker']}.

CO-HOST PROFILES:
- Host 1: {s1['speaker']} ({s1.get('gender', 'host')}, Voice: {s1['voice_name']}) - Lead conversational host who introduces topics, shares relatable observations, and asks engaging questions.
- Host 2: {s2['speaker']} ({s2.get('gender', 'co-host')}, Voice: {s2['voice_name']}) - Insightful expert co-host who provides clarity, explains analytical trade-offs, and breaks down complex financial concepts.

{customization_section}
PODCAST SCRIPT GUIDELINES:
1. Dynamic Chemistry: The conversation must feel authentic and engaging—hosts should react with genuine interest (e.g. "That's a great point, Joe", "Exactly, Jane"), bounce ideas back and forth, and explain concepts using clear real-world examples.
2. Grounded Accuracy: Faithfully represent all key facts, numbers, interest rates, FDIC limits, and policies mentioned in the source document.
3. Natural Turn Length: Keep each turn relatively concise (typically 1 to 3 sentences per turn). Avoid unbroken monologues. Alternate between {s1['speaker']} and {s2['speaker']}. Aim for approximately 8 to 14 dialogue turns.
4. Vocal Style: For each turn, provide a delivery style in the 'style' field (e.g., "cheerful and friendly", "thoughtful and measured", "inquisitive and energetic", "reassuring and warm", "curious").
5. Verbatim Purity: In the 'text' field of each turn, include ONLY the words that the speaker actually utters aloud. Do NOT include stage directions in asterisks or brackets (e.g. no '(laughs)' or '[chuckles]').

SOURCE DOCUMENT TO COVER:
{text}
""".strip()

        try:
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=PodcastScript,
                system_instruction=persona.system_instruction,
                temperature=0.7,
            )
            response = self.client.models.generate_content(
                model=self.podcast_script_model,
                contents=prompt,
                config=config
            )
            raw_text = response.text or ""
            script = PodcastScript.model_validate_json(raw_text)
            logger.info(f"✓ {job_label}Generated podcast script '{script.title}' with {len(script.turns)} turns")
            return script
        except Exception as e:
            logger.error(f"✗ {job_label}Failed to generate podcast script with model '{self.podcast_script_model}': {e}", exc_info=True)
            # Resilient fallback: construct basic 2-turn script if model call fails
            return PodcastScript(
                title="Financial Insights Podcast",
                turns=[
                    PodcastTurn(speaker=s1['speaker'], text=f"Welcome to today's financial briefing. Let's discuss this article: {text[:200]}...", style="cheerful and friendly"),
                    PodcastTurn(speaker=s2['speaker'], text=f"Thanks {s1['speaker']}. That's a critical topic for banking customers to understand.", style="calm and relaxed"),
                ]
            )

    def _generate_multi_speaker_speech(
        self,
        script: PodcastScript,
        persona: VoicePersona,
        job_id: str,
        speed: float = 1.0,
        critique_feedback: Optional[str] = None,
        progress_callback: Optional[Any] = None
    ) -> GenerationResult:
        """
        Synthesizes multi-speaker audio from a PodcastScript using Gemini's official
        multi_speaker_voice_config and speech_metadata on parts.
        """
        speakers = persona.speakers or (
            {"speaker": "Joe", "voice_name": "Puck", "gender": "male", "role": "Host"},
            {"speaker": "Jane", "voice_name": "Kore", "gender": "female", "role": "Co-host"},
        )
        total_turns = len(script.turns)
        logger.info(f"▶ [{job_id}] Synthesizing multi-speaker podcast audio ({total_turns} turns) using {speakers[0]['speaker']} ({speakers[0]['voice_name']}) and {speakers[1]['speaker']} ({speakers[1]['voice_name']}) on model '{self.multi_speaker_model}'...")

        if progress_callback:
            progress_callback(
                stage="SYNTHESIZING",
                message=f"Synthesizing multi-speaker podcast audio ({total_turns} dialogue turns)...",
                current_turn=1,
                total_turns=total_turns
            )

        # Batch turns in groups of up to 12 turns per request to guarantee high-fidelity audio
        batch_size = 12
        batches = [script.turns[i:i + batch_size] for i in range(0, total_turns, batch_size)]
        pcm_segments = []
        total_prompt_tokens = 0
        total_candidates_tokens = 0
        has_real_usage = False

        for batch_idx, batch in enumerate(batches, start=1):
            if len(batches) > 1 and progress_callback:
                progress_callback(
                    stage="SYNTHESIZING",
                    message=f"Synthesizing podcast segment {batch_idx}/{len(batches)} ({len(batch)} turns)...",
                    current_turn=batch_idx,
                    total_turns=len(batches)
                )

            # Build content parts with text and speech_metadata
            parts = []
            for turn in batch:
                turn_style = turn.style or "natural and conversational"
                if abs(speed - 1.0) >= 0.05:
                    if speed < 0.95:
                        turn_style += ", deliberate and unhurried pacing"
                    elif speed > 1.05:
                        turn_style += ", brisk and energetic pacing"

                parts.append({
                    "text": turn.text,
                    "speech_metadata": {
                        "speaker": turn.speaker,
                        "style": turn_style,
                    }
                })

            contents = [{
                "role": "user",
                "parts": parts,
            }]

            speech_config = types.SpeechConfig(
                multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                    speaker_voice_configs=[
                        types.SpeakerVoiceConfig(
                            speaker=s["speaker"],
                            voice_config=types.VoiceConfig(
                                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                    voice_name=s["voice_name"]
                                )
                            )
                        )
                        for s in speakers
                    ]
                )
            )

            config = types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=speech_config,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
            )

            max_attempts = 2
            raw_audio = None
            usage = None
            for attempt in range(1, max_attempts + 1):
                try:
                    response = self.client.models.generate_content(
                        model=self.multi_speaker_model,
                        contents=contents,
                        config=config
                    )
                    raw_audio, _ = self._extract_audio_from_response(response)
                    usage = getattr(response, "usage_metadata", None)
                    break
                except Exception as e:
                    if attempt < max_attempts:
                        logger.warning(f"Multi-speaker generate_content attempt {attempt}/{max_attempts} failed: {e}. Retrying in 3s...")
                        time.sleep(3.0)
                    else:
                        logger.error(f"Multi-speaker generate_content failed after {max_attempts} attempts: {e}", exc_info=True)
                        raise RuntimeError(f"Could not generate multi-speaker audio using model '{self.multi_speaker_model}': {e}")

            # Check if returned audio is a WAV container (starts with RIFF) or raw PCM
            if raw_audio.startswith(b"RIFF"):
                try:
                    with wave.open(io.BytesIO(raw_audio), "rb") as wf:
                        raw_pcm = wf.readframes(wf.getnframes())
                except Exception as we:
                    logger.warning(f"Could not read WAV container from response: {we}, falling back to raw bytes")
                    raw_pcm = raw_audio[44:] if len(raw_audio) > 44 else raw_audio
            else:
                raw_pcm = raw_audio

            # Apply DSP mastering (RMS leveling + raised-cosine micro-fades)
            mastered_pcm = apply_micro_fades(normalize_chunk_rms(raw_pcm))
            pcm_segments.append(mastered_pcm)

            if usage:
                p_tokens = getattr(usage, "prompt_token_count", 0) or 0
                c_tokens = getattr(usage, "candidates_token_count", 0) or 0
                if p_tokens > 0 or c_tokens > 0:
                    has_real_usage = True
                    total_prompt_tokens += p_tokens
                    total_candidates_tokens += c_tokens

        if progress_callback:
            progress_callback(
                stage="STITCHING",
                message="Mastering & normalizing multi-speaker broadcast audio...",
                current_turn=total_turns,
                total_turns=total_turns
            )

        # Stitch segments together with natural 300ms pause
        pause_samples = int(settings.sample_rate * 0.3)
        pause_bytes = b"\x00" * (pause_samples * 2)
        full_pcm = pause_bytes.join(pcm_segments)

        mp3_bytes, duration_sec = self._transcode_pcm_to_mp3(full_pcm, rate=settings.sample_rate)

        aggregated_usage = None
        if has_real_usage:
            aggregated_usage = AggregatedUsageMetadata(
                prompt_token_count=total_prompt_tokens,
                candidates_token_count=total_candidates_tokens,
                total_token_count=total_prompt_tokens + total_candidates_tokens
            )

        # Build formatted transcript with speaker names
        formatted_script = f"# {script.title}\n\n" + "\n\n".join(
            f"**{turn.speaker}**: {turn.text}" for turn in script.turns
        )

        logger.info(f"✓ [{job_id}] Multi-speaker podcast speech complete: {len(batches)} batch(es), duration {duration_sec:.1f}s, MP3 size {len(mp3_bytes)} bytes")

        return GenerationResult(
            job_id=job_id,
            audio_bytes=mp3_bytes,
            audio_format="audio/mpeg",
            duration_seconds=duration_sec,
            persona_used=persona.name,
            model_used=self.multi_speaker_model,
            usage_metadata=aggregated_usage,
            transcript=formatted_script,
            title=script.title
        )

    def generate_speech(
        self,
        text: str,
        persona_name: str = "Technical Explainer",
        job_id: Optional[str] = None,
        voice_customization: Optional[str] = None,
        speed: float = 1.0,
        critique_feedback: Optional[str] = None,
        progress_callback: Optional[Any] = None
    ) -> GenerationResult:
        """
        Generates spoken audio from text using Gemini TTS API.
        For podcast personas, automatically writes a 2-person dialogue script incorporating
        Director's Notes instructions and synthesizes with Gemini Multi-Speaker TTS.
        For solo articles exceeding the chunk threshold (~400 words), partitions into complete-sentence chunks,
        processes sequentially, applies DSP mastering (RMS leveling + micro-fades), and losslessly stitches audio.
        """
        job_id = job_id or f"job_{uuid.uuid4().hex[:8]}"
        persona = get_persona(persona_name)

        # ---------------- Podcast Multi-Speaker Workflow ----------------
        if getattr(persona, "is_podcast", False):
            if progress_callback:
                progress_callback(
                    stage="CHUNKING",
                    message="Crafting 2-person podcast script from article with Gemini...",
                    current_turn=1,
                    total_turns=1
                )
            script = self.generate_podcast_script(
                text=text,
                persona=persona,
                director_notes=voice_customization,
                job_id=job_id
            )
            return self._generate_multi_speaker_speech(
                script=script,
                persona=persona,
                job_id=job_id,
                speed=speed,
                critique_feedback=critique_feedback,
                progress_callback=progress_callback
            )

        words = len(text.split())

        chunks = split_text_into_chunks(text, target_words=settings.tts_chunk_word_limit)
        total_chunks = len(chunks)

        critique_label = " | Critique Remediation Active" if critique_feedback else ""
        if total_chunks > 1:
            logger.info(f"▶ [{job_id}] Article length ({words} words) exceeds {settings.tts_chunk_word_limit} word threshold. Partitioned into {total_chunks} complete-sentence turns (~{settings.tts_chunk_word_limit} words/turn) | Speed: {speed:.2f}x{critique_label}.")
        else:
            logger.info(f"▶ [{job_id}] Single-turn generation for {words} words using persona '{persona.name}' | Speed: {speed:.2f}x{critique_label}")

        if progress_callback:
            progress_callback(
                stage="CHUNKING",
                message=f"Partitioned transcript into {total_chunks} conversational turn(s)...",
                current_turn=1,
                total_turns=total_chunks
            )

        pcm_segments = []
        total_prompt_tokens = 0
        total_candidates_tokens = 0
        has_real_usage = False

        for idx, chunk in enumerate(chunks, start=1):
            if progress_callback:
                progress_callback(
                    stage="SYNTHESIZING",
                    message=f"Synthesizing turn {idx}/{total_chunks} ({len(chunk.split())} words, {speed:.2f}x)...",
                    current_turn=idx,
                    total_turns=total_chunks
                )
            if idx > 1:
                # Pacing buffer between consecutive turns to prevent rapid burst throttling
                time.sleep(1.0)

            if total_chunks > 1:
                logger.info(f"▶ [{job_id}] Processing turn {idx}/{total_chunks} ({len(chunk.split())} words)...")
            raw_pcm, usage = self._generate_single_chunk(
                chunk_text=chunk,
                persona=persona,
                job_id=job_id,
                chunk_index=idx,
                total_chunks=total_chunks,
                voice_customization=voice_customization,
                speed=speed,
                critique_feedback=critique_feedback
            )

            # Apply DSP mastering: RMS loudness normalization + 40ms raised-cosine micro-fades
            mastered_pcm = apply_micro_fades(normalize_chunk_rms(raw_pcm))
            pcm_segments.append(mastered_pcm)

            if usage:
                p_tokens = getattr(usage, "prompt_token_count", 0) or 0
                c_tokens = getattr(usage, "candidates_token_count", 0) or 0
                if p_tokens > 0 or c_tokens > 0:
                    has_real_usage = True
                    total_prompt_tokens += p_tokens
                    total_candidates_tokens += c_tokens

        # Notify stitching stage
        if progress_callback:
            progress_callback(
                stage="STITCHING",
                message=f"Mastering & stitching {total_chunks} audio turns with 300ms natural pauses...",
                current_turn=total_chunks,
                total_turns=total_chunks
            )

        # Stitch PCM chunks together with a natural 300ms silence pause between turns
        pause_samples = int(settings.sample_rate * 0.3)  # 300ms pause
        pause_bytes = b"\x00" * (pause_samples * 2)  # 16-bit mono = 2 bytes per sample
        full_pcm = pause_bytes.join(pcm_segments)

        # Transcode stitched PCM (24kHz 16-bit mono) to standard broadcast MP3 @ 320kbps
        mp3_bytes, duration_sec = self._transcode_pcm_to_mp3(full_pcm, rate=settings.sample_rate)

        # Build aggregated usage metadata if real tokens were returned
        aggregated_usage = None
        if has_real_usage:
            aggregated_usage = AggregatedUsageMetadata(
                prompt_token_count=total_prompt_tokens,
                candidates_token_count=total_candidates_tokens,
                total_token_count=total_prompt_tokens + total_candidates_tokens
            )

        logger.info(f"✓ [{job_id}] Speech generation complete: {total_chunks} turn(s), duration {duration_sec:.1f}s, MP3 size {len(mp3_bytes)} bytes")

        return GenerationResult(
            job_id=job_id,
            audio_bytes=mp3_bytes,
            audio_format="audio/mpeg",
            duration_seconds=duration_sec,
            persona_used=persona.name,
            model_used=self.model,
            usage_metadata=aggregated_usage
        )


    def _extract_audio_from_response(self, response) -> Tuple[bytes, str]:
        """Extracts audio bytes from generate_content response parts."""
        if not response.candidates:
            prompt_feedback = getattr(response, "prompt_feedback", None)
            raise ValueError(f"No candidates returned by Gemini model. (Prompt feedback: {prompt_feedback})")

        candidate = response.candidates[0]
        finish_reason = getattr(candidate, "finish_reason", None)
        if not candidate.content or not candidate.content.parts:
            safety_ratings = getattr(candidate, "safety_ratings", None)
            raise ValueError(f"No content or audio parts returned by Gemini model (finish_reason: {finish_reason}, safety: {safety_ratings}).")

        for part in candidate.content.parts:
            if hasattr(part, "inline_data") and part.inline_data:
                mime_type = part.inline_data.mime_type or "audio/wav"
                data = part.inline_data.data
                audio_bytes = base64.b64decode(data) if isinstance(data, str) else bytes(data)
                return audio_bytes, mime_type

        raise ValueError(f"No inline audio data found in Gemini response parts (finish_reason: {finish_reason}).")

    def _transcode_pcm_to_mp3(self, raw_pcm_bytes: bytes, rate: int = 24000) -> Tuple[bytes, float]:
        """Transcodes raw 24kHz 16-bit mono PCM into broadcast MP3 @ 320kbps (or fallback WAV container)."""
        if raw_pcm_bytes.startswith(b"RIFF"):
            try:
                with wave.open(io.BytesIO(raw_pcm_bytes), "rb") as wf:
                    rate = wf.getframerate()
                    raw_pcm_bytes = wf.readframes(wf.getnframes())
            except Exception as we:
                logger.warning(f"Could not read WAV header in _transcode_pcm_to_mp3: {we}")
                if len(raw_pcm_bytes) > 44:
                    raw_pcm_bytes = raw_pcm_bytes[44:]

        duration_sec = len(raw_pcm_bytes) / (rate * 2.0)

        # 1. Preferred & Cloud Run Optimized: In-memory pure Python C-extension (lameenc)
        if lameenc is not None:
            try:
                try:
                    kbps = int(settings.bitrate.lower().replace("k", "").strip())
                except (ValueError, AttributeError):
                    kbps = 320

                encoder = lameenc.Encoder()
                encoder.set_channels(1)
                encoder.set_in_sample_rate(rate)
                encoder.set_bit_rate(kbps)
                encoder.set_quality(2)  # High-quality LAME psychoacoustic profile (0=best, 2=high, 7=fast)
                mp3_data = encoder.encode(raw_pcm_bytes)
                mp3_data += encoder.flush()
                mp3_bytes = bytes(mp3_data)
                if mp3_bytes:
                    return mp3_bytes, duration_sec
            except Exception as e:
                logger.warning(f"lameenc in-memory transcode failed: {e}. Attempting fallback...")

        # 2. Secondary: Direct ffmpeg subprocess pipe (if ffmpeg is available in environment)
        try:
            cmd = [
                "ffmpeg", "-y",
                "-f", "s16le",
                "-ar", str(rate),
                "-ac", "1",
                "-i", "pipe:0",
                "-b:a", settings.bitrate,
                "-f", "mp3",
                "pipe:1"
            ]
            res = subprocess.run(cmd, input=raw_pcm_bytes, capture_output=True, check=True)
            return res.stdout, duration_sec
        except Exception as e:
            logger.debug(f"Direct ffmpeg transcode not available or failed: {e}")

        # 3. Tertiary: pydub if audioop is available
        if AudioSegment is not None:
            try:
                segment = AudioSegment.from_raw(
                    io.BytesIO(raw_pcm_bytes),
                    sample_width=2,
                    frame_rate=rate,
                    channels=1
                )
                out_buf = io.BytesIO()
                segment.export(out_buf, format="mp3", bitrate=settings.bitrate)
                return out_buf.getvalue(), len(segment) / 1000.0
            except Exception as e:
                logger.debug(f"pydub export failed: {e}")

        # 4. Standard Library Fallback: 16-bit PCM WAV container
        logger.info("Packaging audio into standard WAV container...")
        wav_buf = io.BytesIO()
        with wave.open(wav_buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(rate)
            wf.writeframes(raw_pcm_bytes)
        return wav_buf.getvalue(), duration_sec

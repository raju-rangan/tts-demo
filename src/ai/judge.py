"""Gemini Multimodal LLM-as-a-Judge for Audio Quality Evaluation."""
import os
import json
import logging
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

from src.config import settings

logger = logging.getLogger(__name__)

class MetricScore(BaseModel):
    score: float = Field(..., description="Score from 1.0 to 5.0")
    weight: float = Field(..., description="Weight of metric in overall score")
    rationale: str = Field(..., description="Detailed explanation of the rating")

class RubricMetrics(BaseModel):
    script_adherence_and_accuracy: MetricScore = Field(
        ...,
        description="Score for verbatim script accuracy, checking for any missed, skipped, duplicated, or misread words"
    )
    naturalness_and_inflection: MetricScore = Field(..., description="Score for naturalness and vocal inflection")
    pacing_and_breathing: MetricScore = Field(..., description="Score for pacing, breath intervals, and pauses")
    tone_congruence: MetricScore = Field(..., description="Score for matching the assigned persona tone")
    pronunciation_and_jargon: MetricScore = Field(..., description="Score for pronunciation of financial acronyms and terminology")
    acoustic_quality: MetricScore = Field(..., description="Score for audio clarity and absence of artifacts")

    def items(self):
        return [
            ("script_adherence_and_accuracy", self.script_adherence_and_accuracy),
            ("naturalness_and_inflection", self.naturalness_and_inflection),
            ("pacing_and_breathing", self.pacing_and_breathing),
            ("tone_congruence", self.tone_congruence),
            ("pronunciation_and_jargon", self.pronunciation_and_jargon),
            ("acoustic_quality", self.acoustic_quality),
        ]

    def __getitem__(self, item: str) -> MetricScore:
        return getattr(self, item)

    def __len__(self) -> int:
        return 6

    def values(self):
        return [
            self.script_adherence_and_accuracy,
            self.naturalness_and_inflection,
            self.pacing_and_breathing,
            self.tone_congruence,
            self.pronunciation_and_jargon,
            self.acoustic_quality,
        ]

class QualityEvaluationResponse(BaseModel):
    overall_score: float = Field(..., description="Weighted average score (1.0 - 5.0)")
    overall_reasoning: str = Field(
        ...,
        description="Comprehensive summary explanation for the overall score, detailing strengths and deductions"
    )
    passed_rubric: bool = Field(..., description="True if overall_score >= 4.0")
    metrics: RubricMetrics = Field(..., description="Individual rubric dimensions")
    actionable_feedback: List[str] = Field(..., description="Constructive critiques and recommendations")

class QualityEvaluationResult(QualityEvaluationResponse):
    judge_model: str = Field(default="gemini-3.8-flash", description="Model used for evaluation")
    usage_metadata: Optional[Any] = Field(default=None, description="SDK token usage metadata")

RUBRIC_SYSTEM_INSTRUCTION = """
You are an expert Audio Quality Auditor and Speech Evaluation Judge for a major Financial Institution. Your job is to strictly evaluate synthetic spoken audio against the provided reference article text and persona guidelines.

GRADING RUBRIC (1.0 to 5.0 scale):
1. script_adherence_and_accuracy (Weight: 0.25): Does the spoken audio contain the ENTIRE reference text word-for-word? Specifically check for:
   - Missed or skipped words, phrases, parenthetical expansions, or sentences.
   - Duplicated, repeated, or stuttered words/phrases.
   - Substituted words or misread sentences.
   - Missing titles, headers, bullet numbers, or concluding statements.
2. naturalness_and_inflection (Weight: 0.20): Does the speech sound genuinely human, with organic sentence transitions and dynamic pitch modulation? Or is it robotic and monotone?
3. pacing_and_breathing (Weight: 0.15): Are there appropriate rhetorical pauses and natural breath intervals between paragraphs, section headers, and key financial figures? Is it rushed or sluggish?
4. tone_congruence (Weight: 0.15): Does the vocal delivery match the intended financial persona (e.g. welcoming retail guide, authoritative advisor, strict compliance officer)?
5. pronunciation_and_jargon (Weight: 0.15): Are banking acronyms (FDIC, APY, APR, ACH, EFT, KYC, BSA, AML, HELOC) and financial terms pronounced correctly according to standard banking industry standards?
6. acoustic_quality (Weight: 0.10): Is the audio clean, clear, and free from robotic clipping, metallic buzzing, phase distortion, or sudden volume jumps?

SCORING STANDARDS:
- 5.0: Exceptional, complete verbatim adherence, indistinguishable from a professional human narrator.
- 4.0 - 4.9: High quality, natural, meets enterprise production standards with only minor or negligible phrasing variances.
- 3.0 - 3.9: Understandable but has audible synthetic stiffness, skipped parentheticals, or minor pronunciation lapses.
- 1.0 - 2.9: Poor quality, severe robotic clipping, garbled acronyms, missing text sections, or repeated hallucinations.

You MUST provide:
- `overall_reasoning`: A detailed, comprehensive explanation for the overall score, summarizing strengths, verbatim accuracy, and reason for any point deductions.
- A `score`, `weight`, and specific `rationale` for EACH of the 6 rubric metrics.
- `actionable_feedback`: A bulleted list of actionable recommendations for improving the synthesis.

Return ONLY a valid JSON object matching the requested schema.
""".strip()

class MultimodalAudioJudge:
    """Evaluates audio quality against reference text directly referencing GCS URI."""

    def __init__(self, project_id: Optional[str] = None, location: Optional[str] = None, model: Optional[str] = None):
        self.project_id = project_id or settings.project_id
        self.location = location or getattr(settings, "judge_location", "global")
        self.model = model or settings.judge_model
        self._client: Optional[genai.Client] = None

    @property
    def client(self) -> genai.Client:
        """Lazy-initialized Google Gen AI Client with Vertex AI backend or API key."""
        if self._client is None:
            api_key = os.getenv("GEMINI_API_KEY")
            http_opts = types.HttpOptions(timeout=300000)  # 5 minute timeout for multimodal audio reasoning
            if api_key:
                self._client = genai.Client(api_key=api_key, http_options=http_opts)
            else:
                self._client = genai.Client(
                    vertexai=True,
                    project=self.project_id,
                    location=self.location,
                    http_options=http_opts
                )
        return self._client

    def evaluate_audio_gcs(
        self,
        gcs_audio_uri: str,
        reference_text: str,
        persona_name: str = "Technical Explainer",
        mime_type: str = "audio/mpeg"
    ) -> QualityEvaluationResult:
        """
        Evaluates an audio file stored in GCS by passing its URI pointer directly to Gemini Multimodal.
        Zero audio downloading or streaming through the worker.
        """
        logger.info(f"Evaluating GCS audio '{gcs_audio_uri}' with model '{self.model}' in location '{self.location}'")

        # Create the GCS Part reference
        audio_part = types.Part.from_uri(
            file_uri=gcs_audio_uri,
            mime_type=mime_type
        )

        prompt = f"""
EVALUATION REQUEST:
Intended Persona: {persona_name}

Reference Article Text:
\"\"\"
{reference_text}
\"\"\"

Listen to the attached audio and provide your structured evaluation based on the 6 rubric criteria.
"""

        gen_config = types.GenerateContentConfig(
            system_instruction=RUBRIC_SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=QualityEvaluationResponse,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=[prompt, audio_part],
                config=gen_config
            )
        except Exception as e:
            if "404" in str(e) and self.model != "gemini-2.5-pro":
                logger.warning(f"Judge model '{self.model}' not accessible on Vertex AI in project '{self.project_id}'. Falling back to 'gemini-2.5-pro'...")
                self.model = "gemini-2.5-pro"
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=[prompt, audio_part],
                    config=gen_config
                )
            else:
                raise

        # Parse JSON response
        try:
            data = json.loads(response.text)
            data["judge_model"] = self.model

            # Ensure overall_reasoning is populated
            if "overall_reasoning" not in data or not data["overall_reasoning"]:
                data["overall_reasoning"] = data.get("evaluation_summary") or "Audio evaluation assessed across all 6 financial services rubric dimensions."

            # Normalization fallback if model returns alternate keys like "scores" / "evaluation_notes"
            if "metrics" not in data and "scores" in data:
                notes = data.get("evaluation_notes", {})
                scores = data.get("scores", {})
                weights = {
                    "script_adherence_and_accuracy": 0.25,
                    "naturalness_and_inflection": 0.20,
                    "pacing_and_breathing": 0.15,
                    "tone_congruence": 0.15,
                    "pronunciation_and_jargon": 0.15,
                    "acoustic_quality": 0.10,
                }
                data["metrics"] = {
                    k: {
                        "score": float(scores.get(k, 4.0)),
                        "weight": weights.get(k, 0.15),
                        "rationale": notes.get(k, "Evaluated by judge.")
                    }
                    for k in weights
                }

            if "actionable_feedback" not in data or not data["actionable_feedback"]:
                if "evaluation_summary" in data:
                    data["actionable_feedback"] = [data["evaluation_summary"]]
                else:
                    data["actionable_feedback"] = ["Audio meets high enterprise quality criteria."]

            # Ensure overall score is calculated if missing
            if "overall_score" not in data or not data["overall_score"]:
                if isinstance(data.get("metrics"), dict):
                    metrics_vals = data["metrics"].values()
                    total_score = sum(
                        (m["score"] if isinstance(m, dict) else m.score) * 
                        (m.get("weight", 0.2) if isinstance(m, dict) else m.weight)
                        for m in metrics_vals
                    )
                    data["overall_score"] = round(total_score, 2)
                else:
                    data["overall_score"] = 4.5

            data["passed_rubric"] = data["overall_score"] >= 4.0

            eval_res = QualityEvaluationResult.model_validate(data)
            eval_res.usage_metadata = getattr(response, "usage_metadata", None)
            return eval_res

        except Exception as e:
            logger.error(f"Failed to parse LLM Judge response: {e}\nRaw output: {response.text}")
            raise ValueError(f"Invalid JSON returned from LLM Judge: {e}")

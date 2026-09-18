"""Token Usage & Cost Estimation Engine for Gemini Generative Speech & Multimodal Judge."""
from typing import Optional, Tuple, Any
from src.db.models import TokenUsageDetails, CostBreakdown

# Gemini Model Pricing (USD per 1,000,000 tokens)
# Reference: https://ai.google.dev/pricing
PRICING = {
    "gemini-3.1-flash-tts-preview": {
        "text_input_per_1m": 0.10,     # $0.10 / 1M text input tokens
        "audio_output_per_1m": 2.00,   # $2.00 / 1M audio output tokens
    },
    "gemini-3.8-flash": {
        "input_per_1m": 0.15,          # $0.15 / 1M input tokens (text + multimodal audio)
        "output_per_1m": 0.60,         # $0.60 / 1M output tokens
    },
    "gemini-2.5-pro": {
        "input_per_1m": 1.25,          # $1.25 / 1M input tokens
        "output_per_1m": 5.00,         # $5.00 / 1M output tokens
    }
}

class TokenCostCalculator:
    """Calculates granular token telemetry and billing estimates for pipeline runs."""

    @staticmethod
    def estimate_text_tokens(text: str) -> int:
        """Heuristic calculation of token count from raw text (~1.33 tokens per word)."""
        words = len(text.split())
        return max(1, int(words * 1.33))

    @staticmethod
    def estimate_audio_tokens(duration_seconds: float) -> int:
        """Heuristic calculation of audio tokens (~32 tokens per second of 24kHz audio)."""
        return max(1, int(duration_seconds * 32))

    @classmethod
    def calculate_pipeline_cost(
        cls,
        text: str,
        duration_seconds: float,
        tts_usage_metadata: Optional[Any] = None,
        judge_usage_metadata: Optional[Any] = None,
        tts_model: str = "gemini-3.1-flash-tts-preview",
        judge_model: str = "gemini-3.8-flash"
    ) -> Tuple[TokenUsageDetails, CostBreakdown]:
        """
        Computes the complete token usage and cost breakdown for a speech synthesis + audit job.
        Uses live usage_metadata when provided by the GenAI SDK, with accurate heuristics fallback.
        """
        # 1. Resolve TTS Tokens
        input_text_tokens = 0
        audio_output_tokens = 0
        if tts_usage_metadata:
            input_text_tokens = getattr(tts_usage_metadata, "prompt_token_count", 0) or 0
            audio_output_tokens = getattr(tts_usage_metadata, "candidates_token_count", 0) or 0

        if input_text_tokens <= 0:
            input_text_tokens = cls.estimate_text_tokens(text)
        if audio_output_tokens <= 0:
            audio_output_tokens = cls.estimate_audio_tokens(duration_seconds)

        # 2. Resolve Judge Tokens
        judge_input_tokens = 0
        judge_output_tokens = 0
        if judge_usage_metadata:
            judge_input_tokens = getattr(judge_usage_metadata, "prompt_token_count", 0) or 0
            judge_output_tokens = getattr(judge_usage_metadata, "candidates_token_count", 0) or 0

        if judge_input_tokens <= 0 and judge_model:
            # Judge takes input article text + prompt + attached audio
            judge_input_tokens = input_text_tokens + audio_output_tokens + 150
        if judge_output_tokens <= 0 and judge_model:
            # Rubric JSON response is approximately 300 tokens
            judge_output_tokens = 320

        total_tokens = input_text_tokens + audio_output_tokens + judge_input_tokens + judge_output_tokens

        token_details = TokenUsageDetails(
            input_text_tokens=input_text_tokens,
            audio_output_tokens=audio_output_tokens,
            judge_input_tokens=judge_input_tokens,
            judge_output_tokens=judge_output_tokens,
            total_tokens=total_tokens
        )

        # 3. Calculate Financial Costs (USD)
        tts_pricing = PRICING.get(tts_model, PRICING["gemini-3.1-flash-tts-preview"])
        tts_cost = (
            (input_text_tokens / 1_000_000.0) * tts_pricing["text_input_per_1m"] +
            (audio_output_tokens / 1_000_000.0) * tts_pricing["audio_output_per_1m"]
        )

        judge_pricing = PRICING.get(judge_model, PRICING["gemini-3.8-flash"])
        judge_cost = (
            (judge_input_tokens / 1_000_000.0) * judge_pricing.get("input_per_1m", 0.15) +
            (judge_output_tokens / 1_000_000.0) * judge_pricing.get("output_per_1m", 0.60)
        )

        cost_breakdown = CostBreakdown(
            tts_cost_usd=round(tts_cost, 6),
            judge_cost_usd=round(judge_cost, 6),
            total_cost_usd=round(tts_cost + judge_cost, 6),
            currency="USD"
        )

        return token_details, cost_breakdown

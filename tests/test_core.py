"""Unit tests for Phase 1 Core Speech & Judge modules."""
import pytest
from src.config import settings
from src.ai.personas import PERSONAS, get_persona
from src.ai.judge import QualityEvaluationResult, MetricScore

def test_settings_defaults():
    """Verify settings defaults are populated with Gemini 3 models."""
    assert settings.project_id is not None
    assert settings.voice_model.startswith("gemini-3")
    assert settings.judge_model.startswith("gemini-3")
    assert settings.sample_rate == 24000

def test_personas_exist():
    """Verify financial services personas are defined with appropriate system instructions."""
    expected = [
        "Retail Banking Guide",
        "Wealth & Market Advisor",
        "Regulatory & Policy Officer",
        "Employee Enablement & Operations",
        "Fraud & Security Alert"
    ]
    for name in expected:
        assert name in PERSONAS
        persona = get_persona(name)
        assert persona.voice_name != ""
        assert persona.audience in ["External Customers", "Internal Employees", "Both"]
        assert "FINANCIAL PRONUNCIATION & TERMINOLOGY GUIDELINES" in persona.system_instruction

def test_quality_evaluation_model():
    """Verify QualityEvaluationResult parsing and validation with 6 rubric dimensions."""
    data = {
        "judge_model": "gemini-3.8-flash",
        "overall_score": 4.6,
        "overall_reasoning": "High fidelity delivery with complete script adherence.",
        "passed_rubric": True,
        "metrics": {
            "script_adherence_and_accuracy": {
                "score": 4.9,
                "weight": 0.25,
                "rationale": "Verbatim script adherence with zero omitted sections."
            },
            "naturalness_and_inflection": {
                "score": 4.8,
                "weight": 0.20,
                "rationale": "Very natural cadence."
            },
            "pacing_and_breathing": {
                "score": 4.5,
                "weight": 0.15,
                "rationale": "Good pauses."
            },
            "tone_congruence": {
                "score": 4.7,
                "weight": 0.15,
                "rationale": "Authoritative."
            },
            "pronunciation_and_jargon": {
                "score": 4.6,
                "weight": 0.15,
                "rationale": "Acronyms pronounced correctly."
            },
            "acoustic_quality": {
                "score": 4.8,
                "weight": 0.10,
                "rationale": "Clear sound."
            }
        },
        "actionable_feedback": ["Good delivery."]
    }
    result = QualityEvaluationResult(**data)
    assert result.overall_score == 4.6
    assert result.overall_reasoning == "High fidelity delivery with complete script adherence."
    assert result.passed_rubric is True
    assert len(result.metrics) == 6
    assert len(result.actionable_feedback) == 1

def test_audio_generator_client_defaults_to_vertex(monkeypatch):
    """Verify GeminiAudioGenerator initializes Vertex AI client with project & location when no API key."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    from unittest.mock import patch, MagicMock
    from src.ai.generator import GeminiAudioGenerator

    with patch("google.genai.Client") as mock_client_cls:
        mock_client_instance = MagicMock()
        mock_client_cls.return_value = mock_client_instance

        gen = GeminiAudioGenerator(project_id="test-proj", location="us-central1", model="gemini-3.1-flash-tts-preview")
        client = gen.client

        assert mock_client_cls.called
        kwargs = mock_client_cls.call_args.kwargs
        assert kwargs["vertexai"] is True
        assert kwargs["project"] == "test-proj"
        assert kwargs["location"] == "us-central1"
        assert kwargs["http_options"].timeout == 600000
        assert client == mock_client_instance

def test_audio_generator_client_with_api_key(monkeypatch):
    """Verify GeminiAudioGenerator uses API key when GEMINI_API_KEY is explicitly set."""
    monkeypatch.setenv("GEMINI_API_KEY", "fake-api-key-12345")
    from unittest.mock import patch, MagicMock
    from src.ai.generator import GeminiAudioGenerator

    with patch("google.genai.Client") as mock_client_cls:
        mock_client_instance = MagicMock()
        mock_client_cls.return_value = mock_client_instance

        gen = GeminiAudioGenerator(project_id="test-proj", location="us-central1")
        client = gen.client

        assert mock_client_cls.called
        kwargs = mock_client_cls.call_args.kwargs
        assert kwargs["api_key"] == "fake-api-key-12345"
        assert kwargs["http_options"].timeout == 600000
        assert client == mock_client_instance

def test_transcode_pcm_wav_fallback():
    """Verify transcoding returns valid audio bytes without crashing."""
    from src.ai.generator import GeminiAudioGenerator
    gen = GeminiAudioGenerator()
    # 0.1 second of silent 24kHz 16-bit mono PCM (4800 bytes)
    silent_pcm = b"\x00" * 4800
    audio_bytes, dur = gen._transcode_pcm_to_mp3(silent_pcm, rate=24000)
    assert len(audio_bytes) > 0
    assert abs(dur - 0.1) < 0.01

def test_judge_client_initialization(monkeypatch):
    """Verify MultimodalAudioJudge initializes Vertex AI client with global location and handles API key."""
    from unittest.mock import patch, MagicMock
    from src.ai.judge import MultimodalAudioJudge

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with patch("google.genai.Client") as mock_client_cls:
        judge = MultimodalAudioJudge(project_id="test-proj", location="global", model="gemini-3.8-flash")
        _ = judge.client
        assert mock_client_cls.called
        kwargs = mock_client_cls.call_args.kwargs
        assert kwargs["vertexai"] is True
        assert kwargs["project"] == "test-proj"
        assert kwargs["location"] == "global"
        assert kwargs["http_options"].timeout == 300000

    monkeypatch.setenv("GEMINI_API_KEY", "test-key-999")
    with patch("google.genai.Client") as mock_client_cls:
        judge = MultimodalAudioJudge()
        _ = judge.client
        assert mock_client_cls.called
        kwargs = mock_client_cls.call_args.kwargs
        assert kwargs["api_key"] == "test-key-999"
        assert kwargs["http_options"].timeout == 300000

def test_split_text_into_chunks_short_text():
    """Verify text under 400 words is preserved as a single chunk."""
    from src.ai.generator import split_text_into_chunks
    short_text = "This is a brief financial advisory document. It has two complete sentences."
    chunks = split_text_into_chunks(short_text, target_words=400)
    assert len(chunks) == 1
    assert chunks[0] == short_text

def test_split_text_into_chunks_complete_sentences():
    """Verify long text is partitioned into complete sentences without cutting sentences in half."""
    from src.ai.generator import split_text_into_chunks
    # Build text of 150 sentences of 10 words each = 1,500 words
    sentences = [f"This is sentence number {i} with financial banking compliance guidance." for i in range(1, 151)]
    full_text = " ".join(sentences)
    total_words = len(full_text.split())
    assert total_words > 400

    chunks = split_text_into_chunks(full_text, target_words=400)
    assert len(chunks) >= 3

    # Every chunk must end on a sentence boundary (period)
    for idx, ch in enumerate(chunks):
        assert ch.strip().endswith("guidance.")
        words_in_chunk = len(ch.split())
        assert words_in_chunk <= 400

    # Total sentences across all chunks must equal the original 150 sentences
    reconstructed_sentences = []
    for ch in chunks:
        reconstructed_sentences.extend([s.strip() for s in ch.split(". ") if s.strip()])
    assert len(reconstructed_sentences) == 150

def test_multi_turn_audio_generation(monkeypatch):
    """Verify GeminiAudioGenerator stitches multiple turns and aggregates usage metadata."""
    from unittest.mock import patch, MagicMock
    from src.ai.generator import GeminiAudioGenerator, AggregatedUsageMetadata

    gen = GeminiAudioGenerator()

    # 1. Mock _generate_single_chunk to return 0.05s of PCM (2400 bytes) per chunk and token metadata
    mock_usage_1 = MagicMock(prompt_token_count=500, candidates_token_count=1200)
    mock_usage_2 = MagicMock(prompt_token_count=600, candidates_token_count=1400)
    pcm_chunk_1 = b"\x01\x00" * 1200  # 2400 bytes
    pcm_chunk_2 = b"\x02\x00" * 1200  # 2400 bytes

    side_effects = [
        (pcm_chunk_1, mock_usage_1),
        (pcm_chunk_2, mock_usage_2)
    ]

    with patch.object(gen, "_generate_single_chunk", side_effect=side_effects) as mock_chunk:
        # Build text with ~640 words to trigger exactly 2 turns (target 400 words)
        sentences = [f"Sentence {i} with clear financial guidance terminology." for i in range(1, 95)] # ~650 words
        long_text = " ".join(sentences)

        result = gen.generate_speech(text=long_text, persona_name="Retail Banking Guide", job_id="job_multi_test")

        assert mock_chunk.call_count == 2
        assert result.audio_bytes is not None
        assert len(result.audio_bytes) > 0
        assert result.duration_seconds > 0
        assert result.usage_metadata is not None
        assert result.usage_metadata.prompt_token_count == 1100
        assert result.usage_metadata.candidates_token_count == 2600
        assert result.usage_metadata.total_token_count == 3700


def test_normalize_chunk_rms():
    """Verify RMS loudness normalization scales PCM signal and clamps peaks."""
    import array
    from src.ai.generator import normalize_chunk_rms

    # 1. Test normal gain scaling (RMS 2000 -> target 3000, gain = 1.5)
    samples = array.array("h", [2000, -2000] * 1200)
    raw_pcm = samples.tobytes()

    normalized_pcm = normalize_chunk_rms(raw_pcm, target_rms=3000.0)
    norm_samples = array.array("h", normalized_pcm)

    # First sample should be approximately 3000 (2000 * 1.5)
    assert abs(norm_samples[0] - 3000) < 50
    assert abs(norm_samples[1] - (-3000)) < 50

    # 2. Test maximum gain clamp (RMS 1000 -> target 3000, gain clamped to 2.5)
    samples_low = array.array("h", [1000, -1000] * 1200)
    clamped_pcm = normalize_chunk_rms(samples_low.tobytes(), target_rms=3000.0)
    clamped_samples = array.array("h", clamped_pcm)
    assert abs(clamped_samples[0] - 2500) < 50


def test_apply_micro_fades():
    """Verify 40ms raised-cosine micro-fades taper boundaries smoothly to 0."""
    import array
    from src.ai.generator import apply_micro_fades

    # 1 second of constant PCM at 5000 amplitude (24000 samples)
    samples = array.array("h", [5000] * 24000)
    raw_pcm = samples.tobytes()

    faded_pcm = apply_micro_fades(raw_pcm, fade_samples=960)
    faded_samples = array.array("h", faded_pcm)

    # First sample should be near 0
    assert abs(faded_samples[0]) < 100
    # Sample at 960 should be near 5000 (full amplitude)
    assert abs(faded_samples[960] - 5000) < 100
    # Last sample should be near 0
    assert abs(faded_samples[-1]) < 100


def test_voice_customization_and_progress_callback():
    """Verify voice customization and progress callback work as expected in generate_speech."""
    from unittest.mock import patch, MagicMock
    from src.ai.generator import GeminiAudioGenerator

    gen = GeminiAudioGenerator()
    progress_stages = []

    def dummy_callback(stage, message, current_turn=None, total_turns=None):
        progress_stages.append((stage, current_turn, total_turns))

    mock_usage = MagicMock(prompt_token_count=100, candidates_token_count=200)
    mock_pcm = b"\x05\x00" * 2400

    with patch.object(gen, "_generate_single_chunk", return_value=(mock_pcm, mock_usage)) as mock_chunk:
        result = gen.generate_speech(
            text="Brief banking explainer text with complete sentence.",
            persona_name="Retail Banking Guide",
            job_id="job_cust_test",
            voice_customization="Warm, conversational, slightly slower on disclosures",
            progress_callback=dummy_callback
        )

        assert mock_chunk.called
        kwargs = mock_chunk.call_args.kwargs
        assert kwargs["voice_customization"] == "Warm, conversational, slightly slower on disclosures"

        # Verify progress stages invoked
        stage_names = [s[0] for s in progress_stages]
        assert "CHUNKING" in stage_names
        assert "SYNTHESIZING" in stage_names
        assert "STITCHING" in stage_names

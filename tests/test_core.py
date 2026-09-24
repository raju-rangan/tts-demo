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


def test_transcode_pcm_to_mp3_lameenc():
    """Verify in-memory MP3 transcoding with lameenc generates valid MP3 header."""
    from src.ai.generator import GeminiAudioGenerator, lameenc
    assert lameenc is not None, "lameenc should be installed in the environment"
    gen = GeminiAudioGenerator()
    # 0.5 seconds of 24kHz 16-bit mono PCM (24000 bytes)
    sample_pcm = b"\x05\x00" * 12000
    audio_bytes, dur = gen._transcode_pcm_to_mp3(sample_pcm, rate=24000)
    assert len(audio_bytes) > 0
    assert abs(dur - 0.5) < 0.01
    # Check MPEG audio frame sync header (0xFF and first 3 bits of byte 2 are 111)
    assert audio_bytes[0] == 0xFF
    assert (audio_bytes[1] & 0xE0) == 0xE0


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


def test_speech_speed_prompt_directives():
    """Verify generate_speech passes speed and formats pacing directives correctly."""
    from unittest.mock import patch, MagicMock
    from src.ai.generator import GeminiAudioGenerator

    gen = GeminiAudioGenerator()
    mock_usage = MagicMock(prompt_token_count=100, candidates_token_count=200)
    mock_pcm = b"\x05\x00" * 2400

    # 1. Test speed passed to _generate_single_chunk
    with patch.object(gen, "_generate_single_chunk", return_value=(mock_pcm, mock_usage)) as mock_chunk:
        gen.generate_speech(
            text="Brief banking explainer text with complete sentence.",
            persona_name="Retail Banking Guide",
            speed=0.85
        )
        assert mock_chunk.called
        assert mock_chunk.call_args.kwargs["speed"] == 0.85

    # 2. Test prompt construction with different speeds
    mock_client = MagicMock()
    gen._client = mock_client
    mock_resp = MagicMock()
    mock_resp.usage_metadata = mock_usage
    mock_resp.candidates = [MagicMock()]
    mock_part = MagicMock()
    mock_part.inline_data.data = mock_pcm
    mock_resp.candidates[0].content.parts = [mock_part]
    mock_client.models.generate_content.return_value = mock_resp

    persona = get_persona("Retail Banking Guide")

    # Slow speed (0.80x)
    gen._generate_single_chunk(
        chunk_text="Test slow chunk",
        persona=persona,
        job_id="job_speed_slow",
        speed=0.80
    )
    call_args = mock_client.models.generate_content.call_args.kwargs
    contents_prompt = call_args["contents"]
    assert "SPEED & PACING DIRECTIVE (Delivery Rate: 0.80x):" in contents_prompt
    assert "deliberate, measured, and unhurried pace" in contents_prompt

    # Fast disclaimer speed (1.50x)
    gen._generate_single_chunk(
        chunk_text="Test fast chunk",
        persona=persona,
        job_id="job_speed_fast",
        speed=1.50
    )
    call_args_fast = mock_client.models.generate_content.call_args.kwargs
    contents_fast = call_args_fast["contents"]
    assert "SPEED & PACING DIRECTIVE (Delivery Rate: 1.50x):" in contents_fast
    assert "accelerated rate" in contents_fast

    # Standard speed (1.00x) - no extra speed directive needed
    gen._generate_single_chunk(
        chunk_text="Test standard chunk",
        persona=persona,
        job_id="job_speed_std",
        speed=1.00
    )
    call_args_std = mock_client.models.generate_content.call_args.kwargs
    contents_std = call_args_std["contents"]
    assert "SPEED & PACING DIRECTIVE" not in contents_std


def test_verbatim_script_adherence_and_currency_directives():
    """Verify verbatim script adherence and US currency normalization rules are embedded in prompts."""
    from src.ai.personas import COMMON_FINANCIAL_PRONUNCIATION_DIRECTIVES, get_persona
    from src.ai.generator import GeminiAudioGenerator
    from unittest.mock import MagicMock

    # 1. Verify currency normalization rule in common financial directives
    assert "STRICT PROHIBITION: NEVER use regional numbering terms such as 'lakh' or 'crore'" in COMMON_FINANCIAL_PRONUNCIATION_DIRECTIVES
    assert "$250,000" in COMMON_FINANCIAL_PRONUNCIATION_DIRECTIVES
    assert "two hundred fifty thousand dollars" in COMMON_FINANCIAL_PRONUNCIATION_DIRECTIVES

    # 2. Verify verbatim script adherence block in prompt
    gen = GeminiAudioGenerator()
    mock_client = MagicMock()
    gen._client = mock_client
    mock_resp = MagicMock()
    mock_resp.usage_metadata = MagicMock(prompt_token_count=100, candidates_token_count=100)
    mock_resp.candidates = [MagicMock()]
    mock_part = MagicMock()
    mock_part.inline_data.data = b"\x00" * 4800
    mock_resp.candidates[0].content.parts = [mock_part]
    mock_client.models.generate_content.return_value = mock_resp

    persona = get_persona("Retail Banking Guide")
    gen._generate_single_chunk(
        chunk_text="# Investment Guide\n\nHere are the details.",
        persona=persona,
        job_id="job_adherence_test"
    )

    call_args = mock_client.models.generate_content.call_args.kwargs
    prompt = call_args["contents"]

    assert "VERBATIM SCRIPT ADHERENCE DIRECTIVE:" in prompt
    assert "100% Word-for-Word Fidelity:" in prompt
    assert "Titles & Headlines: If the text begins with a title or headline" in prompt
    assert "Section Headers & Bullet Points: Speak every section header" in prompt
    assert "Parenthetical Expressions: Read all parenthetical expressions" in prompt


def test_critique_feedback_prompt_injection():
    """Verify critic feedback is injected into the prompt when re-synthesizing a job."""
    from src.ai.personas import get_persona
    from src.ai.generator import GeminiAudioGenerator
    from unittest.mock import MagicMock

    gen = GeminiAudioGenerator()
    mock_client = MagicMock()
    gen._client = mock_client
    mock_resp = MagicMock()
    mock_resp.usage_metadata = MagicMock(prompt_token_count=100, candidates_token_count=100)
    mock_resp.candidates = [MagicMock()]
    mock_part = MagicMock()
    mock_part.inline_data.data = b"\x00" * 4800
    mock_resp.candidates[0].content.parts = [mock_part]
    mock_client.models.generate_content.return_value = mock_resp

    persona = get_persona("Retail Banking Guide")
    test_critique = (
        "WHAT YOU DID INCORRECTLY:\n"
        "- Script Adherence: You omitted the title 'Investment Guide'.\n"
        "MANDATORY REMEDIATION:\n"
        "- Read the title clearly aloud before reading paragraph 1."
    )

    gen._generate_single_chunk(
        chunk_text="# Investment Guide\n\nHere are the details.",
        persona=persona,
        job_id="job_critique_test",
        critique_feedback=test_critique
    )

    call_args = mock_client.models.generate_content.call_args.kwargs
    prompt = call_args["contents"]

    assert "AUDITOR CRITIQUE & MANDATORY DEFECT REMEDIATION (RE-TAKE / RETRY):" in prompt
    assert "Strictly remediate the auditor's findings:" in prompt
    assert "WHAT YOU DID INCORRECTLY:" in prompt
    assert "You omitted the title 'Investment Guide'" in prompt
    assert "Read the title clearly aloud before reading paragraph 1" in prompt


def test_podcast_personas():
    """Verify the 3 podcast personas: Man-Woman, Man-Man, Woman-Woman with correct voices and speaker pairs."""
    from src.ai.personas import get_persona, PERSONAS

    podcast_personas = [
        ("Podcast: Co-Hosts (Man & Woman)", ("Puck", "Kore"), ("male", "female")),
        ("Podcast: Co-Hosts (Man & Man)", ("Puck", "Charon"), ("male", "male")),
        ("Podcast: Co-Hosts (Woman & Woman)", ("Kore", "Sulafat"), ("female", "female")),
    ]

    for persona_name, expected_voices, expected_genders in podcast_personas:
        assert persona_name in PERSONAS
        p = get_persona(persona_name)
        assert p.is_podcast is True
        assert p.speakers is not None
        assert len(p.speakers) == 2

        voices = (p.speakers[0]["voice_name"], p.speakers[1]["voice_name"])
        assert voices == expected_voices

        genders = (p.speakers[0]["gender"], p.speakers[1]["gender"])
        assert genders == expected_genders

        assert "CO-HOST PROFILES:" in p.system_instruction
        assert "FINANCIAL PRONUNCIATION & TERMINOLOGY GUIDELINES:" in p.system_instruction


def test_podcast_script_generation():
    """Verify GeminiAudioGenerator.generate_podcast_script prompts Gemini and parses structured dialogue turns."""
    from unittest.mock import MagicMock
    from src.ai.generator import GeminiAudioGenerator, PodcastScript, PodcastTurn
    from src.ai.personas import get_persona

    gen = GeminiAudioGenerator()
    mock_client = MagicMock()
    gen._client = mock_client

    # Mock structured response
    expected_script = PodcastScript(
        title="High-Yield vs CDs: The Liquidity Debate",
        summary="A lively conversation contrasting liquidity vs guaranteed yields.",
        turns=[
            PodcastTurn(speaker="Joe", text="Welcome back! Today we are looking at where to park your cash.", style="upbeat and welcoming"),
            PodcastTurn(speaker="Jane", text="That's right Joe, especially looking at HYSAs versus CDs.", style="articulate and measured"),
            PodcastTurn(speaker="Joe", text="So what's the big trade-off for savers?", style="curious and engaging"),
            PodcastTurn(speaker="Jane", text="It really boils down to liquidity versus fixed APY.", style="clear and reassuring"),
        ]
    )

    mock_resp = MagicMock()
    mock_resp.text = expected_script.model_dump_json()
    mock_resp.parsed = expected_script
    mock_client.models.generate_content.return_value = mock_resp

    persona = get_persona("Podcast: Co-Hosts (Man & Woman)")
    article_text = "Article text on HYSAs vs CDs."
    director_notes = "Focus on the liquidity penalty and make Joe ask relatable questions."

    script = gen.generate_podcast_script(
        text=article_text,
        persona=persona,
        director_notes=director_notes,
        job_id="test_pod_script"
    )

    assert script.title == "High-Yield vs CDs: The Liquidity Debate"
    assert len(script.turns) == 4
    assert script.turns[0].speaker == "Joe"
    assert script.turns[1].speaker == "Jane"

    # Verify prompt arguments
    call_args = mock_client.models.generate_content.call_args.kwargs
    prompt = call_args["contents"]
    assert "Focus on the liquidity penalty and make Joe ask relatable questions." in prompt
    assert "Article text on HYSAs vs CDs." in prompt
    assert "Host 1: Joe (male, Voice: Puck)" in prompt
    assert "Host 2: Jane (female, Voice: Kore)" in prompt


def test_multi_speaker_speech_synthesis_payload():
    """Verify GeminiAudioGenerator._generate_multi_speaker_speech builds Google Multi-Speaker config."""
    from unittest.mock import MagicMock
    from src.ai.generator import GeminiAudioGenerator, PodcastScript, PodcastTurn
    from src.ai.personas import get_persona
    import base64

    gen = GeminiAudioGenerator()
    mock_client = MagicMock()
    gen._client = mock_client

    # Mock audio response (2400 bytes PCM = 0.05s)
    mock_resp = MagicMock()
    mock_resp.usage_metadata = MagicMock(prompt_token_count=350, candidates_token_count=1800)
    mock_resp.candidates = [MagicMock()]
    mock_part = MagicMock()
    # Provide dummy PCM audio in inline_data
    mock_part.inline_data = MagicMock(mime_type="audio/wav", data=base64.b64encode(b"\x05\x00" * 1200).decode("utf-8"))
    mock_resp.candidates[0].content.parts = [mock_part]
    mock_client.models.generate_content.return_value = mock_resp

    script = PodcastScript(
        title="Banking Podcast Demo",
        summary="Summary of banking podcast",
        turns=[
            PodcastTurn(speaker="Joe", text="Welcome to the show!", style="cheerful"),
            PodcastTurn(speaker="Jane", text="Great to be here!", style="friendly"),
        ]
    )
    persona = get_persona("Podcast: Co-Hosts (Man & Woman)")

    result = gen._generate_multi_speaker_speech(
        script=script,
        persona=persona,
        job_id="test_multi_speaker",
        speed=1.0
    )

    assert result.job_id == "test_multi_speaker"
    assert result.audio_bytes is not None
    assert len(result.audio_bytes) > 0
    assert result.title == "Banking Podcast Demo"
    assert "**Joe**: Welcome to the show!" in result.transcript
    assert "**Jane**: Great to be here!" in result.transcript

    # Inspect call args for multi-speaker schema
    call_args = mock_client.models.generate_content.call_args.kwargs
    config = call_args["config"]
    assert config.speech_config is not None
    assert config.speech_config.multi_speaker_voice_config is not None
    speaker_configs = config.speech_config.multi_speaker_voice_config.speaker_voice_configs
    assert len(speaker_configs) == 2
    assert speaker_configs[0].speaker == "Joe"
    assert speaker_configs[0].voice_config.prebuilt_voice_config.voice_name == "Puck"
    assert speaker_configs[1].speaker == "Jane"
    assert speaker_configs[1].voice_config.prebuilt_voice_config.voice_name == "Kore"

    contents = call_args["contents"]
    parts = contents[0]["parts"]
    assert len(parts) == 2
    assert parts[0]["text"] == "Welcome to the show!"
    assert parts[0]["speech_metadata"]["speaker"] == "Joe"
    assert parts[1]["text"] == "Great to be here!"
    assert parts[1]["speech_metadata"]["speaker"] == "Jane"


def test_generate_speech_routes_podcast_pipeline():
    """Verify generate_speech() automatically routes podcast personas through script & multi-speaker pipeline."""
    from unittest.mock import patch, MagicMock
    from src.ai.generator import GeminiAudioGenerator, PodcastScript, PodcastTurn, GenerationResult

    gen = GeminiAudioGenerator()

    fake_script = PodcastScript(
        title="Podcast Title",
        summary="Podcast Summary",
        turns=[
            PodcastTurn(speaker="Joe", text="Turn 1", style="natural"),
            PodcastTurn(speaker="Alex", text="Turn 2", style="analytical"),
        ]
    )

    fake_result = GenerationResult(
        job_id="job_pod_route",
        audio_bytes=b"fake_mp3_data",
        audio_format="audio/mpeg",
        duration_seconds=12.5,
        persona_used="Podcast: Co-Hosts (Man & Man)",
        model_used="gemini-3.1-flash-tts-preview",
        transcript="# Podcast Title\n\n**Joe**: Turn 1\n\n**Alex**: Turn 2",
        title="Podcast Title"
    )

    with patch.object(gen, "generate_podcast_script", return_value=fake_script) as mock_script_gen, \
         patch.object(gen, "_generate_multi_speaker_speech", return_value=fake_result) as mock_multi_synth:

        res = gen.generate_speech(
            text="Source article for podcast conversion",
            persona_name="Podcast: Co-Hosts (Man & Man)",
            job_id="job_pod_route",
            voice_customization="Emphasize commercial lending terms"
        )

        assert mock_script_gen.call_count == 1
        assert mock_multi_synth.call_count == 1
        assert res.title == "Podcast Title"
        assert res.duration_seconds == 12.5
        assert res.model_used == "gemini-3.1-flash-tts-preview"


def test_parse_markdown_script_to_turns():
    """Verify parse_markdown_script_to_turns correctly extracts speaker, style, and text with vocal markers."""
    from src.ai.generator import parse_markdown_script_to_turns

    default_speakers = [
        {"speaker": "Joe", "voice_name": "Puck", "gender": "man"},
        {"speaker": "Jane", "voice_name": "Kore", "gender": "woman"}
    ]

    sample_md = """# Defense and Debt Debate

**Joe** (cheerful and lively): Welcome everyone! [laughs] Today we are breaking down a massive defense spending surge.
**Jane** (skeptical and measured): [sighs] That's right Joe, but where is all that funding actually going to come from?
**Joe**: That is the trillion-dollar question. [chuckles] Let's look at the deficit projections."""

    script = parse_markdown_script_to_turns(sample_md, default_speakers)
    assert script.title == "Defense and Debt Debate"
    assert len(script.turns) == 3

    t1, t2, t3 = script.turns
    assert t1.speaker == "Joe"
    assert t1.style == "cheerful and lively"
    assert "[laughs]" in t1.text
    assert "Today we are breaking down" in t1.text

    assert t2.speaker == "Jane"
    assert t2.style == "skeptical and measured"
    assert "[sighs]" in t2.text

    assert t3.speaker == "Joe"
    assert "[chuckles]" in t3.text


def test_generate_podcast_script_10min_and_research():
    """Verify generate_podcast_script constructs ~10min prompt and invokes web search grounding."""
    from unittest.mock import patch, MagicMock
    from src.ai.generator import GeminiAudioGenerator, PodcastScript, PodcastTurn
    from src.ai.personas import get_persona

    gen = GeminiAudioGenerator()
    persona = get_persona("Podcast: Co-Hosts (Man & Woman)")

    mock_reasoning_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = '{"title": "10-Min Deep Dive", "summary": "Full analysis", "turns": [{"speaker": "Joe", "text": "Welcome to the show! [laughs]", "style": "energetic"}, {"speaker": "Jane", "text": "Great to be here! [chuckles]", "style": "thoughtful"}]}'
    mock_reasoning_client.models.generate_content.return_value = mock_resp
    gen._reasoning_client = mock_reasoning_client

    with patch.object(gen, "research_podcast_context", return_value="Live Grounding Fact: Global defense backlog hit $1.2T.") as mock_research:

        script = gen.generate_podcast_script(
            text="Article about defense spending and national debt.",
            persona=persona,
            director_notes="Focus on European rearmament bottlenecks.",
            target_duration_mins=10,
            enable_web_search=True
        )

        assert mock_research.call_count == 1
        assert script.title == "10-Min Deep Dive"
        assert len(script.turns) == 2
        assert script.turns[0].speaker == "Joe"
        assert script.turns[1].speaker == "Jane"


        # Check prompt contents sent to reasoning client
        call_args = mock_reasoning_client.models.generate_content.call_args.kwargs
        prompt = call_args["contents"]
        assert "~10 MINUTES" in prompt
        assert "1400 to 1700 total spoken words" in prompt
        assert "40 to 55 dynamic dialogue turns" in prompt
        assert "NOTEBOOKLM 5-ACT NARRATIVE STORY ARC" in prompt
        assert "THE DRAMATIC SCENARIO COLD OPEN & LISTENER ALIGNMENT" in prompt
        assert "SOCRATIC FRICTION (MANDATORY)" in prompt
        assert "VIVID METAPHORS (MANDATORY)" in prompt
        assert "THE CHALLENGER OUTRO & PROVOCATIVE TAKEAWAY" in prompt
        assert "HUMAN-LIKE CONVERSATIONAL EXPRESSIVENESS (CRITICAL)" in prompt
        assert "[laughs]" in prompt
        assert "[sighs]" in prompt
        assert "Live Grounding Fact: Global defense backlog hit $1.2T." in prompt
        assert "Focus on European rearmament bottlenecks." in prompt


def test_generate_speech_with_custom_podcast_script():
    """Verify generate_speech skips script generation if pre-drafted podcast_script is provided."""
    from unittest.mock import patch, MagicMock
    from src.ai.generator import GeminiAudioGenerator, GenerationResult

    gen = GeminiAudioGenerator()

    custom_script = """**Joe** (upbeat): This is a pre-drafted script! [laughs]
**Jane** (calm): Indeed it is Joe."""

    fake_result = GenerationResult(
        job_id="job_custom_pod",
        audio_bytes=b"fake_custom_audio",
        audio_format="audio/mpeg",
        duration_seconds=8.0,
        persona_used="Podcast: Co-Hosts (Man & Woman)",
        model_used="gemini-3.1-flash-tts-preview",
        transcript=custom_script,
        title="Custom Script"
    )

    with patch.object(gen, "generate_podcast_script") as mock_script_gen, \
         patch.object(gen, "_generate_multi_speaker_speech", return_value=fake_result) as mock_multi_synth:

        res = gen.generate_speech(
            text="Original article text",
            persona_name="Podcast: Co-Hosts (Man & Woman)",
            job_id="job_custom_pod",
            podcast_script=custom_script
        )

        # generate_podcast_script must NOT be called
        assert mock_script_gen.call_count == 0
        # _generate_multi_speaker_speech MUST be called with parsed turns
        assert mock_multi_synth.call_count == 1
        passed_script = mock_multi_synth.call_args.kwargs["script"]
        assert len(passed_script.turns) == 2
        assert passed_script.turns[0].speaker == "Joe"
        assert "[laughs]" in passed_script.turns[0].text
        assert res.job_id == "job_custom_pod"


def test_square_bracket_vocal_cue_normalization():
    """Verify parse_markdown_script_to_turns strictly normalizes parentheses cues () into square brackets []."""
    from src.ai.generator import parse_markdown_script_to_turns

    script_with_parens = """# Episode Title
**Joe** (curious): (laughs) Welcome to the show!
**Jane**: (sighs) Thanks Joe, (chuckles) this is wild.
**Joe**: Right? (pauses) Let's dive into the plumbing."""

    script = parse_markdown_script_to_turns(script_with_parens)
    assert len(script.turns) == 3

    assert "[laughs]" in script.turns[0].text
    assert "(laughs)" not in script.turns[0].text
    assert script.turns[0].style == "curious"

    assert "[sighs]" in script.turns[1].text
    assert "[chuckles]" in script.turns[1].text
    assert "(sighs)" not in script.turns[1].text
    # Jane omitted style -> fallback to expressive style
    assert script.turns[1].style == "analytical and measured"

    assert "[pauses]" in script.turns[2].text
    assert "(pauses)" not in script.turns[2].text
    assert script.turns[2].style == "curious and energetic"


def test_multi_speaker_pairwise_turn_batching():
    """Verify _generate_multi_speaker_speech batches turns into 2-turn conversational pairs."""
    from unittest.mock import MagicMock
    from src.ai.generator import GeminiAudioGenerator, PodcastScript, PodcastTurn
    from src.ai.personas import get_persona

    gen = GeminiAudioGenerator()
    mock_client = MagicMock()
    gen._client = mock_client

    mock_resp = MagicMock()
    mock_part = MagicMock()
    mock_part.inline_data.data = b"\x00\x00" * 4800  # 100ms of PCM
    mock_resp.candidates = [MagicMock()]
    mock_resp.candidates[0].content.parts = [mock_part]
    mock_client.models.generate_content.return_value = mock_resp

    script_4_turns = PodcastScript(
        title="Defense & Debt 4-Turn Debate",
        summary="Testing 4 turns",
        turns=[
            PodcastTurn(speaker="Joe", text="Jane, imagine proposing a 50% budget hike.", style="curious"),
            PodcastTurn(speaker="Jane", text="[laughs] Oh Joe, you'd get laughed out.", style="amused"),
            PodcastTurn(speaker="Joe", text="Right? Look at the dossier.", style="inquisitive"),
            PodcastTurn(speaker="Jane", text="[sighs] It is a 1.5 trillion dilemma.", style="analytical"),
        ]
    )

    persona = get_persona("Podcast: Co-Hosts (Man & Woman)")
    res = gen._generate_multi_speaker_speech(
        script=script_4_turns,
        persona=persona,
        job_id="job_4_turns_pairwise"
    )

    # 4 turns with batch_size=2 MUST result in exactly 2 generate_content calls
    assert mock_client.models.generate_content.call_count == 2

    # Check batch 1 payload
    b1_call = mock_client.models.generate_content.call_args_list[0].kwargs
    b1_parts = b1_call["contents"][0]["parts"]
    assert len(b1_parts) == 2
    assert b1_parts[0]["speech_metadata"]["speaker"] == "Joe"
    assert b1_parts[1]["speech_metadata"]["speaker"] == "Jane"

    # Check batch 2 payload
    b2_call = mock_client.models.generate_content.call_args_list[1].kwargs
    b2_parts = b2_call["contents"][0]["parts"]
    assert len(b2_parts) == 2
    assert b2_parts[0]["speech_metadata"]["speaker"] == "Joe"
    assert b2_parts[1]["speech_metadata"]["speaker"] == "Jane"


def test_reasoning_client_location_isolation():
    """Verify reasoning_client location defaults to settings.judge_location (global) when vertexai=True."""
    from unittest.mock import patch
    from src.ai.generator import GeminiAudioGenerator

    gen = GeminiAudioGenerator()
    gen.project_id = "test-vertex-project"
    gen._reasoning_client = None
    gen._client = None

    with patch("google.genai.Client") as mock_client_cls:
        _ = gen.reasoning_client
        mock_client_cls.assert_called_once()
        call_kwargs = mock_client_cls.call_args.kwargs
        assert call_kwargs["vertexai"] is True
        assert call_kwargs["location"] == "global"
        assert call_kwargs["project"] == "test-vertex-project"


def test_parse_script_from_json():
    """Verify parse_markdown_script_to_turns seamlessly parses structured JSON scripts."""
    import json
    from src.ai.generator import parse_markdown_script_to_turns

    json_script = json.dumps({
        "title": "Tech & Liquidity Overview",
        "summary": "Co-hosts explore capital requirements",
        "turns": [
            {"speaker": "Joe", "style": "curious and energetic", "text": "Welcome everyone! [laughs] Let's break down liquidity buffers."},
            {"speaker": "Jane", "style": "analytical and measured", "text": "[sighs] Thanks Joe, bank reserves are critical right now."},
            {"speaker": "Joe", "style": "inquisitive", "text": "What about the yield spread? [chuckles]"}
        ]
    })

    script = parse_markdown_script_to_turns(json_script)
    assert script.title == "Tech & Liquidity Overview"
    assert len(script.turns) == 3
    assert script.turns[0].speaker == "Joe"
    assert script.turns[1].speaker == "Jane"
    assert script.turns[2].speaker == "Joe"
    assert "[laughs]" in script.turns[0].text
    assert "[sighs]" in script.turns[1].text


def test_strict_speaker_alternation_guarantee():
    """Verify consecutive turns with the same speaker are automatically flipped to guarantee strict alternation."""
    from src.ai.generator import parse_markdown_script_to_turns

    # A script with 3 consecutive Joe turns followed by 2 consecutive Jane turns
    consecutive_script = """# Consecutive Speakers Test
**Joe**: Point one.
**Joe**: Point two.
**Joe**: Point three.
**Jane**: Point four.
**Jane**: Point five.
"""
    script = parse_markdown_script_to_turns(consecutive_script)
    assert len(script.turns) == 5

    # Check strict alternation across all adjacent turns
    speakers = [t.speaker for t in script.turns]
    assert speakers == ["Joe", "Jane", "Joe", "Jane", "Joe"]
    for i in range(1, len(speakers)):
        assert speakers[i] != speakers[i - 1], f"Turn {i} ({speakers[i]}) did not alternate with turn {i-1} ({speakers[i-1]})"


def test_persona_voice_remapping_cross_cohosts():
    """Verify scripts drafted with Joe & Jane are properly remapped when switched to other personas."""
    from src.ai.generator import parse_markdown_script_to_turns
    from src.ai.personas import get_persona

    script_joe_jane = """# Market Briefing
**Joe**: Welcome to the market briefing!
**Jane**: Thanks Joe, checking bond yields today.
**Joe**: Yields look inverted.
**Jane**: That usually signals caution.
"""

    # Test remapping for "Podcast: Co-Hosts (Man & Man)" (Joe & Alex)
    man_man_persona = get_persona("Podcast: Co-Hosts (Man & Man)")
    res_man_man = parse_markdown_script_to_turns(script_joe_jane, man_man_persona.speakers)
    speakers_mm = [t.speaker for t in res_man_man.turns]
    assert speakers_mm == ["Joe", "Alex", "Joe", "Alex"]

    # Test remapping for "Podcast: Co-Hosts (Woman & Woman)" (Jane & Maya)
    woman_woman_persona = get_persona("Podcast: Co-Hosts (Woman & Woman)")
    res_ww = parse_markdown_script_to_turns(script_joe_jane, woman_woman_persona.speakers)
    speakers_ww = [t.speaker for t in res_ww.turns]
    assert speakers_ww == ["Jane", "Maya", "Jane", "Maya"]





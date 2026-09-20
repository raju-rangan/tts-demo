# Project Memory & Operational Context

## 1. Project Overview & Scope
- **Project Name**: Financial Services Knowledge-to-Speech Platform
- **Active Workspace**: `/Users/rrangan/Documents/customers/tts-demo`
- **Target GCP Project**: `cs-poc-edgd4dliruu2xvksuvo4r3g`
- **Target GCS Bucket**: `knowledge-to-audio-poc`
- **Core Capabilities**:
  - Converts banking, compliance, and wealth management articles into lifelike synthetic audio using Gemini voice models.
  - Performs automated multimodal quality auditing against source transcripts using Gemini as an LLM Judge directly on GCS URIs.
  - Enterprise Web Studio UI (FastAPI + Tailwind/Lucide single-page app) with authentication, job tracking, cost/token telemetry, and slide-over job details.

---

## 2. Architecture & Technical Decisions

### Model Matrix & Regional Routing
| Role | Model Identifier | Vertex Location | Notes |
| :--- | :--- | :--- | :--- |
| **Voice Synthesis (TTS)** | `gemini-3.1-flash-tts-preview` | `us-central1` | 24kHz audio synthesis, steerable financial personas. |
| **Multimodal Audio Judge** | `gemini-3.8-flash` | `global` | High-throughput audio reasoning directly from GCS URIs (`location="global"`). |

### SDK & Client Patterns
- **Google GenAI SDK (`google-genai`)**:
  - Single-turn `generate_content` calls explicitly suppress advisory warnings using:
    `automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)`.
  - Separate `genai.Client` instances are maintained for TTS (`location="us-central1"`) and Judge (`location="global"`).

### Persistence: Hybrid Resilient Repository
- **Primary Design**: Cloud Firestore (`tts_jobs` collection) via `google-cloud-firestore`.
- **Current Active Mode**: Local SQLite (`data/tts_jobs.db`). In project `cs-poc-edgd4dliruu2xvksuvo4r3g`, the default GCP database is configured in legacy **Datastore Mode** rather than **Firestore Native Mode** (`400 The Cloud Firestore API is not available for Firestore in Datastore Mode database`). Additionally, the active credential lacks database administration permissions to provision a secondary Firestore Native database. The system automatically fell back to embedded SQLite to guarantee zero crash and full offline persistence.

### Security & Server Constraints
- All local HTTP servers (FastAPI / Uvicorn) must bind strictly to `127.0.0.1:8000` (never `0.0.0.0`).

### Multimodal Quality Rubric (6 Dimensions)
1. **`script_adherence_and_accuracy`** (Weight: **0.25**): Verbatim transcript audit checking for missed, skipped, repeated, or mispronounced words.
2. **`naturalness_and_inflection`** (Weight: **0.20**): Cadence, pitch dynamics, human realism.
3. **`pacing_and_breathing`** (Weight: **0.15**): Rhetorical pauses between financial sections and numbers.
4. **`tone_congruence`** (Weight: **0.15**): Voice persona alignment (e.g. Retail Guide vs. Compliance Officer).
5. **`pronunciation_and_jargon`** (Weight: **0.15**): Banking acronyms (FDIC, APY, APR, ACH, KYC, AML, HELOC).
6. **`acoustic_quality`** (Weight: **0.10**): Freedom from clipping, metallic distortion, and volume jumps.
- **Overall Score Rationale**: `overall_reasoning: str` field providing a detailed narrative justification of the score.

### Financial Billing & Cost Telemetry Engine
- Parses SDK `response.usage_metadata`:
  - TTS Text Input: $0.10 / 1M tokens
  - TTS Audio Output: $2.00 / 1M tokens
  - Judge Input: $0.15 / 1M tokens
  - Judge Output: $0.60 / 1M tokens
- Typical job cost: ~$0.004 to $0.007 USD per article.

---

## 3. Known Gotchas & Technical Insights

1. **`gemini-3.8-flash` Region**:
   - Calling `gemini-3.8-flash` in `us-central1` returns `404 NOT_FOUND`. It must be initialized with `location="global"` (configured via `GEMINI_JUDGE_LOCATION=global` in `.env`).
2. **GCP Project & ADC Quota Verification**:
   - Validating GCP auth requires verifying that the active `gcloud` project, the ADC `quota_project_id`, and `GCP_PROJECT_ID` in `.env` all match `cs-poc-edgd4dliruu2xvksuvo4r3g`.
3. **Firestore Mode Conflict in Target Project**:
   - The GCP project `cs-poc-edgd4dliruu2xvksuvo4r3g` has its `(default)` database set to **Datastore Mode**. The standard Firestore client library errors with `FailedPrecondition 400`. Because of this, job tracking runs on local SQLite (`data/tts_jobs.db`).
4. **Automatic Function Calling (AFC) Warning**:
   - Without `automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)`, the SDK issues a warning recommending `Chat.send_message` over `Models.generate_content`.
5. **Structured Output Schema Enforcement**:
   - The judge model must receive a pure Pydantic response schema (`QualityEvaluationResponse`) where every field has a concrete data type. Fields like `Optional[Any]` cause Vertex AI `400 INVALID_ARGUMENT: one or more response schemas didn't specify the schema type field`.
6. **Python Virtual Environment**:
   - Dependencies are installed in `.venv` (Python 3.13.7). Commands should be invoked via `./.venv/bin/...` or `python3` within `.venv`.
7. **Live Token Telemetry vs. Fallback Heuristics**:
   - Gemini API returns exact `usage_metadata` (`prompt_token_count`, `candidates_token_count`). Fallback estimations must be disabled for new runs to guarantee 100% actual billing numbers.

---

## 4. Chronological Session RECAP

- **2026-09-18 10:00** - Verified strict authentication against `cs-poc-edgd4dliruu2xvksuvo4r3g` in `scripts/verify_gcp_auth.py`.
- **2026-09-18 10:30** - Provisioned GCS bucket `knowledge-to-audio-poc` with 30-day lifecycle expiration and persona prefix routing (`external/audio/` vs `internal/audio/`).
- **2026-09-18 11:15** - Diagnosed Option 5 failure: resolved `gemini-3.8-flash` 404 in `us-central1` by configuring `GEMINI_JUDGE_LOCATION=global`. Suppressed AFC warning in `generator.py` and `judge.py`.
- **2026-09-18 12:00** - Built Web Studio UI (FastAPI in `src/ui/app.py`, Tailwind SPA in `src/ui/static/index.html`) with KPI cards, job detail drawer, and audio playback.
- **2026-09-18 12:30** - Implemented dual repository pattern in `src/db/repository.py` (Firestore with SQLite fallback). Implemented token/cost calculator in `src/ai/cost_calculator.py`.
- **2026-09-18 13:15** - Added 6th rubric metric (`script_adherence_and_accuracy`, weight 0.25) and `overall_reasoning` field to `src/ai/judge.py`, `src/db/models.py`, `src/db/repository.py`, and `scripts/run_quickstart.py`.
- **2026-09-18 13:40** - Created global Antigravity `recap` skill at `~/.gemini/config/skills/recap/SKILL.md` and synthesized project context into `memory.md`.
- **2026-09-18 13:48** - Diagnosed token telemetry for new runs: identified Vertex AI 400 schema error in judge caused by `Optional[Any]`. Validated live fix (`task-977`) returning 16,567 actual prompt tokens and 620 output tokens from Gemini. Planned removal of heuristic estimations for new runs.
- **2026-09-18 13:52** - Investigated cloud database status: confirmed no records are currently in Firestore on GCP because the project's `(default)` database is in legacy Datastore Mode and the caller lacks Firestore Admin permissions. Clarified that audio is in GCS, models are in Vertex AI, and telemetry metadata is currently in SQLite.
- **2026-09-18 14:50** - Google Cloud Logging, Job Deletion, & Stuck Job Fix:
  - Installed `google-cloud-logging>=3.11.0` and created central logger in `src/utils/logger.py`.
  - Configured real-time log dispatching directly to Google Cloud Logging (`projects/cs-poc-edgd4dliruu2xvksuvo4r3g/logs/tts-studio`) with local rotating file backup (`logs/app.log`) and console output.
  - Implemented full-stack Job Deletion mechanism: `delete_job` in `BaseJobRepository`, `SQLiteJobRepository`, `FirestoreJobRepository`, `DELETE /api/jobs/{job_id}` in `src/ui/app.py`, and UI controls (trash button in table rows and "Delete" button in details drawer) with confirmation dialogs.
  - Remediated stuck jobs `job_d237ac24` and `job_0dd9b084` in `data/tts_jobs.db`.
- **2026-09-18 15:24** - Multi-Turn Sentence-Safe Chunking & Lossless Audio Stitching:
  - Implemented `split_text_into_chunks` in `src/ai/generator.py`: divides articles into complete-sentence units without cutting sentences mid-thought.
  - Implemented `_generate_single_chunk` and sequential multi-turn synthesis in `GeminiAudioGenerator`.
  - Losslessly stitched raw uncompressed 24kHz PCM audio in-memory with a natural 300ms silence pause between turns, followed by single-pass broadcast MP3 encoding @ 320kbps.
  - Implemented `AggregatedUsageMetadata` to sum actual token usage across all turns for accurate billing.
  - Updated Web UI in `src/ui/static/index.html` to display a smart multi-turn auto-chunking indicator.
  - Added unit tests in `tests/test_core.py`.
- **2026-09-18 15:45** - Diagnosed `job_76d641a5` & Calibrated 400-Word Operational Sweet Spot:
  - Root Cause: Live benchmarking revealed `gemini-3.1-flash-tts-preview` produces speech at ~1.8 words/sec of audio (~252 words produces ~5 min audio and takes ~2.3 min latency). At 1,100 words, synthesis requires >611s, exceeding Google Cloud's hard HTTP read timeout of 600.0 seconds (10 minutes).
  - Masking Fallback: Removed `client.interactions.create` fallback from `generator.py` because Vertex AI rejected `gemini-3.1-flash-tts-preview` on that endpoint with 400 Invalid Request, which was masking the 600s read timeout.
  - Calibrated Chunk Limit: Set `tts_chunk_word_limit: int = 400` in `src/config.py` and `src/ai/generator.py`. Each ~400-word turn finishes in ~2 to 2.5 minutes, comfortably within the 10-minute timeout.
  - Partitioning: 1,659-word article cleanly splits into 5 complete-sentence turns (367, 390, 396, 395, and 111 words).
  - All **36 out of 36 automated tests passing**.
- **2026-09-18 15:58** - Added Job Details Retry Capability:
  - Implemented `POST /api/jobs/{job_id}/retry` in `src/ui/app.py`: resets job record to `RUNNING`, clears prior error diagnostics, and re-launches synthesis and judging in `BackgroundTasks`.
  - Added **Retry** button in Job Details drawer header and an inline **"Retry Synthesis Now"** action inside the failure diagnostics banner in `src/ui/static/index.html`.
  - Added quick retry button to table rows for failed jobs.
  - Implemented modal closure guards (`CURRENT_JOB = null`, `isModalOpen` checks) to prevent closed drawers from re-opening on background poll ticks or retry resolution.
  - Added `test_retry_job_api` in `tests/test_ui.py`.
- **2026-09-18 16:30** - Voice Customization, Acoustic DSP Mastering, & Live Progress Screen:
  - **Voice Customization & Director's Notes**: Added `#inputVoiceCustomization` input in New Voice Synthesis modal. Persisted across `JobRecord`, API request models, and SQLite/Firestore repositories. Injected as `USER VOICE CUSTOMIZATION & DELIVERY DIRECTIVES` in Gemini TTS prompts.
  - **Acoustic Studio & Continuity Directives**: Added `COMMON_ACOUSTIC_STUDIO_DIRECTIVES` enforcing an acoustically treated dry sound booth, flat vocal EQ, and on-axis close-mic position. Injected `AUDIO CONTINUITY DIRECTIVE` in multi-turn batches instructing Gemini to maintain identical pitch baseline and room tone across parts.
  - **DSP Audio Mastering**: Implemented `normalize_chunk_rms` (RMS loudness leveling across turns to 3000 RMS with soft-clipping protection) and `apply_micro_fades` (40ms raised-cosine micro-fade in/out on chunk boundaries) before 300ms pause concatenation.
  - **Live Pipeline Progress Screen**: Unblocked `RUNNING` jobs in the Web Studio UI. Added pulsing "Track Live" button and clickable rows. Built interactive 5-stage milestone stepper (`CHUNKING`, `SYNTHESIZING`, `STITCHING`, `UPLOADING`, `EVALUATING`) with turn pills, live description, and auto-refreshing drawer.
  - Added Director's Notes display card in Job Details drawer when custom notes are present.
- **2026-09-18 17:50** - Bulk Processing Reliability, WAF Scraper Hardening & Gemini TTS Backoff:
  - **Sample URL Fixes in Web UI**: Replaced futuristic 2026 placeholder URLs in `src/ui/static/index.html` (`loadSampleUrls()` and textarea placeholder) with verified, active public URLs (`monetary20240918a.htm`, `pr24012.html`, and `Certificate_of_deposit`).
  - **WAF Scraper Hardening**: Enhanced `src/utils/extractor.py` with standard browser headers (`Sec-Ch-Ua`, `Sec-Fetch-*`, `Upgrade-Insecure-Requests`) and an automatic fallback identifying user agent (`ApexBankKnowledgeVoice/1.0`), eliminating 403 Forbidden errors on government and educational pages.
  - **Gemini TTS Backoff & Retry**: Implemented automatic 2-attempt retry with 3.0s exponential backoff in `src/ai/generator.py` for `_generate_single_chunk` when transient empty audio parts or quota bursts occur. Added detailed `finish_reason` and safety ratings diagnostic extraction in `_extract_audio_from_response`.
  - **Inter-Turn Pacing Buffer**: Added 1.0s sleep between consecutive turns in multi-turn synthesis to prevent rapid TPM bursting against Vertex AI preview limits.
  - All **75 out of 75 automated tests passing**.
  - **Localhost Auth Bypass**: Implemented seamless development bypass on `127.0.0.1` and `localhost` with zero Google OAuth prompt errors.
  - **Full-Page Auditor Governance Dashboard**: Integrated interactive Chart.js visualizations (Radar, Donut, Bar, Token breakdown) and FinOps metrics for David Chen.
  - **Resilient Job Creation & Progress Tracking**: Eliminated race condition on `submitNewJob` by immediately unshifting `data.job` into memory, adding direct `GET /api/jobs/{id}` fetch fallback to `openJobDetail`, parsing error responses cleanly, and adding director note guidance to `loadSampleText()`.

- **2026-09-20 14:00** - Speech Speed Control & Critic-Guided Retry Optimization:
  - **Speech Speed Control**: Added `speed` parameter (0.25 to 4.0, default 1.0) according to Cloud TTS / Gemini TTS specifications. Integrated into `JobRecord`, API request models, and injected into Gemini TTS delivery instructions. Added slider control `#inputSpeed` in New Voice Synthesis modal.
  - **Critic-Guided Retry & Observations Injection**: Implemented `POST /api/jobs/{id}/retry/preview` and updated `POST /api/jobs/{id}/retry` with `include_critique` and `additional_instructions` parameters. Automatically injects judge observations and low-scoring rubric feedback into retry prompts as remediation instructions.
  - **Interactive Retry Modal**: Built modal dialog (`#modalRetryDialog`) showing previous scores, judge critique, and editable instructions before re-running synthesis.
  - **Tour Onboarding**: Implemented Driver.js interactive guided tour for new users across Creator and Auditor personas, with persistent state per Google identity.
- **2026-09-20 16:55** - Frontend Architecture Refactoring:
  - **Decomposed Monolithic `index.html`**: Split 4,586-line monolith into modular Jinja2 components (`src/ui/templates/partials/`) and discrete vanilla JS feature modules (`src/ui/templates/partials/scripts/`).
  - **Zero Node/npm Overhead**: Kept lightweight Jinja2 server-side rendering while preserving modern ES6 modular structure, native browser execution, and 100% test compatibility.
  - **Updated FastAPI Handler**: Wired `fastapi.templating.Jinja2Templates` into `app.get("/")`.
  - **Clean Single Source of Truth**: Removed obsolete `src/ui/static/index.html`.
  - **Full-Screen Responsive Layout Optimization**: Replaced `max-w-7xl mx-auto` (which artificially constrained layout width to 1280px / 80rem) with `w-full` in `index.html`. Expanded title truncation widths from `max-w-xs` (320px) to `max-w-md lg:max-w-xl`, eliminating column squeezing across the 8-column Jobs Table and Chart.js dashboards.
  - All **90 out of 90 automated tests passing**.

---

## 5. Active State & Pending Next Steps

### Current State
- Local development server running on `http://127.0.0.1:8000`.
- Auth bypass active on localhost, strict GCIP token validation active on Google Cloud Run.
- Modular Jinja2 frontend template architecture deployed and verified.
- Full-page Auditor dashboard with Chart.js charts active.
- Critic-guided retry preview and speed control enabled.
- All 90 automated tests passing.

### Verification Commands
```bash
# Run test suite (90 tests)
USE_FIRESTORE=false ./.venv/bin/pytest tests/ -v

# Run app locally
make ui
```



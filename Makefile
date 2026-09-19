# ==============================================================================
# Knowledge Article to Speech & Multimodal LLM-as-a-Judge Platform
# ==============================================================================

SHELL := /bin/bash
UV ?= uv

# Load .env file variables automatically if present
ifneq (,$(wildcard ./.env))
    include .env
    export $(shell sed 's/=.*//' .env)
endif

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help message
	@echo "======================================================================"
	@echo "🎙️ Knowledge-to-Speech Platform Developer Commands (powered by uv)"
	@echo "======================================================================"
	@grep -h -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ------------------------------------------------------------------------------
# 1. Environment & Setup (UV)
# ------------------------------------------------------------------------------

.PHONY: venv
venv: ## Create Python virtual environment using uv
	@echo "Creating virtual environment with uv..."
	@$(UV) venv .venv

.PHONY: install
install: ## Sync and install dependencies using uv
	@echo "Installing dependencies with uv..."
	@$(UV) pip install -e .
	@if [ ! -f .env ]; then \
		echo "Creating .env from .env.example..."; \
		cp .env.example .env; \
	fi
	@echo "✓ Setup complete with uv. Edit .env with your GCP project settings."

# ------------------------------------------------------------------------------
# 2. Google Cloud Authentication & Configuration
# ------------------------------------------------------------------------------

.PHONY: auth
auth: ## Authenticate GCP CLI and ADC (auto-bypasses if already authenticated)
	@if [ -z "$(CLEAN_PROJECT_ID)" ] || [ "$(CLEAN_PROJECT_ID)" = "your-gcp-project-id" ]; then \
		echo "⚠️ Warning: GCP_PROJECT_ID is not set in .env. Please configure .env first."; \
		exit 1; \
	fi
	@echo "🔍 Checking GCP authentication state for $(CLEAN_PROJECT_ID)..."
	@ACTIVE_ACCOUNT=$$(gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null); \
	if [ -n "$$ACTIVE_ACCOUNT" ]; then \
		echo "✓ 1. gcloud CLI already authenticated as $$ACTIVE_ACCOUNT (skipping login)"; \
	else \
		echo "🔐 1. Authenticating gcloud CLI user account..."; \
		gcloud auth login; \
	fi
	@CURRENT_PROJ=$$(gcloud config get-value project 2>/dev/null); \
	if [ "$$CURRENT_PROJ" = "$(CLEAN_PROJECT_ID)" ]; then \
		echo "✓ 2. Active gcloud project already set to $(CLEAN_PROJECT_ID)"; \
	else \
		echo "🔐 2. Setting active gcloud project to $(CLEAN_PROJECT_ID)..."; \
		gcloud config set project $(CLEAN_PROJECT_ID); \
	fi
	@if gcloud auth application-default print-access-token >/dev/null 2>&1; then \
		echo "✓ 3. Application Default Credentials (ADC) already active (skipping login)"; \
	else \
		echo "🔐 3. Setting up Application Default Credentials (ADC) for Python SDK..."; \
		gcloud auth application-default login; \
	fi
	@ADC_FILE="$$HOME/.config/gcloud/application_default_credentials.json"; \
	if [ -f "$$ADC_FILE" ] && grep -q '"quota_project_id": "$(CLEAN_PROJECT_ID)"' "$$ADC_FILE" 2>/dev/null; then \
		echo "✓ 4. ADC Quota Project already set to $(CLEAN_PROJECT_ID)"; \
	else \
		echo "🔐 4. Setting ADC Quota Project to $(CLEAN_PROJECT_ID)..."; \
		gcloud auth application-default set-quota-project $(CLEAN_PROJECT_ID); \
	fi
	@echo "✓ GCP Authentication fully verified for project: $(CLEAN_PROJECT_ID)"

.PHONY: auth-force
auth-force: ## Force full interactive re-login for both gcloud CLI and ADC
	@if [ -z "$(CLEAN_PROJECT_ID)" ] || [ "$(CLEAN_PROJECT_ID)" = "your-gcp-project-id" ]; then \
		echo "⚠️ Warning: GCP_PROJECT_ID is not set in .env. Please configure .env first."; \
		exit 1; \
	fi
	@echo "🔐 1. Force re-authenticating gcloud CLI user account..."
	@gcloud auth login
	@echo "🔐 2. Configuring active Google Cloud Project: $(CLEAN_PROJECT_ID)..."
	@gcloud config set project $(CLEAN_PROJECT_ID)
	@echo "🔐 3. Force re-authenticating Application Default Credentials (ADC)..."
	@gcloud auth application-default login
	@echo "🔐 4. Setting ADC Quota Project to $(CLEAN_PROJECT_ID)..."
	@gcloud auth application-default set-quota-project $(CLEAN_PROJECT_ID)
	@echo "✓ GCP Authentication complete for CLI and ADC (project: $(CLEAN_PROJECT_ID))"

.PHONY: auth-cli
auth-cli: ## Authenticate gcloud CLI user account (auto-bypasses if already authenticated)
	@ACTIVE_ACCOUNT=$$(gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null); \
	if [ -n "$$ACTIVE_ACCOUNT" ]; then \
		echo "✓ gcloud CLI already authenticated as $$ACTIVE_ACCOUNT"; \
	else \
		echo "🔐 Authenticating gcloud CLI user account..."; \
		gcloud auth login; \
	fi; \
	gcloud config set project $(CLEAN_PROJECT_ID)

.PHONY: auth-adc
auth-adc: ## Authenticate Application Default Credentials (auto-bypasses if already active)
	@if gcloud auth application-default print-access-token >/dev/null 2>&1; then \
		echo "✓ Application Default Credentials (ADC) already active"; \
	else \
		echo "🔐 Setting up Application Default Credentials (ADC)..."; \
		gcloud auth application-default login; \
	fi; \
	gcloud auth application-default set-quota-project $(CLEAN_PROJECT_ID)

.PHONY: enable-apis
enable-apis: ## Enable required GCP APIs (Cloud Run, Cloud Build, Artifact Registry, Vertex AI, GCS)
	@echo "🔑 Enabling required GCP APIs for $(CLEAN_PROJECT_ID)..."
	gcloud services enable \
		run.googleapis.com \
		cloudbuild.googleapis.com \
		artifactregistry.googleapis.com \
		aiplatform.googleapis.com \
		storage.googleapis.com \
		--project $(CLEAN_PROJECT_ID)
	@echo "✓ Required Google Cloud APIs enabled."

.PHONY: auth-check
auth-check: ## Strictly verify authentication to the specific project in .env
	@$(UV) run python scripts/verify_gcp_auth.py

.PHONY: auth-fix
auth-fix: ## Automatically set gcloud project and ADC quota project to match .env
	@$(UV) run python scripts/verify_gcp_auth.py --fix

.PHONY: bucket
bucket: ## Provision GCS bucket with 5-char random suffix & lifecycle rule (30-day default vs 0)
	@$(UV) run python scripts/setup_bucket.py

.PHONY: bucket-info
bucket-info: ## Inspect existing GCS bucket, lifecycle rules, and prefix IAM condition policies
	@$(UV) run python scripts/setup_bucket.py --info

# ------------------------------------------------------------------------------
# 3. Phase 1: Core Voice Generation & Multimodal Judging
# ------------------------------------------------------------------------------

.PHONY: test-core
test-core: ## Run quickstart end-to-end test on sample article fixture using uv run
	@$(UV) run python scripts/run_quickstart.py --file scripts/samples/sample_article.md --persona "Retail Banking Guide"

.PHONY: synth
synth: ## Synthesize pasted text (Usage: make synth TEXT="Your text..." [PERSONA="Retail Banking Guide"])
	@if [ -z "$(TEXT)" ]; then \
		echo "Error: TEXT variable required. Example: make synth TEXT='Hello world'"; \
		exit 1; \
	fi
	@$(UV) run python scripts/run_quickstart.py --text "$(TEXT)" --persona "$(or $(PERSONA),Retail Banking Guide)"

.PHONY: synth-file
synth-file: ## Synthesize from a markdown/text file (Usage: make synth-file FILE=path/to/file.md)
	@if [ -z "$(FILE)" ]; then \
		echo "Error: FILE variable required. Example: make synth-file FILE=article.md"; \
		exit 1; \
	fi
	@$(UV) run python scripts/run_quickstart.py --file "$(FILE)" --persona "$(or $(PERSONA),Retail Banking Guide)"

.PHONY: synth-only
synth-only: ## Synthesize audio without running LLM Judge (Usage: make synth-only FILE=article.md)
	@$(UV) run python scripts/run_quickstart.py --file "$(or $(FILE),scripts/samples/sample_article.md)" --skip-judge

# ------------------------------------------------------------------------------
# 4. Testing & Code Quality
# ------------------------------------------------------------------------------

.PHONY: test
test: ## Run unit tests with pytest via uv
	@$(UV) run pytest tests/ -v

.PHONY: test-menu
test-menu: ## Launch interactive step-by-step test runner
	@./test_interactive.sh

.PHONY: ui
ui: ## Launch the Web UI Studio on http://127.0.0.1:8000
	@echo "🚀 Launching Apex Bank Knowledge-to-Speech Studio on http://127.0.0.1:8000..."
	@$(UV) run uvicorn src.ui.app:app --host 127.0.0.1 --port 8000

.PHONY: ui-dev
ui-dev: ## Launch the Web UI Studio in auto-reload development mode
	@echo "🚀 Launching Apex Bank Studio in Dev Mode on http://127.0.0.1:8000..."
	@$(UV) run uvicorn src.ui.app:app --host 127.0.0.1 --port 8000 --reload

.PHONY: clean
clean: ## Remove caches, build artifacts, and virtual environment
	@rm -rf .venv .pytest_cache .coverage __pycache__ src/**/__pycache__ tests/__pycache__
	@echo "✓ Cleaned temporary caches and virtual environment."

# ------------------------------------------------------------------------------
# 5. Cloud Run Deployment & Containerization (Python 3.13)
# ------------------------------------------------------------------------------

SERVICE_NAME ?= tts-studio

# Strip quotes and sanitize env variables for gcloud CLI
CLEAN_PROJECT_ID := $(subst ",,$(GCP_PROJECT_ID))
CLEAN_LOCATION := $(or $(subst ",,$(GCP_LOCATION)),us-central1)
CLEAN_BUCKET := $(subst ",,$(GCS_BUCKET_NAME))
CLEAN_VOICE_MODEL := $(or $(subst ",,$(GEMINI_VOICE_MODEL)),gemini-3.1-flash-tts-preview)
CLEAN_JUDGE_MODEL := $(or $(subst ",,$(GEMINI_JUDGE_MODEL)),gemini-3.8-flash)
CLEAN_JUDGE_LOCATION := $(or $(subst ",,$(GEMINI_JUDGE_LOCATION)),global)
CLEAN_PERSONA := $(or $(subst ",,$(DEFAULT_VOICE_PERSONA)),Retail Banking Guide)
CLEAN_BITRATE := $(or $(subst ",,$(AUDIO_BITRATE)),320k)

.PHONY: docker-build
docker-build: ## Build local Docker container image with Python 3.13
	@echo "🐳 Building Docker image $(SERVICE_NAME):latest using Python 3.13..."
	@docker build -t $(SERVICE_NAME):latest .

.PHONY: docker-run
docker-run: ## Run Docker container locally on http://localhost:8080
	@echo "🐳 Running $(SERVICE_NAME) on http://localhost:8080..."
	@docker run -p 8080:8080 --env-file .env $(SERVICE_NAME):latest

.PHONY: deploy
deploy: ## Deploy application directly to Google Cloud Run via Cloud Build
	@if [ -z "$(CLEAN_PROJECT_ID)" ] || [ "$(CLEAN_PROJECT_ID)" = "your-gcp-project-id" ]; then \
		echo "⚠️ Error: GCP_PROJECT_ID is not set in .env. Please configure .env first."; \
		exit 1; \
	fi
	@echo "🚀 Deploying $(SERVICE_NAME) to Google Cloud Run..."
	@echo "   Project:  $(CLEAN_PROJECT_ID)"
	@echo "   Region:   $(CLEAN_LOCATION)"
	@echo "   Service:  $(SERVICE_NAME)"
	gcloud run deploy $(SERVICE_NAME) \
		--project $(CLEAN_PROJECT_ID) \
		--region $(CLEAN_LOCATION) \
		--source . \
		--allow-unauthenticated \
		--set-env-vars '^##^GCP_PROJECT_ID=$(CLEAN_PROJECT_ID)##GCP_LOCATION=$(CLEAN_LOCATION)##GCS_BUCKET_NAME=$(CLEAN_BUCKET)##GEMINI_VOICE_MODEL=$(CLEAN_VOICE_MODEL)##GEMINI_JUDGE_MODEL=$(CLEAN_JUDGE_MODEL)##GEMINI_JUDGE_LOCATION=$(CLEAN_JUDGE_LOCATION)##DEFAULT_VOICE_PERSONA=$(CLEAN_PERSONA)##AUDIO_BITRATE=$(CLEAN_BITRATE)'

.PHONY: cloud-run-logs
cloud-run-logs: ## Stream live logs from the deployed Cloud Run service
	@gcloud run services logs tail $(SERVICE_NAME) --project $(CLEAN_PROJECT_ID) --region $(CLEAN_LOCATION)

.PHONY: cloud-run-url
cloud-run-url: ## Print the live HTTPS URL of the deployed Cloud Run service
	@gcloud run services describe $(SERVICE_NAME) --project $(CLEAN_PROJECT_ID) --region $(CLEAN_LOCATION) --format 'value(status.url)'

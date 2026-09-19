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
auth: ## Authenticate to GCP and configure Application Default Credentials (ADC)
	@if [ -z "$(GCP_PROJECT_ID)" ] || [ "$(GCP_PROJECT_ID)" = "your-gcp-project-id" ]; then \
		echo "⚠️ Warning: GCP_PROJECT_ID is not set in .env. Please configure .env first."; \
		exit 1; \
	fi
	@echo "🔐 Configuring Google Cloud Project: $(GCP_PROJECT_ID)..."
	@gcloud config set project $(GCP_PROJECT_ID)
	@echo "🔐 Setting up Application Default Credentials (ADC)..."
	@gcloud auth application-default login
	@echo "🔐 Setting ADC Quota Project to $(GCP_PROJECT_ID)..."
	@gcloud auth application-default set-quota-project $(GCP_PROJECT_ID)
	@echo "✓ GCP Authentication complete for project: $(GCP_PROJECT_ID)"

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
GCP_LOCATION ?= us-central1

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
	@if [ -z "$(GCP_PROJECT_ID)" ] || [ "$(GCP_PROJECT_ID)" = "your-gcp-project-id" ]; then \
		echo "⚠️ Error: GCP_PROJECT_ID is not set in .env. Please configure .env first."; \
		exit 1; \
	fi
	@echo "🚀 Deploying $(SERVICE_NAME) to Google Cloud Run..."
	@echo "   Project:  $(GCP_PROJECT_ID)"
	@echo "   Region:   $(GCP_LOCATION)"
	@echo "   Service:  $(SERVICE_NAME)"
	gcloud run deploy $(SERVICE_NAME) \
		--project $(GCP_PROJECT_ID) \
		--region $(GCP_LOCATION) \
		--source . \
		--allow-unauthenticated \
		--set-env-vars "GCP_PROJECT_ID=$(GCP_PROJECT_ID),GCP_LOCATION=$(GCP_LOCATION),GCS_BUCKET_NAME=$(GCS_BUCKET_NAME),GEMINI_VOICE_MODEL=$(GEMINI_VOICE_MODEL),GEMINI_JUDGE_MODEL=$(GEMINI_JUDGE_MODEL),DEFAULT_VOICE_PERSONA=$(DEFAULT_VOICE_PERSONA),AUDIO_BITRATE=$(AUDIO_BITRATE)"

.PHONY: cloud-run-logs
cloud-run-logs: ## Stream live logs from the deployed Cloud Run service
	@gcloud run services logs tail $(SERVICE_NAME) --project $(GCP_PROJECT_ID) --region $(GCP_LOCATION)

.PHONY: cloud-run-url
cloud-run-url: ## Print the live HTTPS URL of the deployed Cloud Run service
	@gcloud run services describe $(SERVICE_NAME) --project $(GCP_PROJECT_ID) --region $(GCP_LOCATION) --format 'value(status.url)'

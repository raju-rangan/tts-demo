# ==============================================================================
# Knowledge Article to Speech & Multimodal LLM-as-a-Judge Platform
# ==============================================================================

SHELL := /bin/bash
UV    ?= uv

# Load .env variables safely (ignoring comments and empty lines)
SH_COMMENT := \#
ifneq (,$(wildcard .env))
    -include .env
    export $(shell [ -f .env ] && grep -v "^[[:space:]]*$(SH_COMMENT)" .env 2>/dev/null | grep "=" | cut -d= -f1)
endif

# Lazy evaluation: gcloud is only queried if GCP_PROJECT_ID is not set in .env
RAW_PROJECT     = $(subst ",,$(GCP_PROJECT_ID))
CLEANED_PROJECT = $(if $(filter your-gcp-project-id,$(RAW_PROJECT)),,$(RAW_PROJECT))
GCP_PROJECT    ?= $(or $(CLEANED_PROJECT),$(shell gcloud config get-value project 2>/dev/null))
GCP_REGION     ?= $(or $(subst ",,$(GCP_LOCATION)),us-central1)
SERVICE_NAME   ?= tts-studio

.DEFAULT_GOAL := help

# ------------------------------------------------------------------------------
# Help Target (Categorized)
# ------------------------------------------------------------------------------

.PHONY: help
help: ## Show this help message
	@echo "======================================================================"
	@echo "🎙️ Knowledge-to-Speech Platform Developer Commands (powered by uv)"
	@echo "======================================================================"
	@awk 'BEGIN {FS = ":.*##"} \
		/^##@/ { printf "\n\033[1;35m%s\033[0m\n", substr($$0, 5) } \
		/^[a-zA-Z0-9_-]+:.*##/ { printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)
	@echo ""

##@ 1. Environment & Setup
.PHONY: venv install setup
venv: ## Create Python virtual environment using uv
	@echo "Creating virtual environment with uv..."
	@$(UV) venv .venv

install: ## Sync and install dependencies using uv
	@echo "Installing dependencies with uv..."
	@$(UV) pip install -e .
	@if [ ! -f .env ] && [ -f .env.example ]; then \
		echo "Creating .env from .env.example..."; \
		cp .env.example .env; \
	fi
	@echo "✓ Setup complete with uv. Edit .env with your GCP project settings."

setup: venv install ## Run complete setup (venv + dependencies + .env template)

##@ 2. Google Cloud Authentication & Configuration
.PHONY: auth auth-force auth-cli auth-adc enable-apis auth-check auth-fix bucket bucket-info
auth: ## Authenticate GCP CLI and ADC (auto-bypasses if already authenticated)
	@if [ -z "$(GCP_PROJECT)" ]; then \
		echo "⚠️ Warning: GCP_PROJECT_ID is not set in .env and no active gcloud project found. Please configure .env or gcloud first."; \
		exit 1; \
	fi
	@echo "🔍 Checking GCP authentication state for $(GCP_PROJECT)..."
	@ACTIVE_ACCOUNT=$$(gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null); \
	if [ -n "$$ACTIVE_ACCOUNT" ]; then \
		echo "✓ 1. gcloud CLI already authenticated as $$ACTIVE_ACCOUNT (skipping login)"; \
	else \
		echo "🔐 1. Authenticating gcloud CLI user account..."; \
		gcloud auth login; \
	fi
	@CURRENT_PROJ=$$(gcloud config get-value project 2>/dev/null); \
	if [ "$$CURRENT_PROJ" = "$(GCP_PROJECT)" ]; then \
		echo "✓ 2. Active gcloud project already set to $(GCP_PROJECT)"; \
	else \
		echo "🔐 2. Setting active gcloud project to $(GCP_PROJECT)..."; \
		gcloud config set project $(GCP_PROJECT); \
	fi
	@if gcloud auth application-default print-access-token >/dev/null 2>&1; then \
		echo "✓ 3. Application Default Credentials (ADC) already active (skipping login)"; \
	else \
		echo "🔐 3. Setting up Application Default Credentials (ADC) for Python SDK..."; \
		gcloud auth application-default login; \
	fi
	@ADC_FILE="$$HOME/.config/gcloud/application_default_credentials.json"; \
	if [ -f "$$ADC_FILE" ] && grep -q '"quota_project_id": "$(GCP_PROJECT)"' "$$ADC_FILE" 2>/dev/null; then \
		echo "✓ 4. ADC Quota Project already set to $(GCP_PROJECT)"; \
	else \
		echo "🔐 4. Setting ADC Quota Project to $(GCP_PROJECT)..."; \
		gcloud auth application-default set-quota-project $(GCP_PROJECT); \
	fi
	@echo "✓ GCP Authentication fully verified for project: $(GCP_PROJECT)"

auth-force: ## Force full interactive re-login for both gcloud CLI and ADC
	@if [ -z "$(GCP_PROJECT)" ]; then \
		echo "⚠️ Warning: GCP_PROJECT_ID is not set in .env and no active gcloud project found. Please configure .env or gcloud first."; \
		exit 1; \
	fi
	@echo "🔐 1. Force re-authenticating gcloud CLI user account..."
	@gcloud auth login
	@echo "🔐 2. Configuring active Google Cloud Project: $(GCP_PROJECT)..."
	@gcloud config set project $(GCP_PROJECT)
	@echo "🔐 3. Force re-authenticating Application Default Credentials (ADC)..."
	@gcloud auth application-default login
	@echo "🔐 4. Setting ADC Quota Project to $(GCP_PROJECT)..."
	@gcloud auth application-default set-quota-project $(GCP_PROJECT)
	@echo "✓ GCP Authentication complete for CLI and ADC (project: $(GCP_PROJECT))"

auth-cli: ## Authenticate gcloud CLI user account (auto-bypasses if already authenticated)
	@ACTIVE_ACCOUNT=$$(gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null); \
	if [ -n "$$ACTIVE_ACCOUNT" ]; then \
		echo "✓ gcloud CLI already authenticated as $$ACTIVE_ACCOUNT"; \
	else \
		echo "🔐 Authenticating gcloud CLI user account..."; \
		gcloud auth login; \
	fi; \
	gcloud config set project $(GCP_PROJECT)

auth-adc: ## Authenticate Application Default Credentials (auto-bypasses if already active)
	@if gcloud auth application-default print-access-token >/dev/null 2>&1; then \
		echo "✓ Application Default Credentials (ADC) already active"; \
	else \
		echo "🔐 Setting up Application Default Credentials (ADC)..."; \
		gcloud auth application-default login; \
	fi; \
	gcloud auth application-default set-quota-project $(GCP_PROJECT)

enable-apis: ## Enable required GCP APIs (Cloud Run, Cloud Build, Artifact Registry, Vertex AI, GCS)
	@echo "🔑 Enabling required GCP APIs for $(GCP_PROJECT)..."
	gcloud services enable \
		run.googleapis.com \
		cloudbuild.googleapis.com \
		artifactregistry.googleapis.com \
		aiplatform.googleapis.com \
		storage.googleapis.com \
		--project $(GCP_PROJECT)
	@echo "✓ Required Google Cloud APIs enabled."

auth-check: ## Strictly verify authentication to the specific project in .env
	@$(UV) run python scripts/verify_gcp_auth.py

auth-fix: ## Automatically set gcloud project and ADC quota project to match .env
	@$(UV) run python scripts/verify_gcp_auth.py --fix

bucket: ## Provision GCS bucket with 5-char random suffix & lifecycle rule
	@$(UV) run python scripts/setup_bucket.py

bucket-info: ## Inspect existing GCS bucket, lifecycle rules, and prefix IAM policies
	@$(UV) run python scripts/setup_bucket.py --info

##@ 3. Core Voice Generation & Multimodal Judging
.PHONY: test-core synth synth-file synth-only
test-core: ## Run quickstart end-to-end test on sample article fixture using uv run
	@$(UV) run python scripts/run_quickstart.py --file scripts/samples/sample_article.md --persona "Retail Banking Guide"

synth: ## Synthesize text or file (Usage: make synth TEXT="..." [PERSONA="..."] or FILE="...")
	@if [ -n "$(TEXT)" ]; then \
		$(UV) run python scripts/run_quickstart.py --text "$(TEXT)" --persona "$(or $(PERSONA),Retail Banking Guide)"; \
	elif [ -n "$(FILE)" ]; then \
		$(UV) run python scripts/run_quickstart.py --file "$(FILE)" --persona "$(or $(PERSONA),Retail Banking Guide)"; \
	else \
		echo "Error: Either TEXT or FILE variable required."; \
		echo "Example: make synth TEXT='Hello world'"; \
		echo "Example: make synth FILE=scripts/samples/sample_article.md"; \
		exit 1; \
	fi

synth-file: ## Synthesize from a markdown/text file (Usage: make synth-file FILE=path/to/file.md)
	@if [ -z "$(FILE)" ]; then \
		echo "Error: FILE variable required. Example: make synth-file FILE=article.md"; \
		exit 1; \
	fi
	@$(UV) run python scripts/run_quickstart.py --file "$(FILE)" --persona "$(or $(PERSONA),Retail Banking Guide)"

synth-only: ## Synthesize audio without running LLM Judge (Usage: make synth-only FILE=article.md)
	@$(UV) run python scripts/run_quickstart.py --file "$(or $(FILE),scripts/samples/sample_article.md)" --skip-judge

##@ 4. Web UI & Testing
.PHONY: ui ui-dev test test-menu clean clean-all
ui: ## Launch the Web UI Studio on http://127.0.0.1:8000
	@echo "🚀 Launching Apex Bank Knowledge-to-Speech Studio on http://127.0.0.1:8000..."
	@$(UV) run uvicorn src.ui.app:app --host 127.0.0.1 --port 8000

ui-dev: ## Launch the Web UI Studio in auto-reload development mode
	@echo "🚀 Launching Apex Bank Studio in Dev Mode on http://127.0.0.1:8000..."
	@$(UV) run uvicorn src.ui.app:app --host 127.0.0.1 --port 8000 --reload

test: ## Run unit tests with pytest via uv
	@$(UV) run pytest tests/ -v

test-menu: ## Launch interactive step-by-step test runner
	@./test_interactive.sh

clean: ## Remove temporary caches, coverage, and build artifacts (preserves .venv)
	@rm -rf .pytest_cache .coverage build dist *.egg-info src/*.egg-info
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "✓ Cleaned temporary caches and build artifacts (virtualenv preserved)."

clean-all: clean ## Remove caches AND the Python virtual environment (.venv)
	@rm -rf .venv
	@echo "✓ Removed virtual environment (.venv)."

##@ 5. Cloud Run Deployment & Containers
.PHONY: docker-build docker-run deploy migrate-data cloud-run-proxy cloud-run-logs cloud-run-url
docker-build: ## Build local Docker container image with Python 3.13
	@echo "🐳 Building Docker image $(SERVICE_NAME):latest using Python 3.13..."
	@docker build -t $(SERVICE_NAME):latest .

docker-run: ## Run Docker container locally on http://localhost:8080
	@echo "🐳 Running $(SERVICE_NAME) on http://localhost:8080..."
	@docker run -p 8080:8080 --env-file .env $(SERVICE_NAME):latest

deploy: ## Deploy application directly to Google Cloud Run via Cloud Build
	@if [ -z "$(GCP_PROJECT)" ]; then \
		echo "⚠️ Error: GCP_PROJECT_ID is not set in .env and no active gcloud project found. Please configure .env first."; \
		exit 1; \
	fi
	@echo "🚀 Deploying $(SERVICE_NAME) to Google Cloud Run..."
	@echo "   Project:  $(GCP_PROJECT)"
	@echo "   Region:   $(GCP_REGION)"
	@echo "   Service:  $(SERVICE_NAME)"
	gcloud run deploy $(SERVICE_NAME) \
		--project $(GCP_PROJECT) \
		--region $(GCP_REGION) \
		--source . \
		--no-invoker-iam-check \
		--set-env-vars '^##^GCP_PROJECT_ID=$(GCP_PROJECT)##GCP_LOCATION=$(GCP_REGION)##GCS_BUCKET_NAME=$(subst ",,$(GCS_BUCKET_NAME))##GEMINI_VOICE_MODEL=$(or $(subst ",,$(GEMINI_VOICE_MODEL)),gemini-3.1-flash-tts-preview)##GEMINI_JUDGE_MODEL=$(or $(subst ",,$(GEMINI_JUDGE_MODEL)),gemini-3.8-flash)##GEMINI_JUDGE_LOCATION=$(or $(subst ",,$(GEMINI_JUDGE_LOCATION)),global)##DEFAULT_VOICE_PERSONA=$(or $(subst ",,$(DEFAULT_VOICE_PERSONA)),Retail Banking Guide)##AUDIO_BITRATE=$(or $(subst ",,$(AUDIO_BITRATE)),320k)##GOOGLE_CLIENT_ID=$(or $(subst ",,$(GOOGLE_CLIENT_ID)),716595821548-mmgp3ivk20bboapvlsru7kh08dp0n7c7.apps.googleusercontent.com)##GCIP_API_KEY=$(subst ",,$(GCIP_API_KEY))##GCIP_AUTH_DOMAIN=$(or $(subst ",,$(GCIP_AUTH_DOMAIN)),$(GCP_PROJECT).firebaseapp.com)##ALLOWED_DOMAINS=$(subst ",,$(ALLOWED_DOMAINS))##ALLOWED_USERS=$(subst ",,$(ALLOWED_USERS))##ENABLE_DEMO_AUTH=$(or $(subst ",,$(ENABLE_DEMO_AUTH)),false)##USE_FIRESTORE=$(or $(subst ",,$(USE_FIRESTORE)),true)##FIRESTORE_DATABASE=$(or $(subst ",,$(FIRESTORE_DATABASE)),tts-jobs)##FIRESTORE_COLLECTION=$(or $(subst ",,$(FIRESTORE_COLLECTION)),tts_jobs)'

update-firestore-costs: ## Recalculate historical job costs in Cloud Firestore
	@echo "📊 Recalculating historical job costs in Google Cloud Firestore..."
	@$(UV) run python scripts/recalculate_firestore_costs.py

cloud-run-proxy: ## Launch local authenticated proxy tunnel to the Cloud Run service
	@echo "🌐 Starting authenticated Cloud Run proxy for $(SERVICE_NAME) on http://localhost:8080..."
	gcloud run services proxy $(SERVICE_NAME) --project $(GCP_PROJECT) --region $(GCP_REGION) --port 8080

cloud-run-logs: ## Stream live logs from the deployed Cloud Run service
	@gcloud run services logs tail $(SERVICE_NAME) --project $(GCP_PROJECT) --region $(GCP_REGION)

cloud-run-url: ## Print the live HTTPS URL of the deployed Cloud Run service
	@gcloud run services describe $(SERVICE_NAME) --project $(GCP_PROJECT) --region $(GCP_REGION) --format 'value(status.url)'

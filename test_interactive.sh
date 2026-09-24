#!/usr/bin/env bash
# ==============================================================================
# Interactive Step-by-Step Test Runner for Knowledge-to-Speech Platform
# Powered by Gemini 3 & Google Cloud Storage
# ==============================================================================

set -e

# Color definitions
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Navigate to project root
SCRIPT_SOURCE="${BASH_SOURCE[0]:-${(%):-%x}}"
if [ -n "$SCRIPT_SOURCE" ] && [ "$SCRIPT_SOURCE" != "zsh" ] && [ -f "$SCRIPT_SOURCE" ]; then
    SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_SOURCE")" && pwd)"
    cd "$SCRIPT_DIR"
fi

# Load .env if present
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

UV_BIN="$(command -v uv || echo "uv")"

print_header() {
    clear 2>/dev/null || true
    echo -e "${CYAN}======================================================================${NC}"
    echo -e "${BOLD}🎙️ Knowledge-to-Speech Platform: Step-by-Step Test Runner${NC}"
    echo -e "${CYAN}======================================================================${NC}"
    echo -e "Project ID:     ${GREEN}${GCP_PROJECT_ID:-Not configured}${NC}"
    echo -e "GCS Bucket:     ${GREEN}${GCS_BUCKET_NAME:-Auto-provisioned on demand}${NC}"
    echo -e "Voice Model:    ${MAGENTA}${GEMINI_VOICE_MODEL:-gemini-3.1-flash-tts-preview}${NC}"
    echo -e "Judge Model:    ${MAGENTA}${GEMINI_JUDGE_MODEL:-gemini-3.1-pro-preview}${NC}"
    echo -e "Expiration:     ${YELLOW}${GCS_OBJECT_EXPIRATION_DAYS:-30} days (0 = indefinite)${NC}"
    echo -e "${CYAN}----------------------------------------------------------------------${NC}"
}

pause() {
    echo ""
    echo -e "${YELLOW}Press [Enter] to return to the menu...${NC}"
    read -r
}

# Step 1: Unit Tests
run_unit_tests() {
    echo -e "\n${BOLD}${CYAN}▶ Step 1: Running Offline Unit Tests (Pytest via uv)...${NC}"
    echo -e "${YELLOW}Verifies: Persona prompt guidelines, prefix routing, bucket naming, and Gemini 3 settings.${NC}\n"
    "$UV_BIN" run pytest tests/ -v
    pause
}

# Step 2: GCP Authentication Check
check_gcp_auth() {
    echo -e "\n${BOLD}${CYAN}▶ Step 2: Verifying Target GCP Project Authentication (${GCP_PROJECT_ID})...${NC}\n"
    "$UV_BIN" run python scripts/verify_gcp_auth.py || true
    pause
}

# Step 3: Provision GCS Bucket
setup_bucket() {
    echo -e "\n${BOLD}${CYAN}▶ Step 3: Provisioning / Inspecting GCS Audio Bucket...${NC}"
    echo -e "${YELLOW}Creates {base}-{random5} if needed, configures 30-day lifecycle rule, and prints IAM condition CEL.${NC}\n"
    "$UV_BIN" run python scripts/setup_bucket.py
    
    # Reload .env in case bucket name was saved
    if [ -f .env ]; then
        set -a
        source .env
        set +a
    fi
    pause
}

# Step 4: Fast Audio Synthesis (Skip Judge)
synth_sample_audio() {
    echo -e "\n${BOLD}${CYAN}▶ Step 4: Synthesizing Audio (Gemini 3.1 Flash TTS - Fast)...${NC}"
    echo -e "${YELLOW}Synthesizes scripts/samples/sample_article.md and uploads MP3 to GCS.${NC}\n"
    "$UV_BIN" run python scripts/run_quickstart.py \
        --file scripts/samples/sample_article.md \
        --persona "Retail Banking Guide" \
        --skip-judge \
        --local-out "scripts/samples/latest_generated.mp3"
    
    echo -e "\n${GREEN}✓ Local test audio saved to: scripts/samples/latest_generated.mp3${NC}"
    pause
}

# Step 5: Full End-to-End Pipeline (Synthesis + Multimodal Judge)
run_full_e2e() {
    echo -e "\n${BOLD}${CYAN}▶ Step 5: Running Full End-to-End Pipeline with Multimodal Judge...${NC}"
    echo -e "${YELLOW}Gemini 3.1 Flash TTS (Voice) ➔ GCS Upload ➔ Gemini 3.1 Pro (Quality Judge).${NC}\n"
    "$UV_BIN" run python scripts/run_quickstart.py \
        --file scripts/samples/sample_article.md \
        --persona "Retail Banking Guide" \
        --local-out "scripts/samples/latest_generated.mp3"
    pause
}

# Step 6: Test Custom Persona
test_custom_persona() {
    echo -e "\n${BOLD}${CYAN}▶ Step 6: Test Specific Banking Voice Persona...${NC}\n"
    echo "Choose a financial persona to test:"
    echo "  1) Retail Banking Guide            (Audience: External Customers | Voice: Sulafat)"
    echo "  2) Wealth & Market Advisor         (Audience: External Customers | Voice: Charon)"
    echo "  3) Regulatory & Policy Officer     (Audience: Internal Employees | Voice: Kore)"
    echo "  4) Employee Enablement & Ops       (Audience: Internal Employees | Voice: Enceladus)"
    echo "  5) Fraud & Security Alert          (Audience: Both / Shared      | Voice: Schedar)"
    echo ""
    printf "Enter selection [1-5]: "
    read -r p_choice

    case "$p_choice" in
        1) SELECTED_PERSONA="Retail Banking Guide" ;;
        2) SELECTED_PERSONA="Wealth & Market Advisor" ;;
        3) SELECTED_PERSONA="Regulatory & Policy Officer" ;;
        4) SELECTED_PERSONA="Employee Enablement & Operations" ;;
        5) SELECTED_PERSONA="Fraud & Security Alert" ;;
        *) echo -e "${RED}Invalid selection.${NC}"; pause; return ;;
    esac

    echo -e "\n${MAGENTA}Testing with Persona: ${SELECTED_PERSONA}${NC}"
    "$UV_BIN" run python scripts/run_quickstart.py \
        --file scripts/samples/sample_article.md \
        --persona "$SELECTED_PERSONA" \
        --local-out "scripts/samples/latest_${p_choice}.mp3"
    pause
}

# Step 7: Inspect GCS Objects by Prefix
list_gcs_objects() {
    echo -e "\n${BOLD}${CYAN}▶ Step 7: Inspect GCS Bucket Audio Objects by Prefix...${NC}\n"
    if [ -z "$GCS_BUCKET_NAME" ]; then
        echo -e "${RED}No GCS_BUCKET_NAME configured. Run Step 3 first.${NC}"
        pause
        return
    fi

    echo -e "Listing files in ${GREEN}gs://${GCS_BUCKET_NAME}/${NC}:\n"
    gcloud storage ls --recursive "gs://${GCS_BUCKET_NAME}/**" || gsutil ls -r "gs://${GCS_BUCKET_NAME}/**" || true
    pause
}

# Step 8: Launch Web Studio UI
launch_web_ui() {
    echo -e "\n${BOLD}${CYAN}▶ Step 8: Launching Apex Bank Knowledge-to-Speech Studio...${NC}"
    echo -e "${GREEN}Server running on: http://127.0.0.1:8000${NC}"
    echo -e "${dim}Demo Login credentials: admin@apexbank.com / demo1234${NC}\n"
    "$UV_BIN" run uvicorn src.ui.app:app --host 127.0.0.1 --port 8000
    pause
}

# Main Menu Loop
while true; do
    print_header
    echo -e "${BOLD}Select a test step to execute:${NC}\n"
    echo -e "  ${CYAN}[1]${NC} Run Offline Unit Tests          ${dim}(No GCP needed - fast validation)${NC}"
    echo -e "  ${CYAN}[2]${NC} Check GCP Authentication        ${dim}(Verifies gcloud & ADC credentials)${NC}"
    echo -e "  ${CYAN}[3]${NC} Provision / Verify GCS Bucket   ${dim}(Creates bucket with random suffix & 30d rule)${NC}"
    echo -e "  ${CYAN}[4]${NC} Synthesize Audio Only (Fast)    ${dim}(Gemini 3.1 Flash TTS -> GCS + local MP3)${NC}"
    echo -e "  ${CYAN}[5]${NC} Full End-to-End with Judge      ${dim}(Voice Synthesis + Gemini 3.8 Flash Judge)${NC}"
    echo -e "  ${CYAN}[6]${NC} Test Different Banking Personas ${dim}(Retail, Wealth, Compliance, Ops, Fraud)${NC}"
    echo -e "  ${CYAN}[7]${NC} List Audio Files by GCS Prefix  ${dim}(Inspect external/, internal/, shared/)${NC}"
    echo -e "  ${CYAN}[8]${NC} Launch Web Studio UI            ${dim}(http://127.0.0.1:8000 - Jobs, Tokens, Audio)${NC}"
    echo -e "  ${CYAN}[q]${NC} Exit"
    echo ""
    printf "Enter option [1-8, q]: "
    read -r option

    case "$option" in
        1) run_unit_tests ;;
        2) check_gcp_auth ;;
        3) setup_bucket ;;
        4) synth_sample_audio ;;
        5) run_full_e2e ;;
        6) test_custom_persona ;;
        7) list_gcs_objects ;;
        8) launch_web_ui ;;
        q|Q) echo -e "\n${GREEN}Exiting test runner. Happy testing!${NC}\n"; return 0 2>/dev/null || exit 0 ;;
        *) echo -e "\n${RED}Invalid option. Please choose 1-8 or q.${NC}"; sleep 1 ;;
    esac
done

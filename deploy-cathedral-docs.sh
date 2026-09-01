#!/bin/bash
# deploy-cathedral-docs.sh — Batch deploy cathedral documentation to 28+ repos
# Part of the cathedral-status uplift audit workflow (wisdom-scaffold)
#
# Usage:
#   ./deploy-cathedral-docs.sh [--limit N] [--dry-run] [--output LOG_FILE]
#
# Options:
#   --limit N        Only deploy to first N repos (default: all)
#   --dry-run        Show what would be done without pushing
#   --output FILE    Write log to FILE (default: stdout)
#
# Requirements:
#   - gh (GitHub CLI) authenticated
#   - git configured
#   - bash 4.0+
#
# This script:
#   1. Reads the deployment manifest (built by cathedral-status.sh audit)
#   2. For each target repo: clones, customizes templates, commits, pushes
#   3. Supports --dry-run (idempotent, safe to re-run)
#   4. Skips forks and archived repos (manifest already excludes them)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DRY_RUN=0
LIMIT=999999
OUTPUT_FILE=""
LOG_OUTPUT="/dev/stdout"

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --limit)
      LIMIT="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --output)
      OUTPUT_FILE="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

# Setup logging
if [[ -n "$OUTPUT_FILE" ]]; then
  LOG_OUTPUT="$OUTPUT_FILE"
  mkdir -p "$(dirname "$OUTPUT_FILE")"
fi

log() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_OUTPUT"
}

log "=== Cathedral Docs Deployment ==="
log "Dry-run: $DRY_RUN"
log "Limit: $LIMIT repos"
log "Script dir: $SCRIPT_DIR"

# Verify requirements
if ! command -v gh &> /dev/null; then
  log "ERROR: 'gh' (GitHub CLI) not found. Run: gh auth login"
  exit 1
fi

if ! command -v git &> /dev/null; then
  log "ERROR: 'git' not found."
  exit 1
fi

# License source
LICENSE_FILE="$SCRIPT_DIR/LICENSE"
if [[ ! -f "$LICENSE_FILE" ]]; then
  log "ERROR: LICENSE file not found at $LICENSE_FILE"
  exit 1
fi

# Template directory
TEMPLATE_DIR="$SCRIPT_DIR/docs/cathedral-uplift"
if [[ ! -d "$TEMPLATE_DIR" ]]; then
  log "ERROR: Template directory not found at $TEMPLATE_DIR"
  log "Please run cathedral-status.sh --help first to set up templates."
  exit 1
fi

# Working directory for clones
WORK_DIR="/tmp/cathedral-deploy-$$"
mkdir -p "$WORK_DIR"
log "Work directory: $WORK_DIR"

cleanup() {
  if [[ -d "$WORK_DIR" ]]; then
    log "Cleaning up $WORK_DIR"
    rm -rf "$WORK_DIR"
  fi
}
trap cleanup EXIT

# Repos to deploy (hardcoded from manifest; can be extended)
REPOS=(
  "aerocement:GOVERNANCE.md,ROADMAP.md,.github/ISSUE_TEMPLATE/bug_report.md,.github/ISSUE_TEMPLATE/feature_request.md"
  "aerocement-calc:GOVERNANCE.md,ROADMAP.md,.github/ISSUE_TEMPLATE/bug_report.md,.github/ISSUE_TEMPLATE/feature_request.md"
  "AeroCement_Ecosystem:CONTRIBUTING.md,GOVERNANCE.md,ROADMAP.md,.github/ISSUE_TEMPLATE/bug_report.md,.github/ISSUE_TEMPLATE/feature_request.md"
  "agape-coordination:CONTRIBUTING.md,GOVERNANCE.md,ROADMAP.md,.github/ISSUE_TEMPLATE/bug_report.md,.github/ISSUE_TEMPLATE/feature_request.md"
  "agape-crossover-key:LICENSE,CONTRIBUTING.md,.github/ISSUE_TEMPLATE/bug_report.md,.github/ISSUE_TEMPLATE/feature_request.md"
  "agape-ipfs:GOVERNANCE.md,ROADMAP.md,.github/ISSUE_TEMPLATE/bug_report.md,.github/ISSUE_TEMPLATE/feature_request.md"
  "agape-primitives:LICENSE,CONTRIBUTING.md,GOVERNANCE.md,ROADMAP.md,.github/ISSUE_TEMPLATE/bug_report.md,.github/ISSUE_TEMPLATE/feature_request.md"
  "agape-une:CONTRIBUTING.md,GOVERNANCE.md,ROADMAP.md,.github/ISSUE_TEMPLATE/bug_report.md,.github/ISSUE_TEMPLATE/feature_request.md"
  "agapenet:LICENSE,CONTRIBUTING.md,GOVERNANCE.md,ROADMAP.md,.github/ISSUE_TEMPLATE/bug_report.md,.github/ISSUE_TEMPLATE/feature_request.md"
  "agaperesonance:LICENSE,CONTRIBUTING.md,GOVERNANCE.md,ROADMAP.md,.github/ISSUE_TEMPLATE/bug_report.md,.github/ISSUE_TEMPLATE/feature_request.md"
  "axiom-library:LICENSE,README.md,CONTRIBUTING.md,GOVERNANCE.md,ROADMAP.md,.github/ISSUE_TEMPLATE/bug_report.md,.github/ISSUE_TEMPLATE/feature_request.md"
  "black-locust-rmh:GOVERNANCE.md,ROADMAP.md,.github/ISSUE_TEMPLATE/bug_report.md,.github/ISSUE_TEMPLATE/feature_request.md"
  "canonical:LICENSE,CONTRIBUTING.md,GOVERNANCE.md,ROADMAP.md,.github/ISSUE_TEMPLATE/bug_report.md,.github/ISSUE_TEMPLATE/feature_request.md"
  "etaledger:LICENSE,CONTRIBUTING.md,GOVERNANCE.md,ROADMAP.md,.github/ISSUE_TEMPLATE/bug_report.md,.github/ISSUE_TEMPLATE/feature_request.md"
  "fractallattice:LICENSE,CONTRIBUTING.md,GOVERNANCE.md,ROADMAP.md,.github/ISSUE_TEMPLATE/bug_report.md,.github/ISSUE_TEMPLATE/feature_request.md"
  "jesseray718:CONTRIBUTING.md,GOVERNANCE.md,ROADMAP.md,.github/ISSUE_TEMPLATE/bug_report.md,.github/ISSUE_TEMPLATE/feature_request.md"
  "OpenCell-Thermal-System:GOVERNANCE.md,ROADMAP.md,.github/ISSUE_TEMPLATE/bug_report.md,.github/ISSUE_TEMPLATE/feature_request.md"
  "openroot-canon:CONTRIBUTING.md,GOVERNANCE.md,ROADMAP.md,.github/ISSUE_TEMPLATE/bug_report.md,.github/ISSUE_TEMPLATE/feature_request.md"
  "openroot-foundation:CONTRIBUTING.md,GOVERNANCE.md,ROADMAP.md,.github/ISSUE_TEMPLATE/bug_report.md,.github/ISSUE_TEMPLATE/feature_request.md"
  "openroot-spoke-template:GOVERNANCE.md,ROADMAP.md"
  "openroot-thesis:CONTRIBUTING.md,GOVERNANCE.md,ROADMAP.md,.github/ISSUE_TEMPLATE/bug_report.md,.github/ISSUE_TEMPLATE/feature_request.md"
  "oscillation-mesh:LICENSE,CONTRIBUTING.md,GOVERNANCE.md,ROADMAP.md,.github/ISSUE_TEMPLATE/bug_report.md,.github/ISSUE_TEMPLATE/feature_request.md"
  "renaissance-protocol:GOVERNANCE.md,ROADMAP.md,.github/ISSUE_TEMPLATE/bug_report.md,.github/ISSUE_TEMPLATE/feature_request.md"
  "skills-introduction-to-github:CONTRIBUTING.md,GOVERNANCE.md,ROADMAP.md,.github/ISSUE_TEMPLATE/bug_report.md,.github/ISSUE_TEMPLATE/feature_request.md"
  "und-protocol:CONTRIBUTING.md,GOVERNANCE.md,ROADMAP.md,.github/ISSUE_TEMPLATE/bug_report.md,.github/ISSUE_TEMPLATE/feature_request.md"
  "une:CONTRIBUTING.md,GOVERNANCE.md,ROADMAP.md,.github/ISSUE_TEMPLATE/bug_report.md,.github/ISSUE_TEMPLATE/feature_request.md"
  "wisdom-scaffold:GOVERNANCE.md,ROADMAP.md"
)

# Template file mappings
declare -A TEMPLATE_MAP=(
  ["CONTRIBUTING.md"]="docs/cathedral-uplift/CONTRIBUTING.md"
  ["GOVERNANCE.md"]="docs/cathedral-uplift/GOVERNANCE.md"
  ["ROADMAP.md"]="docs/cathedral-uplift/ROADMAP.md"
  ["README.md"]="docs/cathedral-uplift/project-README.md"
  [".github/ISSUE_TEMPLATE/bug_report.md"]="docs/cathedral-uplift/ISSUE_TEMPLATE/bug_report.md"
  [".github/ISSUE_TEMPLATE/feature_request.md"]="docs/cathedral-uplift/ISSUE_TEMPLATE/feature_request.md"
)

customize_template() {
  local template_file="$1"
  local repo_name="$2"
  
  if [[ ! -f "$template_file" ]]; then
    log "ERROR: Template not found: $template_file"
    return 1
  fi
  
  # Replace placeholders
  sed \
    -e "s/\[PROJECT NAME\]/$repo_name/g" \
    -e "s/\[BRIEF DESCRIPTION\]/Part of the OpenRoot ecosystem./g" \
    -e "s/\[MAINTAINER NAME\/ORG\]/jesseray718/g" \
    "$template_file"
}

deploy_repo() {
  local repo_name="$1"
  local files_needed="$2"
  local repo_path="$WORK_DIR/$repo_name"
  
  log "[$(printf '%2d' $COUNT)/$TOTAL] Processing: $repo_name"
  
  # Clone repo
  if ! gh repo clone "jesseray718/$repo_name" "$repo_path" -- --depth 1 2>&1 >> "$LOG_OUTPUT"; then
    log "  ERROR: Could not clone jesseray718/$repo_name"
    return 1
  fi
  
  cd "$repo_path"
  
  # Process each file needed
  local files_added=0
  for target_file in $files_needed; do
    # Determine template source
    local template_src="${TEMPLATE_MAP[$target_file]:-}"
    
    if [[ "$target_file" == "LICENSE" ]]; then
      # Copy LICENSE as-is (AGPL-3.0)
      if [[ ! -f "$target_file" ]]; then
        cp "$LICENSE_FILE" "$target_file"
        ((files_added++))
        log "  + $target_file (AGPL-3.0)"
      else
        log "  ~ $target_file (already exists)"
      fi
    elif [[ -z "$template_src" ]]; then
      log "  ! No template mapping for: $target_file (skipping)"
    elif [[ ! -f "$template_src" ]]; then
      log "  ! Template not found: $template_src (skipping)"
    elif [[ -f "$target_file" ]]; then
      log "  ~ $target_file (already exists)"
    else
      # Create target directory if needed
      mkdir -p "$(dirname "$target_file")"
      
      # Customize and write template
      customize_template "$template_src" "$repo_name" > "$target_file"
      ((files_added++))
      log "  + $target_file"
    fi
  done
  
  # Commit and push if any files were added
  if [[ $files_added -gt 0 ]]; then
    git add .
    
    if [[ $DRY_RUN -eq 1 ]]; then
      log "  [DRY-RUN] Would commit and push $files_added file(s)"
      git diff --cached >> "$LOG_OUTPUT"
    else
      git commit -m "docs: add cathedral documentation (governance, roadmap, contributing, issue templates)" 2>&1 >> "$LOG_OUTPUT"
      if git push origin main 2>&1 >> "$LOG_OUTPUT"; then
        log "  ✓ Pushed $files_added file(s)"
      else
        log "  ! Push failed (repo may be ahead or branch protected)"
      fi
    fi
  else
    log "  ✓ No changes needed"
  fi
  
  cd - > /dev/null
  return 0
}

# Main loop
COUNT=0
TOTAL=${#REPOS[@]}
SUCCEEDED=0
FAILED=0

for repo_entry in "${REPOS[@]}"; do
  ((COUNT++))
  if [[ $COUNT -gt $LIMIT ]]; then
    log "Limit ($LIMIT) reached. Stopping."
    break
  fi
  
  IFS=':' read -r repo_name files_needed <<< "$repo_entry"
  files_needed="${files_needed//,/ }"
  
  if deploy_repo "$repo_name" "$files_needed"; then
    ((SUCCEEDED++))
  else
    ((FAILED++))
  fi
done

# Summary
log ""
log "=== Summary ==="
log "Total repos: $COUNT"
log "Succeeded: $SUCCEEDED"
log "Failed: $FAILED"
log "Dry-run: $DRY_RUN"
if [[ $DRY_RUN -eq 0 ]]; then
  log "Next: Run cathedral-status.sh to re-audit and verify repos are HEALTHY"
fi

if [[ -n "$OUTPUT_FILE" ]]; then
  echo "Log written to: $OUTPUT_FILE"
  tail -20 "$OUTPUT_FILE"
fi

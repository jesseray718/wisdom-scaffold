#!/usr/bin/env bash
#
# deploy-cathedral-docs.sh
#
# Batch-deploys cathedral documentation (GOVERNANCE, ROADMAP, CONTRIBUTING,
# issue templates, and optionally README/LICENSE) to every repo listed in
# docs/cathedral-uplift/deployment-manifest.yaml.
#
# This is a documentation-only operation. It never touches source code and
# never modifies forked or archived repos (the manifest already excludes
# them, per uplift-policy.yaml).
#
# Requirements:
#   - GitHub CLI (`gh`), authenticated: `gh auth login`
#   - `yq` (mikefarah/yq v4+) for YAML parsing
#   - `git`
#
# Usage:
#   ./deploy-cathedral-docs.sh [options]
#
# Options:
#   --dry-run           Show what would be done; do not commit or push.
#   --limit N           Only process the first N repos in the manifest.
#   --repo NAME          Only process a single repo (by name, no owner prefix).
#   --owner OWNER        Repo owner/org to deploy to (default: jesseray718).
#   --manifest PATH      Path to deployment-manifest.yaml
#                        (default: <script dir>/docs/cathedral-uplift/deployment-manifest.yaml)
#   --templates-dir PATH Path to template files
#                        (default: <script dir>/docs/cathedral-uplift)
#   --workdir PATH       Directory to clone target repos into
#                        (default: /tmp/cathedral-deploy-clones)
#   -h, --help           Show this help and exit.
#
# Idempotency:
#   - Existing target files are never overwritten; a file already present in
#     the target repo is left untouched and reported as "already present".
#   - If nothing changed for a repo (no new files were added), no commit is
#     made and nothing is pushed.
#
set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd -P)"
MANIFEST="${SCRIPT_DIR}/docs/cathedral-uplift/deployment-manifest.yaml"
TEMPLATES_DIR="${SCRIPT_DIR}/docs/cathedral-uplift"
LICENSE_SOURCE="${SCRIPT_DIR}/LICENSE"
WORKDIR="/tmp/cathedral-deploy-clones"
OWNER="jesseray718"
DRY_RUN=0
LIMIT=0
ONLY_REPO=""
COMMIT_MESSAGE="docs: add cathedral documentation (governance, roadmap, contributing, issue templates)"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log()  { printf '%s\n' "$*"; }
info() { printf '[INFO] %s\n' "$*"; }
warn() { printf '[WARN] %s\n' "$*" >&2; }
err()  { printf '[ERROR] %s\n' "$*" >&2; }

usage() {
    sed -n '2,39p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

require_cmd() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        err "Required command '$cmd' not found in PATH."
        exit 1
    fi
}

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        --limit)
            LIMIT="${2:?--limit requires a number}"
            shift 2
            ;;
        --repo)
            ONLY_REPO="${2:?--repo requires a repo name}"
            shift 2
            ;;
        --owner)
            OWNER="${2:?--owner requires a value}"
            shift 2
            ;;
        --manifest)
            MANIFEST="${2:?--manifest requires a path}"
            shift 2
            ;;
        --templates-dir)
            TEMPLATES_DIR="${2:?--templates-dir requires a path}"
            shift 2
            ;;
        --workdir)
            WORKDIR="${2:?--workdir requires a path}"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            err "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Preflight checks
# ---------------------------------------------------------------------------
require_cmd gh
require_cmd yq
require_cmd git

if [[ ! -f "$MANIFEST" ]]; then
    err "Manifest not found: $MANIFEST"
    exit 1
fi

if [[ ! -d "$TEMPLATES_DIR" ]]; then
    err "Templates directory not found: $TEMPLATES_DIR"
    exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
    err "GitHub CLI is not authenticated. Run 'gh auth login' first."
    exit 1
fi

mkdir -p "$WORKDIR"

if [[ "$DRY_RUN" -eq 1 ]]; then
    info "Running in --dry-run mode: no commits or pushes will be made."
fi

REPO_COUNT="$(yq '.repos | length' "$MANIFEST")"
info "Manifest lists ${REPO_COUNT} target repo(s): $MANIFEST"

# ---------------------------------------------------------------------------
# Deployment counters
# ---------------------------------------------------------------------------
DEPLOYED=0
SKIPPED=0
FAILED=0
PROCESSED=0

# ---------------------------------------------------------------------------
# Customize a template file's placeholder tokens and write it to destination.
# ---------------------------------------------------------------------------
customize_and_write() {
    local src="$1" dest="$2" project_name="$3" description="$4" license_name="$5"

    mkdir -p "$(dirname -- "$dest")"
    sed \
        -e "s/\[PROJECT NAME\]/${project_name//\//\\/}/g" \
        -e "s/\[BRIEF DESCRIPTION\]/${description//\//\\/}/g" \
        -e "s/\[LICENSE NAME\]/${license_name//\//\\/}/g" \
        "$src" > "$dest"
}

# ---------------------------------------------------------------------------
# Deploy documentation to a single repo.
# ---------------------------------------------------------------------------
deploy_repo() {
    local name="$1"
    local description="$2"
    local needs_license="$3"
    local files_json="$4"

    local full_name="${OWNER}/${name}"
    local repo_dir="${WORKDIR}/${name}"
    local changed=0

    info "----------------------------------------------------------------"
    info "Processing ${full_name}"

    # Clone (or fetch + reset if already cloned) -----------------------------
    if [[ -d "${repo_dir}/.git" ]]; then
        info "Repo already cloned locally; fetching latest..."
        if ! git -C "$repo_dir" fetch origin >/dev/null 2>&1; then
            err "Failed to fetch ${full_name}; skipping."
            FAILED=$((FAILED + 1))
            return
        fi
    else
        info "Cloning ${full_name}..."
        if ! gh repo clone "$full_name" "$repo_dir" -- --quiet >/dev/null 2>&1; then
            err "Failed to clone ${full_name}; skipping."
            FAILED=$((FAILED + 1))
            return
        fi
    fi

    local default_branch
    default_branch="$(gh repo view "$full_name" --json defaultBranchRef -q '.defaultBranchRef.name' 2>/dev/null || echo main)"
    [[ -z "$default_branch" || "$default_branch" == "null" ]] && default_branch="main"

    if ! git -C "$repo_dir" checkout -B "$default_branch" "origin/${default_branch}" --quiet 2>/dev/null; then
        err "Failed to check out ${default_branch} for ${full_name}; skipping."
        FAILED=$((FAILED + 1))
        return
    fi
    git -C "$repo_dir" reset --hard "origin/${default_branch}" --quiet

    # Copy + customize template files, but never overwrite existing files ---
    local file_count
    file_count="$(jq 'length' <<<"$files_json")"
    local i
    for (( i=0; i<file_count; i++ )); do
        local template target src dest
        template="$(jq -r ".[$i].template" <<<"$files_json")"
        target="$(jq -r ".[$i].target" <<<"$files_json")"
        src="${TEMPLATES_DIR}/${template}"
        dest="${repo_dir}/${target}"

        if [[ ! -f "$src" ]]; then
            warn "Template not found, skipping: $src"
            continue
        fi

        if [[ -f "$dest" ]]; then
            info "  already present, skipping: ${target}"
            continue
        fi

        if [[ "$DRY_RUN" -eq 1 ]]; then
            info "  [dry-run] would add: ${target} (from ${template})"
            changed=1
            continue
        fi

        customize_and_write "$src" "$dest" "$name" "$description" "AGPL-3.0"
        info "  added: ${target}"
        changed=1
    done

    # LICENSE (only when the manifest flags this repo as needing one) -------
    if [[ "$needs_license" == "true" ]]; then
        local license_dest="${repo_dir}/LICENSE"
        if [[ -f "$license_dest" ]]; then
            info "  LICENSE already present, skipping"
        elif [[ ! -f "$LICENSE_SOURCE" ]]; then
            warn "  LICENSE source not found at ${LICENSE_SOURCE}; skipping LICENSE for ${full_name}"
        elif [[ "$DRY_RUN" -eq 1 ]]; then
            info "  [dry-run] would add: LICENSE (AGPL-3.0)"
            changed=1
        else
            cp "$LICENSE_SOURCE" "$license_dest"
            info "  added: LICENSE (AGPL-3.0)"
            changed=1
        fi
    fi

    if [[ "$changed" -eq 0 ]]; then
        info "No changes needed for ${full_name} (already healthy). Skipping commit."
        SKIPPED=$((SKIPPED + 1))
        return
    fi

    if [[ "$DRY_RUN" -eq 1 ]]; then
        info "[dry-run] Would commit and push to ${full_name} (${default_branch})."
        DEPLOYED=$((DEPLOYED + 1))
        return
    fi

    git -C "$repo_dir" add -A

    if git -C "$repo_dir" diff --cached --quiet; then
        info "No staged changes for ${full_name}; nothing to commit."
        SKIPPED=$((SKIPPED + 1))
        return
    fi

    if ! git -C "$repo_dir" commit -m "$COMMIT_MESSAGE" --quiet; then
        err "Commit failed for ${full_name}; skipping push."
        FAILED=$((FAILED + 1))
        return
    fi

    if ! git -C "$repo_dir" push origin "HEAD:${default_branch}" --quiet; then
        err "Push failed for ${full_name}."
        FAILED=$((FAILED + 1))
        return
    fi

    info "Deployed and pushed to ${full_name} (${default_branch})."
    DEPLOYED=$((DEPLOYED + 1))
}

# ---------------------------------------------------------------------------
# Main loop over manifest repos
# ---------------------------------------------------------------------------
for (( idx=0; idx<REPO_COUNT; idx++ )); do
    name="$(yq -r ".repos[$idx].name" "$MANIFEST")"

    if [[ -n "$ONLY_REPO" && "$name" != "$ONLY_REPO" ]]; then
        continue
    fi

    if [[ "$LIMIT" -gt 0 && "$PROCESSED" -ge "$LIMIT" ]]; then
        info "Reached --limit ${LIMIT}; stopping."
        break
    fi

    description="$(yq -r ".repos[$idx].description" "$MANIFEST")"
    needs_license="$(yq -r ".repos[$idx].license" "$MANIFEST")"
    files_json="$(yq -o=json ".repos[$idx].files" "$MANIFEST")"

    PROCESSED=$((PROCESSED + 1))
    deploy_repo "$name" "$description" "$needs_license" "$files_json"

    if [[ -n "$ONLY_REPO" ]]; then
        break
    fi
done

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
log ""
log "================================================================"
log "CATHEDRAL DOCS DEPLOYMENT SUMMARY"
log "  Processed: ${PROCESSED}"
log "  Deployed:  ${DEPLOYED}"
log "  Skipped (already healthy): ${SKIPPED}"
log "  Failed:    ${FAILED}"
[[ "$DRY_RUN" -eq 1 ]] && log "  (dry-run: no commits or pushes were made)"
log "================================================================"

if [[ "$FAILED" -gt 0 ]]; then
    exit 1
fi

#!/usr/bin/env bash
# cathedral-status.sh — report-only cross-reference of jesseray718's own repositories.
#
# Purpose:
#   Lists the owner's ORIGINAL (non-forked) GitHub repositories, cross-references
#   each one's documentation/structure against a small set of conventions, and
#   writes a plain-language TXT report plus a spreadsheet-friendly CSV report.
#   Optionally hands the "blanks" (missing items) per repo to a local command
#   (e.g. a wrapper around a locally-hosted coder model) to draft suggested
#   content — purely as local report material. Nothing is ever written back
#   to GitHub: no clones, no commits, no pushes, no branches, no PRs, no
#   settings changes.
#
# Safety:
#   - Read-only GitHub API calls only (via `gh api`).
#   - Forks are always excluded from classification (never treated as "yours").
#   - Archived repos are included in the report but marked REPORT_ONLY.
#   - No writes to any assessed repository, ever.
#   - Reports are written outside version control by default.
#
# Usage:
#   /home/jesse/wisdom-scaffold/cathedral-status.sh [options]
#
# Options:
#   --owner LOGIN     GitHub login to audit (default: jesseray718)
#   --output DIR      Absolute directory to write reports into
#                      (default: /tmp/cathedral-reports)
#   --limit N         Only process the first N eligible repos (0 = all, default: 0)
#   --self-test       Run the full report pipeline against embedded fixture
#                      data instead of calling the GitHub API (no network,
#                      no auth required). Useful for validating the script.
#   -h, --help        Show this help and exit.
#
# Examples:
#   /home/jesse/wisdom-scaffold/cathedral-status.sh --self-test
#   /home/jesse/wisdom-scaffold/cathedral-status.sh --limit 3
#   /home/jesse/wisdom-scaffold/cathedral-status.sh --owner jesseray718 --output /home/jesse/cathedral-reports
#
# Optional local model cross-reference:
#   Set LLM_CMD to an absolute path of an executable that reads a prompt on
#   stdin and writes suggested draft content to stdout. When set, this script
#   pipes each repo's list of missing items to it and saves the result next
#   to the reports as a local suggestion file. This never modifies GitHub.
#   Example:
#     export LLM_CMD=/home/jesse/models/run_7b_coder.sh
#     /home/jesse/wisdom-scaffold/cathedral-status.sh
#
# Exit codes:
#   0  success
#   1  usage error
#   2  missing required tool (gh, jq, curl)
#   3  GitHub API call failed (auth/network) and --self-test was not used

set -u
set -o pipefail

OWNER="jesseray718"
OUTPUT_DIR="/tmp/cathedral-reports"
LIMIT=0
SELF_TEST=0

usage() {
    sed -n '2,52p' "$0" | sed 's/^# \{0,1\}//'
}

while [ $# -gt 0 ]; do
    case "$1" in
        --owner)
            OWNER="${2:-}"
            shift 2
            ;;
        --output)
            OUTPUT_DIR="${2:-}"
            shift 2
            ;;
        --limit)
            LIMIT="${2:-0}"
            shift 2
            ;;
        --self-test)
            SELF_TEST=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
done

case "$OUTPUT_DIR" in
    /*) ;;
    *)
        echo "ERROR: --output must be an absolute path (got: $OUTPUT_DIR)" >&2
        exit 1
        ;;
esac

if [ "$SELF_TEST" -eq 0 ]; then
    for tool in gh jq; do
        if ! command -v "$tool" >/dev/null 2>&1; then
            echo "ERROR: required tool '$tool' not found in PATH." >&2
            echo "Install it, or run with --self-test to validate the report pipeline offline." >&2
            exit 2
        fi
    done
fi

mkdir -p "$OUTPUT_DIR" || {
    echo "ERROR: could not create output directory: $OUTPUT_DIR" >&2
    exit 1
}

STAMP="$(date -u +%Y%m%d-%H%M%S)"
TXT_REPORT="$OUTPUT_DIR/cathedral-status-$STAMP.txt"
CSV_REPORT="$OUTPUT_DIR/cathedral-status-$STAMP.csv"
SUGGEST_DIR="$OUTPUT_DIR/suggestions-$STAMP"

DOC_CANDIDATES_README="README.md README"
DOC_CANDIDATES_CONTRIBUTING="CONTRIBUTING.md CONTRIBUTING"
DOC_CANDIDATES_GOVERNANCE="CODE_OF_CONDUCT.md CONTRIBUTORS.md GOVERNANCE.md"
DOC_CANDIDATES_ROADMAP="ROADMAP.md docs/ROADMAP.md NEXT.md STATUS.md docs/roadmap"
DOC_CANDIDATES_ISSUES=".github/ISSUE_TEMPLATE"
DOC_CANDIDATES_CODERABBIT=".coderabbit.yaml"
DEP_MANIFESTS="package.json requirements.txt pyproject.toml Pipfile Gemfile go.mod Cargo.toml pom.xml"
DOC_CANDIDATES_DEPENDABOT=".github/dependabot.yml"

# path_present PATTERNS_STRING TREE_FILE
# Returns 0 if any candidate path/prefix appears in the repo tree listing.
path_present() {
    _candidates="$1"
    _tree_file="$2"
    for _c in $_candidates; do
        if grep -qiE "^${_c//./\\.}(/|$)" "$_tree_file"; then
            return 0
        fi
    done
    return 1
}

# classify_repo NAME FORK ARCHIVED LICENSE TREE_FILE -> sets CLASS, REASON, MISSING (globals)
classify_repo() {
    _name="$1"; _fork="$2"; _archived="$3"; _license="$4"; _tree_file="$5"
    MISSING=""
    NOTES=""

    if [ "$_fork" = "true" ]; then
        CLASS="REPORT_ONLY"
        REASON="Fork of another repository; not treated as original work."
        return
    fi
    if [ "$_archived" = "true" ]; then
        CLASS="REPORT_ONLY"
        REASON="Repository is archived; report-only, no changes suggested."
        return
    fi

    has_readme=1;  path_present "$DOC_CANDIDATES_README" "$_tree_file" || has_readme=0
    has_contrib=1; path_present "$DOC_CANDIDATES_CONTRIBUTING" "$_tree_file" || has_contrib=0
    has_gov=1;     path_present "$DOC_CANDIDATES_GOVERNANCE" "$_tree_file" || has_gov=0
    has_roadmap=1; path_present "$DOC_CANDIDATES_ROADMAP" "$_tree_file" || has_roadmap=0
    has_issues=1;  path_present "$DOC_CANDIDATES_ISSUES" "$_tree_file" || has_issues=0
    has_rabbit=1;  path_present "$DOC_CANDIDATES_CODERABBIT" "$_tree_file" || has_rabbit=0
    has_dep_manifest=1; path_present "$DEP_MANIFESTS" "$_tree_file" || has_dep_manifest=0
    has_dependabot=1;   path_present "$DOC_CANDIDATES_DEPENDABOT" "$_tree_file" || has_dependabot=0

    [ "$has_readme" -eq 0 ]  && MISSING="$MISSING README"
    [ "$has_contrib" -eq 0 ] && MISSING="$MISSING CONTRIBUTING"
    [ "$has_gov" -eq 0 ]     && MISSING="$MISSING GOVERNANCE/CODE_OF_CONDUCT"
    [ "$has_roadmap" -eq 0 ] && MISSING="$MISSING ROADMAP/STATUS"
    [ "$has_issues" -eq 0 ]  && MISSING="$MISSING ISSUE_TEMPLATE-or-discussions"

    if [ "$_license" = "NONE" ] || [ -z "$_license" ]; then
        NOTES="$NOTES LICENSE:DECISION_REQUIRED(no-license-detected-human-choice-needed)"
    fi
    if [ "$has_rabbit" -eq 0 ]; then
        NOTES="$NOTES CodeRabbit:OPTIONAL_AUTOMATION(not-a-defect)"
    fi
    if [ "$has_dep_manifest" -eq 0 ]; then
        NOTES="$NOTES Dependabot:NOT_APPLICABLE(no-dependency-manifest-found)"
    elif [ "$has_dependabot" -eq 0 ]; then
        NOTES="$NOTES Dependabot:OPTIONAL_AUTOMATION(manifest-present-not-configured)"
    fi

    if [ -n "$(echo "$MISSING" | tr -d '[:space:]')" ]; then
        CLASS="REVIEW_RECOMMENDED"
        REASON="Missing:${MISSING}"
    elif [ "$_license" = "NONE" ] || [ -z "$_license" ]; then
        CLASS="DECISION_REQUIRED"
        REASON="Core docs present; license status needs a human decision."
    else
        CLASS="HEALTHY"
        REASON="Core docs and license present."
    fi
}

maybe_llm_suggest() {
    _name="$1"
    _missing="$2"
    [ -n "${LLM_CMD:-}" ] || return 0
    [ -x "$LLM_CMD" ] || {
        echo "  (LLM_CMD set but not executable: $LLM_CMD — skipping cross-reference)"
        return 0
    }
    mkdir -p "$SUGGEST_DIR"
    _prompt="Repository ${OWNER}/${_name} is missing: ${_missing}. Draft short, plain-language suggested content or structure notes to fill these blanks. Do not invent license text."
    if printf '%s\n' "$_prompt" | "$LLM_CMD" > "$SUGGEST_DIR/${_name}.txt" 2>"$SUGGEST_DIR/${_name}.err"; then
        echo "  local model suggestion -> $SUGGEST_DIR/${_name}.txt"
    else
        echo "  (LLM_CMD failed for ${_name}; see $SUGGEST_DIR/${_name}.err)"
    fi
}

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

fetch_repo_list() {
    if [ "$SELF_TEST" -eq 1 ]; then
        cat > "$WORKDIR/repos.tsv" <<'EOF'
fractallattice	false	false	master	NONE
openroot	false	false	main	GPL-3.0
AeroCement_Ecosystem	false	false	main	NONE
aerocement-	false	true	main	NONE
skills-introduction-to-github	true	false	main	NONE
EOF
        return 0
    fi
    if ! gh api --paginate "users/${OWNER}/repos?per_page=100&type=owner" \
        --jq '.[] | [.name, .fork, .archived, .default_branch, (.license.spdx_id // "NONE")] | @tsv' \
        > "$WORKDIR/repos.tsv" 2>"$WORKDIR/repos.err"; then
        echo "ERROR: GitHub API call failed (auth/network). Details:" >&2
        cat "$WORKDIR/repos.err" >&2
        echo "Run 'gh auth login' first, or use --self-test to validate the report pipeline offline." >&2
        exit 3
    fi
}

fetch_tree() {
    _name="$1"; _branch="$2"; _out="$3"
    if [ "$SELF_TEST" -eq 1 ]; then
        case "$_name" in
            fractallattice)
                printf 'README.md\nAGAPE_OFFLINE_CORE.json\n' > "$_out" ;;
            openroot)
                printf 'README.md\nCONTRIBUTING.md\nCODE_OF_CONDUCT.md\nLICENSE\n.github/ISSUE_TEMPLATE/bug.md\ndocs/roadmap/PLAN.md\n' > "$_out" ;;
            AeroCement_Ecosystem)
                printf 'README.md\ndrill_scheduler.sh\n' > "$_out" ;;
            *)
                printf 'README.md\n' > "$_out" ;;
        esac
        return 0
    fi
    gh api "repos/${OWNER}/${_name}/git/trees/${_branch}?recursive=1" \
        --jq '.tree[].path' > "$_out" 2>"$WORKDIR/tree.err" || : > "$_out"
}

{
    echo "CATHEDRAL STATUS REPORT (report-only)"
    echo "Owner: $OWNER"
    echo "Generated (UTC): $STAMP"
    echo "Mode: $([ "$SELF_TEST" -eq 1 ] && echo SELF_TEST-fixture-data || echo LIVE-github-api)"
    echo "Rule: forks are always excluded from 'yours'; archived repos are report-only."
    echo ""
} > "$TXT_REPORT"

echo "repo,classification,reason,fork,archived,license,missing,notes" > "$CSV_REPORT"

fetch_repo_list

TOTAL=$(wc -l < "$WORKDIR/repos.tsv" | tr -d ' ')
if [ "$LIMIT" -gt 0 ] && [ "$LIMIT" -lt "$TOTAL" ]; then
    head -n "$LIMIT" "$WORKDIR/repos.tsv" > "$WORKDIR/repos.limited.tsv"
    mv "$WORKDIR/repos.limited.tsv" "$WORKDIR/repos.tsv"
    TOTAL="$LIMIT"
fi

i=0
while IFS=$'\t' read -r NAME FORK ARCHIVED BRANCH LICENSE; do
    [ -n "$NAME" ] || continue
    i=$((i + 1))
    echo "[$i/$TOTAL] Checking ${OWNER}/${NAME}"

    TREE_FILE="$WORKDIR/tree-${NAME}.txt"
    if [ "$FORK" != "true" ]; then
        fetch_tree "$NAME" "${BRANCH:-main}" "$TREE_FILE"
    else
        : > "$TREE_FILE"
    fi

    classify_repo "$NAME" "$FORK" "$ARCHIVED" "$LICENSE" "$TREE_FILE"

    {
        echo "- ${OWNER}/${NAME}"
        echo "    classification: $CLASS"
        echo "    reason: $REASON"
        [ -n "${NOTES:-}" ] && echo "    notes:$NOTES"
        echo ""
    } >> "$TXT_REPORT"

    CSV_MISSING=$(echo "${MISSING:-}" | sed 's/^ //; s/ /;/g')
    CSV_NOTES=$(echo "${NOTES:-}" | sed 's/^ //; s/,/;/g')
    echo "\"$NAME\",\"$CLASS\",\"$REASON\",\"$FORK\",\"$ARCHIVED\",\"$LICENSE\",\"$CSV_MISSING\",\"$CSV_NOTES\"" >> "$CSV_REPORT"

    if [ "$CLASS" = "REVIEW_RECOMMENDED" ] && [ -n "${MISSING:-}" ]; then
        maybe_llm_suggest "$NAME" "$MISSING"
    fi
done < "$WORKDIR/repos.tsv"

{
    echo "SUMMARY"
    echo "Repos assessed: $TOTAL"
    echo "Reports written to: $OUTPUT_DIR"
    if [ -z "${LLM_CMD:-}" ]; then
        echo "Local model cross-reference: skipped (set LLM_CMD to an executable to enable)."
    fi
} >> "$TXT_REPORT"

echo ""
echo "TXT report: $TXT_REPORT"
echo "CSV report: $CSV_REPORT"
if [ -d "$SUGGEST_DIR" ]; then
    echo "Suggestions: $SUGGEST_DIR"
fi
exit 0

#!/usr/bin/env bash
# Prepare everything a Phase 2 reviewer needs, from a fresh clone, in one command.
#
#     bash scripts/prepare_phase2_bundles.sh [BUNDLE_DIR]
#
# What it does, in order:
#   1. builds this repository's Python 3.11 environment (.venv) if it is missing;
#   2. verifies the working tree is clean and the Phase 2 freeze manifest still
#      matches every frozen artifact (protocol, rubric, schema, prompts, packets);
#   3. exports one physically isolated bundle per reviewer OUTSIDE the clone
#      (default: ../phase2_review_bundles/phase2_claude and .../phase2_codex);
#   4. gives the bundles their own minimal Python 3.11 environment
#      (BUNDLE_DIR/.venv: pyyaml only, no numpy, no scipy, no repository code);
#   5. runs the reviewer preflight inside each bundle and prints the launch
#      commands.
#
# It never writes into the repository beyond creating .venv, and it refuses to
# overwrite an existing bundle: a bundle that a review may have started in is
# never regenerated silently.
#
# Requires `uv` (https://docs.astral.sh/uv/) or a `python3.11` on PATH.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUNDLE_DIR="${1:-$(cd "$REPO_ROOT/.." && pwd)/phase2_review_bundles}"
export PATH="$HOME/.local/bin:$PATH"

say()  { printf '\n== %s\n' "$*"; }
stop() { printf 'STOP: %s\n' "$*" >&2; exit 1; }

make_venv() {  # make_venv <dir> [pip args...]
    local dir="$1"; shift
    if [ -x "$dir/bin/python" ]; then
        return 0
    fi
    if command -v uv >/dev/null 2>&1; then
        uv venv --python 3.11 "$dir"
        uv pip install --python "$dir/bin/python" "$@"
    elif command -v python3.11 >/dev/null 2>&1; then
        python3.11 -m venv "$dir"
        "$dir/bin/python" -m pip install --quiet --upgrade pip
        "$dir/bin/python" -m pip install --quiet "$@"
    else
        stop "need 'uv' or a 'python3.11' on PATH to build $dir (system python3 is too old)"
    fi
}

cd "$REPO_ROOT"

say "repository environment"
make_venv "$REPO_ROOT/.venv" -e ".[dev]"
PY="$REPO_ROOT/.venv/bin/python"
"$PY" --version

say "working tree must be clean and at the frozen protocol"
if [ -n "$(git status --porcelain)" ]; then
    stop "the working tree is dirty; commit or stash first so both bundles come from one commit"
fi
"$PY" scripts/freeze_phase2.py --check
HEAD_SHA="$(git rev-parse HEAD)"
TAG_SHA="$(git rev-list -n 1 phase2-odc-pre-review-frozen 2>/dev/null || true)"
if [ -z "$TAG_SHA" ]; then
    printf 'note: tag phase2-odc-pre-review-frozen is not present locally (fetch tags to see it)\n'
elif [ "$TAG_SHA" != "$HEAD_SHA" ]; then
    printf 'note: HEAD %s is not the tagged freeze commit %s; the frozen artifacts still hash-match the freeze manifest, which is what the preflight checks\n' "${HEAD_SHA:0:7}" "${TAG_SHA:0:7}"
fi

say "bundle directory: $BUNDLE_DIR"
case "$BUNDLE_DIR" in
    "$REPO_ROOT"|"$REPO_ROOT"/*) stop "bundles must live outside the repository";;
esac
mkdir -p "$BUNDLE_DIR"
make_venv "$BUNDLE_DIR/.venv" pyyaml

for reviewer in claude codex; do
    out="$BUNDLE_DIR/phase2_$reviewer"
    say "bundle for $reviewer"
    if [ -e "$out" ]; then
        printf 'already exists, not touched: %s\n' "$out"
    else
        "$PY" scripts/make_phase2_review_bundle.py --reviewer "$reviewer" --out "$out"
    fi
    ( cd "$out" && "$BUNDLE_DIR/.venv/bin/python" scripts/check_phase2_ready.py --reviewer "$reviewer" | tail -n 8 )
done

say "ready. Launch each reviewer in a FRESH session started inside its bundle:"
cat <<EOF

  Claude:
    cd $BUNDLE_DIR/phase2_claude && source ../.venv/bin/activate && claude

  GPT / Codex:
    cd $BUNDLE_DIR/phase2_codex && source ../.venv/bin/activate && codex

then paste the matching block from experiments/phase2_odc_control/README.md
("Launching a reviewer"). Tell the reviewer nothing else.
EOF

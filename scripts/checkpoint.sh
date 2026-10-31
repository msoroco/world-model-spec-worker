#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if [[ $# -ne 1 || -z "$1" ]]; then
  echo 'usage: scripts/checkpoint.sh "short progress summary"' >&2
  exit 2
fi
branch="$(git branch --show-current)"
if [[ "$branch" != 'worker/full-train-delivery' ]]; then
  echo "refusing to publish from unexpected branch: $branch" >&2
  exit 2
fi

# Assignment owners never push. The lead invokes this after reviewing a
# coherent checkpoint. Frozen inputs and runtime are never staged here.
git add -A -- work/
if ! git diff --cached --quiet -- work/; then
  git diff --cached --check -- work/
  git commit -m "Checkpoint full-train delivery: $1" -- work/
fi

# Retry any previously unpushed checkpoint even when there are no new files.
git push origin "$branch"

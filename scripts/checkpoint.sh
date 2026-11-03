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

# The independent timer publishes work/ snapshots. Frozen inputs and runtime
# are never staged. The directory may be empty before the first agent result.
if [[ -d work ]]; then
  git add -A -- work/
  if ! git diff --cached --quiet -- work/; then
    git diff --cached --check -- work/
    git commit -m "Checkpoint full-train delivery: $1" -- work/
  fi
fi

# Retry any previously unpushed checkpoint even when there are no new files.
GIT_TERMINAL_PROMPT=0 git push origin "$branch"

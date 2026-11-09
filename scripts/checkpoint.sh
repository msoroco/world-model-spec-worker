#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
if [[ $# -ne 1 || -z "$1" ]]; then echo 'usage: scripts/checkpoint.sh "short progress summary"' >&2; exit 2; fi
branch="$(git branch --show-current)"
expected="$(python3.11 -c 'import json; print(json.load(open("batch.json"))["return_branch"])')"
if [[ "$branch" != "$expected" ]]; then echo "refusing to publish from unexpected branch: $branch" >&2; exit 2; fi
if [[ -d work ]]; then
  git add -A -- work/
  if ! git diff --cached --quiet -- work/; then
    git diff --cached --check -- work/
    git commit -m "Checkpoint ${branch}: $1" -- work/
  fi
fi
GIT_TERMINAL_PROMPT=0 git push origin "$branch"

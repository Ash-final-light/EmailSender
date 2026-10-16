#!/usr/bin/env bash
set -euo pipefail
git config user.name 'github-actions[bot]'
git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
git add data/
if ! git diff --cached --quiet; then
  git commit -m 'chore: persist newsletter state'
  git push
fi

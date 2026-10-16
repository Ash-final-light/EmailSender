#!/usr/bin/env bash
set -euo pipefail
git config user.name 'github-actions[bot]'
git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
git add job_radar/data/
if ! git diff --cached --quiet; then
  git commit -m 'chore: persist internship radar state'
  git push
fi

#!/usr/bin/env bash
set -euo pipefail
git config user.name 'github-actions[bot]'
git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
git add job_radar/data/
if ! git diff --cached --quiet; then
  git commit -m 'chore: persist internship radar state'
fi
# A maintainer may push code while the collector runs. Rebase the saved state
# onto that fast-moving branch before pushing; a real data conflict fails closed.
branch="$(git branch --show-current)"
if [[ -z "$branch" ]]; then echo 'Expected the default branch checkout' >&2; exit 1; fi
git fetch origin "$branch"
git rebase "origin/$branch"
git push origin "HEAD:$branch"

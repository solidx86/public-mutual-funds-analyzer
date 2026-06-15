#!/usr/bin/env bash
# Commit + push new/updated private outputs (client proposals, FundMaster workbooks)
# to the private data repo. Path-agnostic: resolves the private repo through the
# gitignored symlink mount, so no absolute path is hardcoded. No-ops cleanly when
# the private mount is absent (e.g. a fresh public-only clone, including CI).
set -euo pipefail

mount="output/fund_proposals"   # stable public-repo-relative symlink into the private repo

if ! priv_root="$(git -C "$mount" rev-parse --show-toplevel 2>/dev/null)"; then
  echo "private mount not present — skipping sync"
  exit 0
fi

git -C "$priv_root" add -A
if git -C "$priv_root" diff --cached --quiet; then
  echo "nothing to sync"
  exit 0
fi
git -C "$priv_root" commit -m "data: sync proposals/fundmasters ($(date +%F))"
git -C "$priv_root" push
echo "synced private outputs"

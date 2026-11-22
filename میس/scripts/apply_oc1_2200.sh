#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$SCRIPT_DIR/apply_oc2_2200.sh" "${1:?Usage: apply_oc1_2200.sh <kernel-source-directory>}"

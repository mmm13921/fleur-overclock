# EEVDF — Linux 6.18 backport

This folder archives the EEVDF core patch, its audit script, and the post-integration cleanup.

## Contents
- `0001-eevdf-core-618.py`: EEVDF core backport layer.
- `audit_eevdf_618.py`: source-level feature/symbol audit.
- `apply_eevdf_legacy_cleanup.py`: removes obsolete legacy CFS granularity sysctl interfaces while preserving `sched_base_slice` and EEVDF controls.

The upstream/backport scope and known incomplete features are documented in the existing `eevdf/README.md`. A successful compile or static audit does not establish device boot or runtime correctness.

These are archive snapshots; keep them synchronized with the active `eevdf/` and `scripts/` copies.

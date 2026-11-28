# HMP — Fleur MT6781 / Fleux V12

This folder archives the HMP integration patch and the Fleur 4.14 reference implementation.

## Contents
- `apply_hmp_mt6781.py`: integrates HMP into Fleux V12, adapts the cluster topology to MT6781 (CPU0–5 LITTLE, CPU6–7 BIG), and connects the HMP/EAS/Hybrid scheduler-mode integration.
- `reference/`: vendor HMP source and scheduler header reference files.

The HMP integration is an adapted port; do not describe it as a bit-for-bit copy of the complete original platform scheduler. Build/boot/runtime validation must be tracked separately.

The active build entry point remains `scripts/apply_hmp_mt6781.py`; keep this archive synchronized with it and `vendor/hmp-fleur-4.14/`.

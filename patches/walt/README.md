# WALT — MT6781 / Fleux V12

This folder is the versioned archive for the Fleur-native WALT implementation and its MT6781 integration.

## Contents
- `apply_walt_mt6781.py`: full WALT scheduler accounting integration, task/rq demand tracking, WALT CPU/task utilization controls, and idle-rq frequency-demand handling.
- `apply_walt_controls_mt6781.py`: WALT sysctl/control registration and bounds.
- `apply_waltgov_mt6781.py`: WALT CPUFreq governor and tunables, including the `hispeed_freq` whitelist.
- `reference/`: pinned Fleur 4.14 WALT source/header references used by the port.
- `walt_runtime_check.sh`: read-only on-device diagnostic.
- `walt-proc-sysctl.md`: runtime interface notes.

## hispeed_freq whitelist
The accepted values (kHz) are exactly:
`2000000 1933000 1866000 1800000 1733000 1666000 1618000 1500000 1375000 1275000 1175000 1075000 975000 875000 774000 500000`.
Any other value is rejected by the sysfs store handler. The table attribute prints this list as one space-separated line.

## Runtime status
The idle-runqueue guards in the WALT CPU-util and WALT governor paths are intended to prevent stale WALT demand from holding the CPU at a previous high OPP (the reported 2055 MHz lock). CI success is not proof of device runtime behavior; validate idle and load transitions on the phone.

## Source of truth
These are archived snapshots. The active build workflow still invokes the corresponding files under `scripts/` and consumes the reference sources under `vendor/walt-fleur-4.14/`. Keep archive copies synchronized whenever the active implementation changes.

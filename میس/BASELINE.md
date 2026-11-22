# MEYS VX V15 — Preserved baseline

This directory is an exact file snapshot of the boot-tested MEYS VX V15 build configuration.

- Repository: https://github.com/mmm13921/fleur-overclock
- Baseline commit: b8a7c9aa045f4d142c9401a9df89216b1b1d4464
- Successful device test: https://github.com/mmm13921/fleur-overclock/actions/runs/44998872003
- Kernel base: Fleux V11 / Linux 4.19.325
- Device: Redmi Note 11S 4G (fleur / MT6781)
- Kernel branding: MEYS VX

## Included work

- EEVDF Linux 6.18 backport, Layer 1, with the audit and patch series.
- HMP / EAS / Hybrid scheduler mode work.
- F2FS Project ID / quota compatibility and Android 13 MediaProvider bridge.
- VFS / mount compatibility work.
- Cgroup v2 and HyperOS filesystem build configuration.
- AnyKernel installers, build scripts, audits, and workflow definitions.
- Modem DPMAIF suspend/resume safety guard.

## Explicit limitations

This is the V15 snapshot, not the later experimental modem-stack transplant. The modem change here is only the DPMAIF PM safety guard; it does not contain a full ECCCI / CCCI / Conn_MD / CCMNI transplant. EEVDF DELAY_DEQUEUE, DELAY_ZERO, and the full sched_delayed lifecycle are also not implemented in this baseline.

The snapshot is stored under this directory for preservation and review. GitHub Actions workflows inside this nested directory are archival copies and are not automatically active workflows; active workflows remain under the repository-root .github/workflows directory.

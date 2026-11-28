# Patch archive — Fleur / MT6781

This directory stores versioned, reviewable snapshots of the kernel and userspace patch work, grouped by subsystem. It is an archive and audit index; the active build workflows continue to use their existing entry points under `scripts/`, `eevdf/`, `vendor/`, and `research/` unless a workflow is explicitly migrated and verified.

## Subsystem folders

| Folder | Scope |
|---|---|
| [walt/](walt/README.md) | Fleur-native WALT accounting, controls, WALT governor, hispeed OPP whitelist, idle-demand fix, diagnostics and reference source |
| [hmp/](hmp/README.md) | MT6781 HMP integration and Fleur 4.14 reference implementation |
| [eevdf/](eevdf/README.md) | Linux 6.18 EEVDF backport, audit and legacy sysctl cleanup |
| [capacity/](capacity/README.md) | CPU capacity-margin variants and schedutil capacity/frequency patches |
| [limits/](limits/README.md) | Scheduler and VM sysctl bound changes |
| [modem/](modem/README.md) | MT6781 DPMAIF modem suspend/resume compatibility |
| [conservative/](conservative/README.md) | Conservative governor audit/docs and DBS sampling-rate experiment |
| [filesystem/](filesystem/README.md) | F2FS, filesystem mount and FUSE compatibility |
| [scheduler/](scheduler/README.md) | HMP/EAS/Hybrid scheduler modes and historical scheduler experiments |
| [overclock/](overclock/README.md) | CPU OC1/OC2/OC3 and GPU 1100 MHz patch scripts |

## Legacy numbered series and build helpers

- `apply/` retains the earlier numbered source-patch series for the Fleux V11/V12 storage and scheduler work.
- `config/` contains build-time configuration helpers.
- `installers/` contains AnyKernel packaging helpers; these are not kernel source patches.

## Archive rules

1. Each subsystem folder contains the patch applicators/reference files and a README describing purpose, scope and validation caveats.
2. Keep archive snapshots synchronized with their active source counterparts whenever a patch changes.
3. Do not treat the presence of a patch in this archive as proof that the current build applies or enables it.
4. Build success/static audits do not prove device boot or runtime correctness. Record device test status separately.
5. Preserve distinct experimental variants and their original values; do not silently merge or replace them.

Device target: Redmi Note 11S 4G (`fleur`), MediaTek MT6781.
Current preferred kernel source for active work: Fleux V12.

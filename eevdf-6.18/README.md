# EEVDF Linux 6.18 backport archive

This directory is the consolidated, source-controlled archive of the MEYS EEVDF Linux 6.18 backport work.

## Scope and provenance

- Target kernel for the historical backport: **Fleux V11 / Linux 4.19.325**.
- Stable starting point used by the experimental work: `meys-build38-boot-patches` (Build 38 + guarded boot patches).
- Expanded implementation branch: `meys-eevdf-618-porting`.
- Earlier Layer 1 + dequeue-bool snapshot: `meys-eevdf-618-full`.
- This archive is a **research and porting record**, not a claim that the backport is production-ready.
- The latest Fleux V12 work must be audited separately. These patchers were authored for V11/4.19.325 and must not be blindly applied to V12.

## Contents

- `PORTING_MATRIX.md`: feature-by-feature implementation and validation state.
- `CHANGELOG.md`: functional changes grouped by layer.
- `COMMITS.md`: commit history from the Build 38 baseline to the EEVDF branches, plus the initial Build 38 EEVDF commits.
- `VALIDATION.md`: exact distinction between source audit, CI, compile, runtime and device boot.
- `BUILD_LOG.md`: preserved detailed failure analysis and CI run references from the original project notes.
- `series`: ordered patcher application list.
- `audit_eevdf_618.py`: static source audit.
- `patches/`: exact Python patchers copied from the latest `meys-eevdf-618-porting` branch.
- `ci/`: archived EEVDF source-audit workflow and the build-script snapshot used by the experimental branch.
- `SOURCE_MANIFEST.md`: source refs and blob hashes for copied artifacts.

## Patch application order

Run the patchers against a **clean, disposable Fleux V11 / 4.19.325 source tree**, in the order listed in `series`. Do not run against the production tree without a clean backup and a fresh diff review. Each patcher has exact-anchor checks and can stop if the source differs.

The scripts are source transformers. Their presence, or a passing marker audit, does not prove scheduler correctness.

## EEVDF features represented in this archive

1. EEVDF augmented timeline: minimum virtual runtime and minimum slice augmentation.
2. Protected virtual deadline / protected slice (`vprot`).
3. `PREEMPT_SHORT` and relative-deadline placement (`PLACE_REL_DEADLINE`).
4. Base-slice controls and normalized sysctl bounds.
5. The `sched_class::dequeue_task()` bool return prerequisite.
6. Fair-task custom slice through the existing `sched_attr.sched_runtime` ABI.
7. Delayed dequeue and zero-lag behavior: `DELAY_DEQUEUE` / `DELAY_ZERO`.
8. Delayed entity accounting across hierarchical task groups, PELT, PSI, uclamp, schedtune, MTK heavy-task counters, IOWAIT, hrtick, CFS throttling, wakeup/requeue, migration, task exit and group teardown.

## Important status warning

The expanded source patcher contains Layer 3 delayed-dequeue work and the static audit checks many of its markers. Historical CI attempts exposed API/anchor and audit mismatches. The available record does **not** establish a successful final full-kernel compile, runtime stress pass, or boot on Redmi Note 11S. See `VALIDATION.md` and `BUILD_LOG.md`.

## Upstream references

- [Linux 6.18 EEVDF documentation](https://docs.kernel.org/scheduler/sched-eevdf.html)
- [Linux v6.18 fair scheduler](https://github.com/torvalds/linux/blob/v6.18/kernel/sched/fair.c)
- [Linux v6.18 scheduler features](https://github.com/torvalds/linux/blob/v6.18/kernel/sched/features.h)
- [Linux v6.18 scheduler core](https://github.com/torvalds/linux/blob/v6.18/kernel/sched/core.c)
- [Linux v6.18 scheduler internals](https://github.com/torvalds/linux/blob/v6.18/kernel/sched/sched.h)
- [Fleux upstream](https://gitlab.com/daliboss/fleux)

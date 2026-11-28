# Validation record

## What is actually established

- The repository contains Layer 1, Layer 2 and Layer 3 source-transformer scripts from `meys-eevdf-618-porting`.
- The audit script statically checks EEVDF symbols, feature switches, delayed-dequeue state and several accounting/cleanup paths.
- Historical CI runs were created for audit and build integration.
- The project notes record failed CI attempts and source/audit mismatches.

## What is not established

- No verified successful final full-kernel compile for the complete Layer 1–3 patch series is established by the archived records.
- No successful final AnyKernel package for this complete experimental port is established.
- No runtime stress test proving delayed-dequeue accounting correctness is recorded.
- No device boot or sustained stability test on Redmi Note 11S is recorded.
- No COD Mobile performance result is established by this EEVDF port.

## Historical CI evidence

- Audit run 45074244223 for commit `323710e7...` was recorded as successful, but the corresponding build run 45074244232 failed during compilation. Audit success did not imply build success.
- Build run 45074696502 and audit run 45074696505 were for intermediate commit `e3006c26...`; they must not be attributed to the later commit.
- Build run 45074713511 and audit run 45074713510 were created for `ddbd0f93...`; the later log records the build failing at “Apply EEVDF layers” and the audit failing on the migration guard assertion.
- Commit `1efa8cfb...` adapted the delayed migration guard to the 4.19 API. The following audit still expected the old `migration_type/migrate_load` expression.
- Commit `2192589e...` updated the audit expectation to the 4.19 guard. The original notes recorded CI runs 45075426116 and 45075426097 as queued at the time of writing; their final conclusions are not established in the archived evidence.

## Known integration problems

1. A `cfs_rq_throttled()` helper was referenced before declaration; a forward declaration was added.
2. The newer `struct lb_env` `migration_type` member and `migrate_load` enum were unavailable in the 4.19 destination API. The guard was adapted to `if (p->se.sched_delayed) return 0;`.
3. The audit still expected the old migration guard after the patcher had been updated; the audit assertion was corrected.
4. Earlier build attempts failed in the patch-application/integration stage. A successful compiler run after all final fixes is not evidenced.

## Required next steps before claiming completion

- Re-run the exact current branch audit and preserve its complete output.
- Apply all three patchers to a clean pinned Fleux source snapshot.
- Review the full transformed-source diff, not only audit markers.
- Compile the full device kernel and inspect warnings.
- Test scheduler accounting and all delayed-dequeue transitions under stress.
- Boot on the target device and test stability before producing a release.

## Status vocabulary

- **Implemented in patcher:** transformation code exists.
- **Applied:** patcher completed against a specific pinned source tree.
- **Static audit PASS:** source markers/structural assertions passed.
- **Build PASS:** compiler and packaging completed.
- **Runtime PASS:** scheduler stress/accounting tests passed.
- **Device boot PASS:** target device booted and remained stable.

Do not collapse these into a single “success” label.

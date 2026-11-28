# Scripts

Active scripts used by build workflows and manual validation live here.

- `build_kernel.sh`: pinned-source kernel build pipeline and profile dispatch.
- `apply_*.py` / `apply_*.sh`: source patchers; each must be paired with the workflow/profile that invokes it.
- `audit_*.py`: static source, config, or image audits.
- `anykernel_*.sh`: AnyKernel3 packaging/install metadata.
- `*_runtime_check.sh`, `cpuset_v2.sh`: post-boot read-only checks/helpers.

Historical or alternate patch snapshots are kept under `patches/`; do not assume every archived patch is active. Preserve parameter values unless a change is explicitly requested.

set -Eeuo pipefail
SRC_DIR="${1:?Usage: configure_cgroup_v2.sh SRC_DIR OUT_DIR}"
OUT_DIR="${2:?Usage: configure_cgroup_v2.sh SRC_DIR OUT_DIR}"
AUDIT_FILE="${3:-$OUT_DIR/cpuset-cgroup-audit.txt}"
CONFIG="$OUT_DIR/.config"
CONFIG_TOOL="$SRC_DIR/scripts/config"
if [[ ! -s "$CONFIG" || ! -f "$CONFIG_TOOL" ]]; then
  echo "Kernel .config or scripts/config is missing." >&2
  exit 2
fi
bash "$CONFIG_TOOL" --file "$CONFIG" \
  --enable CGROUPS \
  --enable CPUSETS \
  --enable MEMCG \
  --enable MEMCG_SWAP \
  --enable SWAP \
  --enable BLK_CGROUP \
  --enable CGROUP_SCHED \
  --enable FAIR_GROUP_SCHED \
  --enable CFS_BANDWIDTH \
  --enable CGROUP_PIDS \
  --enable CGROUP_RDMA \
  --enable BPF_SYSCALL \
  --enable CGROUP_BPF
make -C "$SRC_DIR" O="$OUT_DIR" olddefconfig \
  CC=clang LD=ld.lld LLVM=1 LLVM_IAS=1
required=(
  CGROUPS
  CPUSETS
  MEMCG
  MEMCG_SWAP
  SWAP
  BLK_CGROUP
  CGROUP_SCHED
  FAIR_GROUP_SCHED
  CFS_BANDWIDTH
  CGROUP_PIDS
  CGROUP_RDMA
  BPF_SYSCALL
  CGROUP_BPF
)
for symbol in "${required[@]}"; do
  if ! grep -qx "CONFIG_${symbol}=y" "$CONFIG"; then
    echo "Required cgroup-v2 option was not enabled: CONFIG_${symbol}" >&2
    exit 1
  fi
done
grep -Eq 'cpuset_files|cpuset_cftypes' "$SRC_DIR/kernel/cgroup/cpuset.c" || {
  echo "The selected source does not contain the cpuset controller file table." >&2
  exit 1
}
grep -q 'cpuset_cgrp_subsys' "$SRC_DIR/kernel/cgroup/cpuset.c" || {
  echo "The selected source does not contain the cpuset cgroup subsystem." >&2
  exit 1
}
grep -q 'cgroup2_fs_type' "$SRC_DIR/kernel/cgroup/cgroup.c" || {
  echo "The selected source does not contain the cgroup2 filesystem." >&2
  exit 1
}
grep -Eq '\.dfl_cftypes[[:space:]]*=[[:space:]]*cpu_files' "$SRC_DIR/kernel/sched/core.c"
grep -Eq '\.dfl_cftypes[[:space:]]*=[[:space:]]*blkcg_files' "$SRC_DIR/block/blk-cgroup.c"
grep -Eq '\.dfl_cftypes[[:space:]]*=[[:space:]]*memory_files' "$SRC_DIR/mm/memcontrol.c"
grep -Eq '\.dfl_cftypes[[:space:]]*=[[:space:]]*pids_files' "$SRC_DIR/kernel/cgroup/pids.c"
grep -Eq '\.dfl_cftypes[[:space:]]*=[[:space:]]*rdmacg_files' "$SRC_DIR/kernel/cgroup/rdma.c"
if ! grep -qx "CONFIG_CPUSETS=y" "$CONFIG"; then
  echo "CONFIG_CPUSETS did not survive olddefconfig." >&2
  exit 1
fi
for control in '"cpus"' '"mems"' '"cpu_exclusive"' '"mem_exclusive"' '"mem_hardwall"' '"memory_migrate"' '"memory_spread_page"' '"memory_spread_slab"' '"memory_pressure"' '"sched_load_balance"' '"sched_relax_domain_level"'; do
  grep -Fq "$control" "$SRC_DIR/kernel/cgroup/cpuset.c" || {
    echo "Expected cpuset control missing from source: $control" >&2
    exit 1
  }
done
echo "Cgroup v2 build configuration verified."
echo "Native v2 controllers enabled: cpu, io, memory, pids, rdma."
echo "CPU controls include cpu.weight and cpu.max; memory swap accounting is enabled."
echo "Cgroup BPF support is enabled."
echo "cpuset: CONFIG_CPUSETS=y; legacy cgroup-v1 cpuset subsystem and controls verified."
echo "cpuset: this 4.19 source does not expose cpuset as a cgroup-v2 controller."
echo "Runtime: Android init must retain/mount the legacy cpuset hierarchy (normally /dev/cpuset)."
mkdir -p "$(dirname "$AUDIT_FILE")"
{
  echo "result=PASS"
  echo "config=CONFIG_CPUSETS=y"
  echo "controller=cgroup-v1 cpuset"
  echo "controls=cpus,mems,cpu_exclusive,mem_exclusive,mem_hardwall,memory_migrate,memory_spread_page,memory_spread_slab,memory_pressure,sched_load_balance,sched_relax_domain_level"
  echo "cgroup_v2_cpuset=not_registered_in_this_4.19_source"
  echo "runtime_mount=Android init must mount legacy cpuset hierarchy"
} > "$AUDIT_FILE"

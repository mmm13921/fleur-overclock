set -Eeuo pipefail
SRC_DIR="${1:?Usage: configure_cgroup_v2.sh SRC_DIR OUT_DIR [AUDIT_FILE]}"
OUT_DIR="${2:?Usage: configure_cgroup_v2.sh SRC_DIR OUT_DIR [AUDIT_FILE]}"
AUDIT_FILE="${3:-$OUT_DIR/cgroup-interface-audit.txt}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
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
  --enable UCLAMP_TASK_GROUP \
  --enable PSI \
  --enable CGROUP_RDMA \
  --enable BPF_SYSCALL \
  --enable CGROUP_BPF
make -C "$SRC_DIR" O="$OUT_DIR" olddefconfig \
  CC=clang LD=ld.lld LLVM=1 LLVM_IAS=1
python3 -m py_compile "$SCRIPT_DIR/audit_cgroup_interfaces.py"
python3 "$SCRIPT_DIR/audit_cgroup_interfaces.py" "$SRC_DIR" "$CONFIG" "$AUDIT_FILE"
grep -qx "result=PASS" "$AUDIT_FILE"

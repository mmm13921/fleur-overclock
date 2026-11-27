set -eu
ACTION="${1:-status}"
NAME="${2:-}"
ROOT="${CGROUP2_ROOT:-}"
if [ -z "$ROOT" ]; then
  ROOT="$(awk '$3 == "cgroup2" { print $2; exit }' /proc/mounts)"
fi
if [ -z "$ROOT" ] || [ ! -d "$ROOT" ]; then
  echo "ERROR: cgroup2 mount not found; set CGROUP2_ROOT if mounted elsewhere." >&2
  exit 1
fi
if [ ! -r "$ROOT/cgroup.controllers" ] || [ ! -w "$ROOT/cgroup.subtree_control" ]; then
  echo "ERROR: cgroup2 root controller files are unavailable or not writable: $ROOT" >&2
  exit 1
fi
valid_name() {
  case "$1" in
    ""|*[!A-Za-z0-9_.-]*|"."|"..") return 1 ;;
    *) return 0 ;;
  esac
}
group_path() {
  valid_name "$NAME" || { echo "ERROR: invalid group name." >&2; exit 2; }
  printf '%s/%s' "$ROOT" "$NAME"
}
case "$ACTION" in
  status)
    echo "cgroup2_root=$ROOT"
    echo "available_controllers=$(cat "$ROOT/cgroup.controllers")"
    echo "enabled_root_controllers=$(cat "$ROOT/cgroup.subtree_control")"
    echo "cpuset_cpus_effective=$(cat "$ROOT/cpuset.cpus.effective" 2>/dev/null || true)"
    echo "cpuset_mems_effective=$(cat "$ROOT/cpuset.mems.effective" 2>/dev/null || true)"
    ;;
  enable)
    grep -qw cpuset "$ROOT/cgroup.controllers" || { echo "ERROR: cpuset controller is not advertised by this kernel." >&2; exit 1; }
    if ! grep -qw cpuset "$ROOT/cgroup.subtree_control"; then
      printf '%s' '+cpuset' > "$ROOT/cgroup.subtree_control"
    fi
    echo "cpuset_enabled=yes"
    ;;
  create)
    GROUP="$(group_path)"
    grep -qw cpuset "$ROOT/cgroup.subtree_control" || { echo "ERROR: run '$0 enable' first." >&2; exit 1; }
    [ ! -e "$GROUP" ] || { echo "ERROR: group already exists: $GROUP" >&2; exit 1; }
    MEMS="$(cat "$ROOT/cpuset.mems.effective")"
    CPUS="$(cat "$ROOT/cpuset.cpus.effective")"
    [ -n "$MEMS" ] && [ -n "$CPUS" ] || { echo "ERROR: root effective cpuset values are empty." >&2; exit 1; }
    mkdir "$GROUP"
    if ! { printf '%s' "$MEMS" > "$GROUP/cpuset.mems" && printf '%s' "$CPUS" > "$GROUP/cpuset.cpus"; }; then
      rmdir "$GROUP" 2>/dev/null || true
      echo "ERROR: failed to initialize cpuset from root effective masks." >&2
      exit 1
    fi
    echo "created=$GROUP"
    echo "cpuset.cpus=$CPUS"
    echo "cpuset.mems=$MEMS"
    ;;
  set)
    [ "$#" -eq 4 ] || { echo "Usage: $0 set GROUP CPU_LIST MEM_LIST" >&2; exit 2; }
    GROUP="$(group_path)"
    [ -d "$GROUP" ] || { echo "ERROR: group does not exist: $GROUP" >&2; exit 1; }
    [ -n "$3" ] && [ -n "$4" ] || { echo "ERROR: CPU and memory-node lists must be non-empty." >&2; exit 2; }
    printf '%s' "$4" > "$GROUP/cpuset.mems"
    printf '%s' "$3" > "$GROUP/cpuset.cpus"
    echo "updated=$GROUP"
    echo "cpuset.cpus=$(cat "$GROUP/cpuset.cpus")"
    echo "cpuset.mems=$(cat "$GROUP/cpuset.mems")"
    ;;
  attach)
    [ "$#" -eq 3 ] || { echo "Usage: $0 attach GROUP PID" >&2; exit 2; }
    case "$3" in
      ""|*[!0-9]*|0) echo "ERROR: PID must be a positive integer." >&2; exit 2 ;;
    esac
    GROUP="$(group_path)"
    [ -d "$GROUP" ] && [ -d "/proc/$3" ] || { echo "ERROR: group or PID does not exist." >&2; exit 1; }
    printf '%s' "$3" > "$GROUP/cgroup.procs"
    echo "attached_pid=$3"
    ;;
  show)
    GROUP="$(group_path)"
    [ -d "$GROUP" ] || { echo "ERROR: group does not exist: $GROUP" >&2; exit 1; }
    for FILE in cpuset.cpus cpuset.mems cpuset.cpus.effective cpuset.mems.effective cgroup.procs; do
      if [ -r "$GROUP/$FILE" ]; then
        echo "$FILE=$(tr '\n' ' ' < "$GROUP/$FILE")"
      fi
    done
    ;;
  remove)
    GROUP="$(group_path)"
    [ -d "$GROUP" ] || { echo "ERROR: group does not exist: $GROUP" >&2; exit 1; }
    rmdir "$GROUP"
    echo "removed=$GROUP"
    ;;
  *)
    echo "Usage: $0 {status|enable|create GROUP|set GROUP CPU_LIST MEM_LIST|attach GROUP PID|show GROUP|remove GROUP}" >&2
    exit 2
    ;;
esac

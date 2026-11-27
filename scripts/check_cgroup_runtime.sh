set -eu
ROOT=""
while read -r dev mnt type opts rest; do
  if [ "$type" = "cgroup2" ]; then ROOT="$mnt"; break; fi
done < /proc/mounts
if [ -z "$ROOT" ] || [ ! -r "$ROOT/cgroup.controllers" ]; then
  echo "FAIL: cgroup2 is not mounted or cgroup.controllers is unavailable"
  exit 1
fi
echo "cgroup2_mount=$ROOT"
echo "available_controllers=$(cat "$ROOT/cgroup.controllers")"
echo "enabled_root_controllers=$(cat "$ROOT/cgroup.subtree_control" 2>/dev/null || true)"
for ctl in cpu cpuset io memory pids perf_event rdma; do
  if grep -qw "$ctl" "$ROOT/cgroup.controllers"; then
    echo "controller_$ctl=available"
  else
    echo "controller_$ctl=not-advertised"
  fi
done
found=0
for dir in "$ROOT" "$ROOT"/* "$ROOT"/*/* "$ROOT"/*/*/*; do
  [ -d "$dir" ] || continue
  for file in cpuset.cpus cpuset.mems cpuset.effective_cpus cpuset.effective_mems cpuset.prefer_cpu cpu.weight cpu.weight.nice cpu.max cpu.uclamp.min cpu.uclamp.max cpu.uclamp.latency_sensitive cpu.stat io.stat io.max memory.current memory.min memory.low memory.high memory.max memory.events memory.stat memory.oom.group pids.current pids.max pids.events rdma.current rdma.max cpu.pressure io.pressure memory.pressure; do
    if [ -e "$dir/$file" ]; then
      echo "interface=$dir/$file"
      found=1
    fi
  done
done
if [ "$found" -eq 0 ]; then
  echo "WARN: no controller interface files found below the cgroup2 mount"
fi
echo "read_only_check=yes; no cgroup values or task memberships were changed"

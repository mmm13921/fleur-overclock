set -eu
OUT=/data/local/tmp/fleur-cgroup-v2-preflight
rm -rf "$OUT"
mkdir -p "$OUT"/{props,proc,mounts,configs,init,sysfs}
if [ "$(id -u)" != "0" ]; then
  echo "Run as root: su -c sh collect_cgroup_v2_preflight.sh" >&2
  exit 1
fi
getprop | grep -E 'ro.build.version|ro.build.fingerprint|ro.product.(device|model|vendor)|ro.miui|ro.build.version.sdk' > "$OUT/props/build.txt" || true
cat /proc/cgroups > "$OUT/proc/cgroups.txt" 2>&1 || true
cat /proc/mounts > "$OUT/mounts/proc_mounts.txt" 2>&1 || true
cat /proc/self/mountinfo > "$OUT/mounts/mountinfo.txt" 2>&1 || true
for f in /sys/fs/cgroup/cgroup.controllers /sys/fs/cgroup/cgroup.subtree_control /sys/fs/cgroup/cgroup.type /sys/fs/cgroup/cgroup.events; do
  if [ -r "$f" ]; then cat "$f" > "$OUT/sysfs/$(basename "$f")"; fi
done
for f in /system/etc/cgroups.json /system/etc/task_profiles.json /vendor/etc/cgroups.json /vendor/etc/task_profiles.json /odm/etc/cgroups.json /odm/etc/task_profiles.json /system_ext/etc/cgroups.json /system_ext/etc/task_profiles.json /system/etc/task_profiles/cgroups_33.json /system/etc/task_profiles/task_profiles_33.json; do
  if [ -r "$f" ]; then
    n=$(echo "$f" | sed 's#^/##;s#/#_#g')
    cp "$f" "$OUT/configs/$n"
  fi
done
for d in /dev/cpuctl /dev/memcg /dev/cpuset /dev/blkio /dev/stune /sys/fs/cgroup; do
  if [ -d "$d" ]; then
    n=$(echo "$d" | sed 's#^/##;s#/#_#g')
    ls -laR "$d" > "$OUT/sysfs/$n.txt" 2>&1 || true
  fi
done
for d in /vendor/etc/init /odm/etc/init /system/etc/init /; do
  [ -d "$d" ] || continue
  find "$d" -maxdepth 2 -type f -name '*.rc' 2>/dev/null
done | sort -u > "$OUT/init/rc_files.txt"
while IFS= read -r f; do
  grep -nE -B 3 -A 5 'cgroup|task_profiles|writepid|cpuctl|memcg|cpuset|blkio' "$f" 2>/dev/null | sed "s#^#$f:#" >> "$OUT/init/cgroup_rc_matches.txt" || true
done < "$OUT/init/rc_files.txt"
{
  echo "device=$(getprop ro.product.device)"
  echo "model=$(getprop ro.product.model)"
  echo "android=$(getprop ro.build.version.release)"
  echo "sdk=$(getprop ro.build.version.sdk)"
  echo "fingerprint=$(getprop ro.build.fingerprint)"
  echo "kernel=$(uname -a)"
  echo "cgroup2_mounts:"
  grep -w cgroup2 /proc/mounts || true
  echo "available_v2_controllers:"
  cat /sys/fs/cgroup/cgroup.controllers 2>/dev/null || true
} > "$OUT/SUMMARY.txt"
tar -czf /sdcard/fleur-cgroup-v2-preflight.tar.gz -C /data/local/tmp fleur-cgroup-v2-preflight
echo "/sdcard/fleur-cgroup-v2-preflight.tar.gz"

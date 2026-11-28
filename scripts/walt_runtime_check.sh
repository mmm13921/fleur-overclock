# Read-only WALT / HMP / EEVDF runtime diagnostic for Redmi Note 11S 4G (fleur)
# Run as root: su -c 'sh /path/to/walt_runtime_check.sh'
set -u
PASS=0
WARN=0
FAIL=0
say() { printf '%s\n' "$*"; }
check_file() {
  label="$1"; path="$2"
  if [ -r "$path" ]; then
    value=$(cat "$path" 2>/dev/null | tr '\n' ' ')
    say "PASS | $label | $value"
    PASS=$((PASS + 1))
  else
    say "WARN | $label | missing: $path"
    WARN=$((WARN + 1))
  fi
}
say "=== MEYS Build62 WALT runtime check (read-only) ==="
KREL=$(uname -r 2>/dev/null)
say "kernel_release=$KREL"
case "$KREL" in
  *4.19.325-Meys-Build62-WALT-Full*) say "PASS | expected Build62 WALT kernel"; PASS=$((PASS + 1));;
  *) say "WARN | kernel release does not match Build62 WALT"; WARN=$((WARN + 1));;
esac
for n in sched_walt_ravg_window sched_walt_disabled sched_use_walt_cpu_util sched_use_walt_task_util sched_walt_init_task_load_pct sched_walt_cpu_high_irqload sched_walt_ravg_hist_size sched_walt_window_stats_policy sched_walt_account_wait_time sched_walt_freq_account_wait_time sched_walt_io_is_busy; do
  check_file "$n" "/proc/sys/kernel/$n"
done
if [ -r /proc/sys/kernel/sched_use_walt_cpu_util ]; then
  WALT_CPU_UTIL=$(cat /proc/sys/kernel/sched_use_walt_cpu_util 2>/dev/null)
  if [ "$WALT_CPU_UTIL" = "0" ]; then say "PASS | safe CPUFreq default | WALT CPU util disabled; PELT frequency input active"; PASS=$((PASS + 1)); else say "WARN | safe CPUFreq default | expected sched_use_walt_cpu_util=0, got $WALT_CPU_UTIL"; WARN=$((WARN + 1)); fi
fi
check_file sched_cpu_mode /proc/sys/kernel/sched_cpu_mode
for n in sched_base_slice sched_eevdf_place_lag sched_eevdf_place_deadline_initial sched_eevdf_place_rel_deadline sched_eevdf_run_to_parity sched_eevdf_preempt_short; do
  check_file "$n" "/proc/sys/kernel/$n"
done
for n in sched_latency_ns sched_min_granularity_ns sched_wakeup_granularity_ns; do
  if [ -e "/proc/sys/kernel/$n" ]; then say "FAIL | obsolete EEVDF-conflicting sysctl remains | $n"; FAIL=$((FAIL + 1)); else say "PASS | obsolete CFS sysctl removed | $n"; PASS=$((PASS + 1)); fi
done
say "=== CPUFreq policies ==="
FOUND_POLICY=0
for p in /sys/devices/system/cpu/cpufreq/policy*; do
  [ -d "$p" ] || continue
  FOUND_POLICY=1
  say "policy=$(basename "$p")"
  check_file "scaling_governor $(basename "$p")" "$p/scaling_governor"
  check_file "scaling_available_governors $(basename "$p")" "$p/scaling_available_governors"
  check_file "related_cpus $(basename "$p")" "$p/related_cpus"
  check_file "cpuinfo_cur_freq $(basename "$p")" "$p/cpuinfo_cur_freq"
  if [ -d "$p/walt" ]; then
    check_file "walt up_rate_limit_us $(basename "$p")" "$p/walt/up_rate_limit_us"
    check_file "walt down_rate_limit_us $(basename "$p")" "$p/walt/down_rate_limit_us"
    check_file "walt hispeed_load $(basename "$p")" "$p/walt/hispeed_load"
    check_file "walt hispeed_freq $(basename "$p")" "$p/walt/hispeed_freq"
    check_file "walt boost $(basename "$p")" "$p/walt/boost"
  else
    say "WARN | WALT rate-limit directory missing for $(basename "$p")"
    WARN=$((WARN + 1))
  fi
done
if [ "$FOUND_POLICY" -eq 0 ]; then say "WARN | no CPUFreq policy directories found"; WARN=$((WARN + 1)); fi
say "=== Scheduler / tracepoint availability ==="
if [ -d /sys/kernel/tracing/events ]; then TRACE=/sys/kernel/tracing/events; elif [ -d /sys/kernel/debug/tracing/events ]; then TRACE=/sys/kernel/debug/tracing/events; else TRACE=; fi
if [ -n "$TRACE" ]; then
  for e in walt_update_task_ravg walt_update_history walt_migration_update_sum; do
    if [ -d "$TRACE/sched/$e" ]; then say "PASS | tracepoint sched:$e"; PASS=$((PASS + 1)); else say "WARN | tracepoint sched:$e unavailable"; WARN=$((WARN + 1)); fi
  done
else
  say "WARN | tracefs/debugfs events not mounted or unavailable"
  WARN=$((WARN + 1))
fi
say "=== Build config availability ==="
if [ -r /proc/config.gz ]; then
  for c in CONFIG_SCHED_WALT CONFIG_SCHED_HMP CONFIG_SCHED_HMP_PLUS CONFIG_CPU_FREQ_GOV_WALT CONFIG_CPU_FREQ_GOV_CONSERVATIVE CONFIG_CPU_FREQ_GOV_ONDEMAND CONFIG_IRQ_TIME_ACCOUNTING; do
    if zcat /proc/config.gz 2>/dev/null | grep -q "^$c=y$"; then say "PASS | $c=y"; PASS=$((PASS + 1)); else say "WARN | $c not confirmed in /proc/config.gz"; WARN=$((WARN + 1)); fi
  done
else
  say "WARN | /proc/config.gz unavailable; config checks skipped"
  WARN=$((WARN + 1))
fi
say "=== Summary ==="
say "PASS=$PASS WARN=$WARN FAIL=$FAIL"
say "This script does not change sysctls, governors, CPU masks, thermal limits, or filesystem settings."

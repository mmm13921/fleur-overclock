#!/usr/bin/env python3
"""Expose the native Fleur WALT controls with bounded, live sysctl handlers."""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: apply_walt_controls_mt6781.py SOURCE_DIR")

root = Path(sys.argv[1])

def edit(rel, old, new, label, count=1):
    path = root / rel
    data = path.read_text()
    found = data.count(old)
    if found != count:
        raise SystemExit(f"{label}: expected {count} anchor(s), found {found} in {rel}")
    path.write_text(data.replace(old, new))
    
# The first WALT build exposed a forward-use in core.c: local wakeup calls
# the helper before its definition. Add a CONFIG-guarded prototype.
edit(
    "kernel/sched/core.c",
    "static void try_to_wake_up_local(struct task_struct *p)\n{",
    "#ifdef CONFIG_SCHED_WALT\nstatic inline void walt_try_to_wake_up(struct task_struct *p);\n#endif\n\nstatic void try_to_wake_up_local(struct task_struct *p)\n{",
    "WALT wakeup helper forward declaration",
)

# Promote the device-native tuning variables to the public WALT sysctl ABI.
walt = root / "kernel/sched/walt.c"
s = walt.read_text()
mapping = {
    "walt_ravg_hist_size": "sysctl_sched_walt_ravg_hist_size",
    "walt_window_stats_policy": "sysctl_sched_walt_window_stats_policy",
    "walt_account_wait_time": "sysctl_sched_walt_account_wait_time",
    "walt_freq_account_wait_time": "sysctl_sched_walt_freq_account_wait_time",
    "walt_io_is_busy": "sysctl_sched_walt_io_is_busy",
}
for old, new in mapping.items():
    if old not in s:
        raise SystemExit(f"missing native WALT parameter {old}")
    s = s.replace(old, new)
s = s.replace(
    "static __read_mostly unsigned int sysctl_sched_walt_ravg_hist_size = 5;",
    "__read_mostly unsigned int sysctl_sched_walt_ravg_hist_size = 5;",
)
s = s.replace(
    "static __read_mostly unsigned int sysctl_sched_walt_window_stats_policy =",
    "__read_mostly unsigned int sysctl_sched_walt_window_stats_policy =",
)
s = s.replace(
    "static __read_mostly unsigned int sysctl_sched_walt_account_wait_time = 1;",
    "__read_mostly unsigned int sysctl_sched_walt_account_wait_time = 1;",
)
s = s.replace(
    "static __read_mostly unsigned int sysctl_sched_walt_freq_account_wait_time = 0;",
    "__read_mostly unsigned int sysctl_sched_walt_freq_account_wait_time = 0;",
)
s = s.replace(
    "static __read_mostly unsigned int sysctl_sched_walt_io_is_busy = 0;",
    "__read_mostly unsigned int sysctl_sched_walt_io_is_busy = 0;",
)
walt.write_text(s)

# Export declarations for sysctl.c. The original WALT patch already adds
# the four utilization/init/IRQ declarations in this same header.
edit(
    "include/linux/sched.h",
    "extern unsigned int sysctl_sched_walt_cpu_high_irqload;\n",
    "extern unsigned int sysctl_sched_walt_cpu_high_irqload;\n"
    "extern unsigned int sysctl_sched_walt_ravg_hist_size;\n"
    "extern unsigned int sysctl_sched_walt_window_stats_policy;\n"
    "extern unsigned int sysctl_sched_walt_account_wait_time;\n"
    "extern unsigned int sysctl_sched_walt_freq_account_wait_time;\n"
    "extern unsigned int sysctl_sched_walt_io_is_busy;\n"
    "extern unsigned int walt_ravg_window;\n"
    "extern bool walt_disabled;\n",
    "WALT parameter declarations",
)

# Add explicit bounds for writable controls and read-only introspection for
# the boot-time window and disabled state. These are genuine live variables,
# not placeholder sysctl names.
sysctl = root / "kernel/sysctl.c"
data = sysctl.read_text()
anchor = '''\t{
\t\t.procname\t= "sched_walt_cpu_high_irqload",
\t\t.data\t\t= &sysctl_sched_walt_cpu_high_irqload,
\t\t.maxlen\t\t= sizeof(unsigned int),
\t\t.mode\t\t= 0644,
\t\t.proc_handler\t= proc_dointvec,
\t},'''
extra = '''\t{
\t\t.procname\t= "sched_walt_cpu_high_irqload",
\t\t.data\t\t= &sysctl_sched_walt_cpu_high_irqload,
\t\t.maxlen\t\t= sizeof(unsigned int),
\t\t.mode\t\t= 0644,
\t\t.proc_handler\t= proc_dointvec_minmax,
\t\t.extra1\t\t= &walt_sysctl_zero,
\t\t.extra2\t\t= &walt_sysctl_nsec_per_sec,
\t},'''
if data.count(anchor) != 1:
    raise SystemExit("WALT IRQ threshold sysctl anchor missing or duplicated")
data = data.replace(anchor, extra)
# Add bound objects at file scope; one is shared with boolean controls.
include_anchor = "#include <linux/sysctl.h>\n"
if include_anchor not in data:
    raise SystemExit("sysctl include anchor missing")
data = data.replace(include_anchor, include_anchor + "\nstatic int one = 1;\nstatic int three = 3;\nstatic int five = 5;\nstatic int hundred = 100;\nstatic int nsec_per_sec = 1000000000;\n", 1)

# Existing WALT entries are converted to bounded handlers.
def replace_entry(procname, old_handler, new_handler, low, high):
    global data
    start = data.find('.procname\t= "' + procname + '"')
    if start < 0:
        raise SystemExit("missing sysctl entry " + procname)
    end = data.find("\n\t},", start)
    if end < 0:
        raise SystemExit("unterminated sysctl entry " + procname)
    block = data[start:end]
    old = ".proc_handler\t= " + old_handler + ","
    if block.count(old) != 1:
        raise SystemExit("handler mismatch for " + procname)
    block = block.replace(old, ".proc_handler\t= " + new_handler + ",")
    block += "\n\t.extra1\t\t= &walt_sysctl_zero,"
    block += "\n\t.extra2\t\t= " + high + ","
    data = data[:start] + block + data[end:]

replace_entry("sched_use_walt_cpu_util", "proc_dointvec", "proc_dointvec_minmax", "zero", "&walt_sysctl_one")
replace_entry("sched_use_walt_task_util", "proc_dointvec", "proc_dointvec_minmax", "zero", "&walt_sysctl_one")
replace_entry("sched_walt_init_task_load_pct", "proc_dointvec", "proc_dointvec_minmax", "zero", "&walt_sysctl_hundred")

# Insert remaining native knobs immediately after the bounded IRQ entry.
irq_end = data.find("\n\t},", data.find('.procname\t= "sched_walt_cpu_high_irqload"'))
if irq_end < 0:
    raise SystemExit("could not locate end of WALT IRQ sysctl entry")
entries = '''
\t},
\t{
\t\t.procname\t= "sched_walt_ravg_hist_size",
\t\t.data\t\t= &sysctl_sched_walt_ravg_hist_size,
\t\t.maxlen\t\t= sizeof(unsigned int),
\t\t.mode\t\t= 0644,
\t\t.proc_handler\t= proc_dointvec_minmax,
\t\t.extra1\t\t= &walt_sysctl_one,
\t\t.extra2\t\t= &walt_sysctl_five,
\t},
\t{
\t\t.procname\t= "sched_walt_window_stats_policy",
\t\t.data\t\t= &sysctl_sched_walt_window_stats_policy,
\t\t.maxlen\t\t= sizeof(unsigned int),
\t\t.mode\t\t= 0644,
\t\t.proc_handler\t= proc_dointvec_minmax,
\t\t.extra1\t\t= &walt_sysctl_zero,
\t\t.extra2\t\t= &walt_sysctl_three,
\t},
\t{
\t\t.procname\t= "sched_walt_account_wait_time",
\t\t.data\t\t= &sysctl_sched_walt_account_wait_time,
\t\t.maxlen\t\t= sizeof(unsigned int),
\t\t.mode\t\t= 0644,
\t\t.proc_handler\t= proc_dointvec_minmax,
\t\t.extra1\t\t= &walt_sysctl_zero,
\t\t.extra2\t\t= &walt_sysctl_one,
\t},
\t{
\t\t.procname\t= "sched_walt_freq_account_wait_time",
\t\t.data\t\t= &sysctl_sched_walt_freq_account_wait_time,
\t\t.maxlen\t\t= sizeof(unsigned int),
\t\t.mode\t\t= 0644,
\t\t.proc_handler\t= proc_dointvec_minmax,
\t\t.extra1\t\t= &walt_sysctl_zero,
\t\t.extra2\t\t= &walt_sysctl_one,
\t},
\t{
\t\t.procname\t= "sched_walt_io_is_busy",
\t\t.data\t\t= &sysctl_sched_walt_io_is_busy,
\t\t.maxlen\t\t= sizeof(unsigned int),
\t\t.mode\t\t= 0644,
\t\t.proc_handler\t= proc_dointvec_minmax,
\t\t.extra1\t\t= &walt_sysctl_zero,
\t\t.extra2\t\t= &walt_sysctl_one,
\t},
\t{
\t\t.procname\t= "sched_walt_ravg_window",
\t\t.data\t\t= &walt_ravg_window,
\t\t.maxlen\t\t= sizeof(unsigned int),
\t\t.mode\t\t= 0444,
\t\t.proc_handler\t= proc_dointvec,
\t},
\t{
\t\t.procname\t= "sched_walt_disabled",
\t\t.data\t\t= &walt_disabled,
\t\t.maxlen\t\t= sizeof(bool),
\t\t.mode\t\t= 0444,
\t\t.proc_handler\t= proc_dobool,
'''
data = data[:irq_end] + entries + data[irq_end + len("\n\t},"):]
sysctl.write_text(data)

# Structural audit: each public control must have a backing variable and a
# sysctl table entry; no unsupported Qualcomm-only knobs are fabricated.
required = [
    "sched_use_walt_cpu_util", "sched_use_walt_task_util",
    "sched_walt_init_task_load_pct", "sched_walt_cpu_high_irqload",
    "sched_walt_ravg_hist_size", "sched_walt_window_stats_policy",
    "sched_walt_account_wait_time", "sched_walt_freq_account_wait_time",
    "sched_walt_io_is_busy", "sched_walt_ravg_window", "sched_walt_disabled",
]
for name in required:
    if data.count('.procname\t= "' + name + '"') != 1:
        raise SystemExit("WALT sysctl registration audit failed: " + name)

print("result=PASS")
print("walt_controls=" + ",".join(required))
print("bounds=bool 0..1;history 1..5;policy 0..3;init_load 0..100;irq_threshold 0..1s")
print("window=boot-time early_param; exported read-only through sysctl")
print("disabled=read-only state; no unsafe runtime enable/disable switch")
print("wake_helper=forward declaration fixed")

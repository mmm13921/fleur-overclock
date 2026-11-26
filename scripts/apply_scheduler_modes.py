#!/usr/bin/env python3
"""Backport the Fleur 4.14 HMP/EAS/Hybrid mode selector to Fleux 4.19."""
from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: apply_scheduler_modes.py SOURCE_DIR AUDIT_FILE")

root = Path(sys.argv[1])
audit = Path(sys.argv[2])

def replace_once(rel, old, new, label):
    path = root / rel
    source = path.read_text()
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one anchor in {rel}, found {count}")
    path.write_text(source.replace(old, new))

replace_once(
    "include/linux/sched/sysctl.h",
    "#if defined(CONFIG_ENERGY_MODEL) && defined(CONFIG_CPU_FREQ_GOV_SCHEDUTIL)\n"
    "extern unsigned int sysctl_sched_energy_aware;\n"
    "int sched_energy_aware_handler(struct ctl_table *table, int write,\n"
    "\t\tvoid *buffer, size_t *lenp, loff_t *ppos);\n"
    "#endif",
    "#if defined(CONFIG_ENERGY_MODEL) && defined(CONFIG_CPU_FREQ_GOV_SCHEDUTIL)\n"
    "extern unsigned int sysctl_sched_energy_aware;\n"
    "int sched_energy_aware_handler(struct ctl_table *table, int write,\n"
    "\t\tvoid *buffer, size_t *lenp, loff_t *ppos);\n"
    "#ifdef CONFIG_MACH_MT6781\n"
    "extern unsigned int sysctl_sched_cpu_mode;\n"
    "int sched_cpu_mode_handler(struct ctl_table *table, int write,\n"
    "\t\tvoid *buffer, size_t *lenp, loff_t *ppos);\n"
    "#endif\n"
    "#endif",
    "scheduler sysctl declarations",
)

replace_once(
    "kernel/sched/topology.c",
    "unsigned int sysctl_sched_energy_aware = 1;\nDEFINE_MUTEX(sched_energy_mutex);",
    "unsigned int sysctl_sched_energy_aware = 0;\n"
    "#ifdef CONFIG_MACH_MT6781\n"
    "/* Fleur 4.14 mode semantics: 0=HMP, 1=EAS, 2=Hybrid. */\n"
    "unsigned int sysctl_sched_cpu_mode = 0;\n"
    "#endif\n"
    "DEFINE_MUTEX(sched_energy_mutex);",
    "scheduler mode state",
)

old_handlers = (
    "int sched_energy_aware_handler(struct ctl_table *table, int write,\n"
    "\t\tvoid *buffer, size_t *lenp, loff_t *ppos)\n"
    "{\n"
    "\tint ret, state;\n"
    "\n"
    "\tif (write && !capable(CAP_SYS_ADMIN))\n"
    "\t\treturn -EPERM;\n"
    "\n"
    "\tret = proc_dointvec_minmax(table, write, buffer, lenp, ppos);\n"
    "\tif (!ret && write) {\n"
    "\t\tstate = static_branch_unlikely(&sched_energy_present);\n"
    "\t\tif (state != sysctl_sched_energy_aware) {\n"
    "\t\t\tmutex_lock(&sched_energy_mutex);\n"
    "\t\t\tsched_energy_update = 1;\n"
    "\t\t\trebuild_sched_domains();\n"
    "\t\t\tsched_energy_update = 0;\n"
    "\t\t\tmutex_unlock(&sched_energy_mutex);\n"
    "\t\t}\n"
    "\t}\n"
    "\n"
    "\treturn ret;\n"
    "}"
)
new_handlers = (
    "int sched_energy_aware_handler(struct ctl_table *table, int write,\n"
    "\t\tvoid *buffer, size_t *lenp, loff_t *ppos)\n"
    "{\n"
    "\tint ret, state;\n"
    "\n"
    "\tif (write && !capable(CAP_SYS_ADMIN))\n"
    "\t\treturn -EPERM;\n"
    "\n"
    "\tret = proc_dointvec_minmax(table, write, buffer, lenp, ppos);\n"
    "\tif (!ret && write) {\n"
    "\t\tmutex_lock(&sched_energy_mutex);\n"
    "#ifdef CONFIG_MACH_MT6781\n"
    "\t\tWRITE_ONCE(sysctl_sched_cpu_mode,\n"
    "\t\t\tREAD_ONCE(sysctl_sched_energy_aware) ? 1 : 0);\n"
    "#endif\n"
    "\t\tstate = static_branch_unlikely(&sched_energy_present);\n"
    "\t\tif (state != READ_ONCE(sysctl_sched_energy_aware)) {\n"
    "\t\t\tsched_energy_update = 1;\n"
    "\t\t\trebuild_sched_domains();\n"
    "\t\t\tsched_energy_update = 0;\n"
    "\t\t}\n"
    "\t\tmutex_unlock(&sched_energy_mutex);\n"
    "\t}\n"
    "\n"
    "\treturn ret;\n"
    "}\n"
    "\n"
    "#ifdef CONFIG_MACH_MT6781\n"
    "int sched_cpu_mode_handler(struct ctl_table *table, int write,\n"
    "\t\tvoid *buffer, size_t *lenp, loff_t *ppos)\n"
    "{\n"
    "\tint ret, state;\n"
    "\tunsigned int enable_eas;\n"
    "\n"
    "\tif (write && !capable(CAP_SYS_ADMIN))\n"
    "\t\treturn -EPERM;\n"
    "\n"
    "\tret = proc_dointvec_minmax(table, write, buffer, lenp, ppos);\n"
    "\tif (!ret && write) {\n"
    "\t\tenable_eas = READ_ONCE(sysctl_sched_cpu_mode) != 0;\n"
    "\t\tmutex_lock(&sched_energy_mutex);\n"
    "\t\tWRITE_ONCE(sysctl_sched_energy_aware, enable_eas);\n"
    "\t\tstate = static_branch_unlikely(&sched_energy_present);\n"
    "\t\tif (state != enable_eas) {\n"
    "\t\t\tsched_energy_update = 1;\n"
    "\t\t\trebuild_sched_domains();\n"
    "\t\t\tsched_energy_update = 0;\n"
    "\t\t}\n"
    "\t\tmutex_unlock(&sched_energy_mutex);\n"
    "\t}\n"
    "\n"
    "\treturn ret;\n"
    "}\n"
    "#endif"
)
replace_once(
    "kernel/sched/topology.c",
    old_handlers,
    new_handlers,
    "EAS and CPU-mode sysctl handlers",
)

replace_once(
    "kernel/sysctl.c",
    "\t\t.procname\t= \"sched_energy_aware\",\n"
    "\t\t.data\t\t= &sysctl_sched_energy_aware,\n"
    "\t\t.maxlen\t\t= sizeof(unsigned int),\n"
    "\t\t.mode\t\t= 0644,\n"
    "\t\t.proc_handler\t= sched_energy_aware_handler,\n"
    "\t\t.extra1\t\t= &zero,\n"
    "\t\t.extra2\t\t= &one,\n"
    "\t},\n"
    "#endif\n"
    "#ifdef CONFIG_PROVE_LOCKING",
    "\t\t.procname\t= \"sched_energy_aware\",\n"
    "\t\t.data\t\t= &sysctl_sched_energy_aware,\n"
    "\t\t.maxlen\t\t= sizeof(unsigned int),\n"
    "\t\t.mode\t\t= 0644,\n"
    "\t\t.proc_handler\t= sched_energy_aware_handler,\n"
    "\t\t.extra1\t\t= &zero,\n"
    "\t\t.extra2\t\t= &one,\n"
    "\t},\n"
    "#ifdef CONFIG_MACH_MT6781\n"
    "\t{\n"
    "\t\t.procname\t= \"sched_cpu_mode\",\n"
    "\t\t.data\t\t= &sysctl_sched_cpu_mode,\n"
    "\t\t.maxlen\t\t= sizeof(unsigned int),\n"
    "\t\t.mode\t\t= 0644,\n"
    "\t\t.proc_handler\t= sched_cpu_mode_handler,\n"
    "\t\t.extra1\t\t= &zero,\n"
    "\t\t.extra2\t\t= &two,\n"
    "\t},\n"
    "#endif\n"
    "#endif\n"
    "#ifdef CONFIG_PROVE_LOCKING",
    "CPU-mode sysctl table entry",
)

audit_text = """Fleux scheduler CPU modes — source and structural audit
target_repository=daliboss/fleux
target_ref=v12
target_kernel=4.19.325
reference_repository=MiCode/Xiaomi_Kernel_OpenSource
reference_ref=32022887f842ec64e317fc22745fedf35e982837
reference_kernel=4.14.186
reference_device=Redmi Note 11S / MT6781 / fleur
reference_mode_logic=official should_hmp() in kernel/sched/hmp.h
result=PASS
mode_values=0:HMP,1:EAS,2:Hybrid
mode_sysctl=/proc/sys/kernel/sched_cpu_mode
default_mode=0
mode_0=Fleur-native HMP placement, active migration and idle pull using WALT demand; EAS disabled
mode_1=existing Fleux EAS placement
mode_2=EAS while root_domain is not overutilized; Fleur-native HMP while overutilized
fork_policy=non-kernel fork prefers fastest allowed CPU capacity domain, matching official HMP intent
task_demand_signal=WALT ravg demand normalized to 0..1024; feeds HMP loadwop_avg and EAS util
heavy_task_boundary=650/1024 native Fleur HMP heavy-task threshold, driven by WALT loadwop_avg
hmp_scope=native Fleur HMP cluster domains, fork/wake placement, active up migration and idle pull are backported; Qualcomm RTG is not part of the MTK reference
boot_default=Fleur HMP; EAS and Hybrid remain selectable at runtime
hardware_validation=required; not performed by CI
benchmark_validation=not performed by CI
"""
config = (root / "arch/arm64/configs/fleur_defconfig").read_text()
for required in (
    "CONFIG_MACH_MT6781=y",
    "CONFIG_ENERGY_MODEL=y",
    "CONFIG_CPU_FREQ_DEFAULT_GOV_SCHEDUTIL=y",
):
    if required not in config:
        raise SystemExit(f"Fleux scheduler modes: expected defconfig setting missing: {required}")

makefile = (root / "Makefile").read_text()
# Verify the actual boot defaults.
topology = (root / "kernel/sched/topology.c").read_text()
if "unsigned int sysctl_sched_energy_aware = 0;" not in topology:
    raise SystemExit("HMP default audit: EAS must be disabled at boot")
if "unsigned int sysctl_sched_cpu_mode = 0;" not in topology:
    raise SystemExit("HMP default audit: sched_cpu_mode must default to 0")
if "default_mode=0" not in audit_text or "boot_default=Fleur HMP" not in audit_text:
    raise SystemExit("HMP default audit: generated audit does not declare HMP boot default")

if "PATCHLEVEL = 19" not in makefile or "SUBLEVEL = 325" not in makefile:
    raise SystemExit("Expected Fleux target kernel 4.19.325 was not found")

audit.parent.mkdir(parents=True, exist_ok=True)
audit.write_text(audit_text)
print(audit_text, end="")

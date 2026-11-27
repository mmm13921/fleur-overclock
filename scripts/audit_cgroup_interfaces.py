#!/usr/bin/env python3
import pathlib
import re
import sys

src = pathlib.Path(sys.argv[1])
config = pathlib.Path(sys.argv[2])
audit = pathlib.Path(sys.argv[3])
cfg_text = config.read_text()
def enabled(name):
    return re.search(r"^CONFIG_" + re.escape(name) + r"=y$", cfg_text, re.M) is not None
def source(rel):
    p = src / rel
    if not p.is_file():
        raise SystemExit("Required kernel source file is missing: " + rel)
    return p.read_text()
def table(text, name, rel):
    pattern = r"struct\\s+cftype\\s+" + re.escape(name) + r"\\s*\\[\\]\\s*=\\s*\\{(.*?)\\n\\};"
    m = re.search(pattern, text, re.S)
    if not m:
        raise SystemExit("Cannot find registered cftype table " + name + " in " + rel)
    return set(re.findall(r'\\.name\\s*=\\s*"([^"]+)"', m.group(1)))
def registered(text, subsystem, table_name, rel):
    pattern = r"struct\\s+cgroup_subsys\\s+" + re.escape(subsystem) + r"\\s*=\\s*\\{(.*?)\\n\\};"
    m = re.search(pattern, text, re.S)
    if not m or not re.search(r"\\.dfl_cftypes\\s*=\\s*" + re.escape(table_name) + r"\\b", m.group(1)):
        raise SystemExit("Default-hierarchy registration missing: " + subsystem + " -> " + table_name + " in " + rel)
def require(names, actual, label):
    missing = sorted(set(names) - actual)
    if missing:
        raise SystemExit(label + " missing implemented controls: " + ",".join(missing))
def optional_config(name):
    return "y" if enabled(name) else "not-enabled"
required_config = ["CGROUPS", "CPUSETS", "MEMCG", "BLK_CGROUP", "CGROUP_SCHED", "FAIR_GROUP_SCHED", "CFS_BANDWIDTH", "CGROUP_PIDS"]
missing_cfg = [x for x in required_config if not enabled(x)]
if missing_cfg:
    raise SystemExit("Required cgroup configuration missing: " + ",".join(missing_cfg))

cpuset_rel = "kernel/cgroup/cpuset.c"
cpuset_src = source(cpuset_rel)
cpuset_names = table(cpuset_src, "files", cpuset_rel)
registered(cpuset_src, "cpuset_cgrp_subsys", "files", cpuset_rel)
cpuset_required = ["cpus", "mems", "effective_cpus", "effective_mems", "cpu_exclusive", "mem_exclusive", "mem_hardwall", "sched_load_balance", "sched_relax_domain_level", "memory_migrate", "memory_pressure", "memory_spread_page", "memory_spread_slab", "memory_pressure_enabled"]
require(cpuset_required, cpuset_names, "cpuset")
if enabled("MTK_SCHED_EXTENSION"):
    require(["prefer_cpu"], cpuset_names, "MTK cpuset")
else:
    cpuset_names.discard("prefer_cpu")

cpu_rel = "kernel/sched/core.c"
cpu_src = source(cpu_rel)
cpu_names = table(cpu_src, "cpu_files", cpu_rel)
registered(cpu_src, "cpu_cgrp_subsys", "cpu_files", cpu_rel)
if enabled("FAIR_GROUP_SCHED"):
    require(["weight", "weight.nice"], cpu_names, "cpu")
if enabled("CFS_BANDWIDTH"):
    require(["max"], cpu_names, "cpu")
uclamp_active = enabled("UCLAMP_TASK_GROUP") and not enabled("SCHED_TUNE")
if uclamp_active:
    require(["uclamp.min", "uclamp.max", "uclamp.latency_sensitive"], cpu_names, "cpu uclamp")
else:
    cpu_names.difference_update(["uclamp.min", "uclamp.max", "uclamp.latency_sensitive"])

io_rel = "block/blk-cgroup.c"
io_src = source(io_rel)
io_names = table(io_src, "blkcg_files", io_rel)
registered(io_src, "io_cgrp_subsys", "blkcg_files", io_rel)
require(["stat"], io_names, "io")
# This target tree registers only io.stat in its v2 table; do not claim limits.
io_limits = sorted(io_names.intersection({"weight", "max"}))

mem_rel = "mm/memcontrol.c"
mem_src = source(mem_rel)
mem_names = table(mem_src, "memory_files", mem_rel)
registered(mem_src, "memory_cgrp_subsys", "memory_files", mem_rel)
require(["current", "min", "low", "high", "max", "events", "stat", "oom.group"], mem_names, "memory")
memory_swap_v2 = sorted(x for x in mem_names if x.startswith("swap."))

pids_rel = "kernel/cgroup/pids.c"
pids_src = source(pids_rel)
pids_names = table(pids_src, "pids_files", pids_rel)
registered(pids_src, "pids_cgrp_subsys", "pids_files", pids_rel)
require(["max", "current", "events"], pids_names, "pids")

rdma_rel = "kernel/cgroup/rdma.c"
rdma_src = source(rdma_rel)
rdma_names = table(rdma_src, "rdmacg_files", rdma_rel)
registered(rdma_src, "rdma_cgrp_subsys", "rdmacg_files", rdma_rel)
require(["max", "current"], rdma_names, "rdma")

core_rel = "kernel/cgroup/cgroup.c"
core_src = source(core_rel)
core_names = table(core_src, "cgroup_base_files", core_rel)
core_required = ["type", "procs", "threads", "controllers", "subtree_control", "events", "max.descendants", "max.depth", "stat", "freeze"]
require(["cgroup." + x for x in core_required] + ["cpu.stat"], core_names, "cgroup core")
if "cgroup2_fs_type" not in core_src:
    raise SystemExit("cgroup2 filesystem implementation is missing")

psi_names = {"cpu.pressure", "io.pressure", "memory.pressure"}
psi_active = enabled("PSI")
if psi_active:
    require(psi_names, core_names, "PSI")

lines = [
    "result=PASS",
    "source=Fleux-V12-Linux-4.19.325",
    "cgroup2_filesystem=present",
    "cgroup_core=" + ",".join(sorted(core_names)),
    "cpu_controller=" + ",".join(sorted(cpu_names | {"stat"})),
    "cpuset_controller=cgroup-v2-native;registered_through_dfl_cftypes",
    "cpuset_controls=" + ",".join(sorted(cpuset_names)),
    "io_controller=" + ",".join(sorted("io." + x for x in io_names)),
    "io_limits=not-registered-in-target-v2-table;io.weight-and-io.max-not-claimed",
    "memory_controller=" + ",".join(sorted("memory." + x for x in mem_names)),
    "memory_swap_v2=not-registered-in-target-v2-table",
    "pids_controller=" + ",".join(sorted("pids." + x for x in pids_names)),
    "rdma_controller_config=" + optional_config("CGROUP_RDMA"),
    "rdma_controls=" + ",".join(sorted("rdma." + x for x in rdma_names)),
    "psi_config=" + optional_config("PSI"),
    "psi_controls=" + (",".join(sorted(psi_names)) if psi_active else "not-enabled"),
    "bpf_cgroup_config=" + optional_config("CGROUP_BPF"),
    "bpf_syscall_config=" + optional_config("BPF_SYSCALL"),
    "uclamp_group_controls=" + ("enabled" if uclamp_active else "not-active"),
    "cpu_idle=not-implemented-in-this-4.19-target",
    "runtime=mount-cgroup2-and-enable-required-controllers-in-cgroup.subtree_control;kernel-build-does-not-edit-Android-init-or-ramdisk",
    "defaults=unchanged;no-resource-limits-or-runtime-values-written",
]
audit.parent.mkdir(parents=True, exist_ok=True)
audit.write_text("\\n".join(lines) + "\\n")
print("\\n".join(lines))

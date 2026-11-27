# Native cgroup v2 CPUSET runtime helper

The Fleux V12 4.19.325 source registers CPUSET natively on the cgroup v2 default hierarchy. The build enables CONFIG_CPUSETS and audits the actual cftype registration. This helper manages a single named child cgroup below the mounted cgroup2 root; it does not run automatically at boot and does not change any CPU or task placement until the operator explicitly invokes `enable`, `create`, `set`, or `attach`.

## Install and inspect

The AnyKernel3 ZIP contains `cpuset-v2.sh`. After flashing, copy it to a writable location, for example:

```sh
su
cp /path/to/cpuset-v2.sh /data/local/tmp/cpuset-v2.sh
chmod 0755 /data/local/tmp/cpuset-v2.sh
/data/local/tmp/cpuset-v2.sh status
```

## Explicit setup

```sh
su
/data/local/tmp/cpuset-v2.sh enable
/data/local/tmp/cpuset-v2.sh create game
/data/local/tmp/cpuset-v2.sh set game 6-7 0
/data/local/tmp/cpuset-v2.sh show game
/data/local/tmp/cpuset-v2.sh attach game PID
```

Replace CPU and memory-node lists with values valid on the running device. The example `6-7` is illustrative only; confirm online CPUs and memory nodes first. `attach` moves the entire process (all its threads) to the group. Do not move Android system processes or framework services without understanding the impact.

## Rollback

Move attached processes back to the root or another cgroup before removing the child. Then run:

```sh
/data/local/tmp/cpuset-v2.sh remove game
```

The helper deliberately does not disable the root cpuset controller, mount cgroup2, edit init/ramdisk files, set boot-time defaults, or change task affinity. The `enable` action writes `+cpuset` to the cgroup2 root's `cgroup.subtree_control`; Android init or vendor policy may own this hierarchy and may reject or later overwrite the change. All commands require root. If the controller is not advertised or the hierarchy is not writable, the helper exits with an error rather than falling back to cgroup v1.

## Supported CPUSET v2 files in this kernel source

`cpuset.cpus`, `cpuset.mems`, `cpuset.effective_cpus`, `cpuset.effective_mems`, `cpuset.cpu_exclusive`, `cpuset.mem_exclusive`, `cpuset.mem_hardwall`, `cpuset.sched_load_balance`, `cpuset.sched_relax_domain_level`, `cpuset.memory_migrate`, `cpuset.memory_pressure`, `cpuset.memory_spread_page`, `cpuset.memory_spread_slab`, and `cpuset.memory_pressure_enabled`. `cpuset.prefer_cpu` is conditional on MTK_SCHED_EXTENSION.

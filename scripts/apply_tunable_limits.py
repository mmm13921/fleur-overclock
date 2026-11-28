import re
import sys
from pathlib import Path

if len(sys.argv) != 3:
    raise SystemExit("usage: apply_tunable_limits.py SOURCE_DIR AUDIT_FILE")

root = Path(sys.argv[1])
audit = Path(sys.argv[2])
path = root / "kernel/sysctl.c"
source = path.read_text()

# Boolean, enumeration, and coupled RT controls retain their semantic ranges.
# Every other numeric sched_* sysctl gets a zero lower bound and no artificial
# sysctl upper bound. Native C type limits and scheduler arithmetic still apply.
SCHED_PROTECTED = {
    "sched_child_runs_first",
    "sched_base_slice",
    "sched_eevdf_place_lag",
    "sched_eevdf_place_deadline_initial",
    "sched_eevdf_place_rel_deadline",
    "sched_eevdf_run_to_parity",
    "sched_eevdf_preempt_short",
    "sched_tunable_scaling",
    "sched_schedstats",
    "sched_autogroup_enabled",
    "sched_energy_aware",
    "sched_cpu_mode",
    "sched_cfs_bandwidth_slice_us",
    "sched_rt_period_us",
    "sched_rt_runtime_us",
    "sched_rr_timeslice_ms",
}
VM_TARGETS = {"extfrag_threshold", "watermark_scale_factor", "swappiness"}
GENERIC_MINMAX = {
    "proc_dointvec_minmax",
    "proc_douintvec_minmax",
    "proc_doulongvec_minmax",
    "proc_dointvec_minmax_warn_RT_change",
    "watermark_scale_factor_sysctl_handler",
}

def matching_brace(text, start):
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i + 1
    raise SystemExit("unterminated sysctl table entry")

# Dedicated type-correct zero values for signed, unsigned-int and unsigned-long
# minmax handlers. Add them before kern_table so all entries can reference them.
anchor = "static struct ctl_table kern_table[] = {"
if source.count(anchor) != 1:
    raise SystemExit("kern_table declaration anchor not found exactly once")
zero_decls = (
    "static int sched_minimum_zero = 0;\n"
    "static unsigned int sched_minimum_zero_uint = 0;\n"
    "static unsigned long sched_minimum_zero_ul = 0;\n\n"
)
if "static int sched_minimum_zero = 0;" not in source:
    source = source.replace(anchor, zero_decls + anchor, 1)

matches = list(re.finditer(r'\.procname\s*=\s*"([^"]+)"', source))
edits = []
declared_minimums = set()
changed = []
already_unbounded = []
custom_handlers = []
vm_changed = []
granularity_names = {"sched_shares_ratelimit"}

for match in matches:
    name = match.group(1)
    is_sched = name.startswith("sched_") and name not in SCHED_PROTECTED
    is_vm = name in VM_TARGETS
    if not (is_sched or is_vm):
        continue

    start = source.rfind("{", 0, match.start())
    if start < 0:
        raise SystemExit(f"{name}: sysctl entry opening brace not found")
    end = matching_brace(source, start)
    entry = source[start:end]
    handler = re.search(r'\.proc_handler\s*=\s*([A-Za-z0-9_]+)', entry)
    if not handler:
        raise SystemExit(f"{name}: proc_handler missing")
    handler_name = handler.group(1)

    if is_vm:
        if handler_name not in GENERIC_MINMAX:
            already_unbounded.append(name)
            continue
        new_entry = re.sub(r'(?m)^\s*\.extra1\s*=.*\n', '', entry)
        new_entry = re.sub(r'(?m)^\s*\.extra2\s*=.*\n', '', new_entry)
        if new_entry == entry:
            raise SystemExit(f"{name}: expected VM bounds were not found")
        edits.append((start, end, new_entry))
        vm_changed.append(name)
        continue

    # Scheduler granularity/latency controls use sched_proc_update_handler,
    # which consumes extra1/extra2 as signed integer minimum/maximum pointers.
    if handler_name == "sched_proc_update_handler":
        minimum = re.search(r'\.extra1\s*=\s*&([A-Za-z0-9_]+)', entry)
        if not minimum:
            raise SystemExit(f"{name}: scheduler minimum pointer missing")
        minimum_name = minimum.group(1)
        declared_minimums.add(minimum_name)
        new_entry = re.sub(r'(?m)^\s*\.extra2\s*=.*\n', '', entry)
        if ".extra2" in new_entry:
            raise SystemExit(f"{name}: maximum pointer could not be removed")
        edits.append((start, end, new_entry))
        changed.append(name)
        if name in granularity_names:
            already_unbounded.append(name + ":minimum-zero")
        continue

    if handler_name in GENERIC_MINMAX:
        if handler_name == "proc_douintvec_minmax":
            zero_ptr = "&sched_minimum_zero_uint"
        elif handler_name == "proc_doulongvec_minmax":
            zero_ptr = "&sched_minimum_zero_ul"
        else:
            zero_ptr = "&sched_minimum_zero"
        new_entry = re.sub(r'(?m)^\s*\.extra1\s*=.*\n', "", entry)
        new_entry = re.sub(r'(?m)^\s*\.extra2\s*=.*\n', "", new_entry)
        handler_line = re.search(r'(?m)^\s*\.proc_handler\s*=.*\n', new_entry)
        if not handler_line:
            raise SystemExit(f"{name}: handler line disappeared during patch")
        new_entry = new_entry[:handler_line.start()] + (
            "\t\t.extra1\t\t= " + zero_ptr + ",\n"
        ) + new_entry[handler_line.start():]
        edits.append((start, end, new_entry))
        changed.append(name)
        continue

    if handler_name == "proc_dointvec":
        new_entry = re.sub(
            r'(\.proc_handler\s*=\s*)proc_dointvec(\s*,)',
            r'\1proc_dointvec_minmax\2', entry, count=1)
        if new_entry == entry:
            raise SystemExit(f"{name}: proc_dointvec handler conversion failed")
        handler_line = re.search(r'(?m)^\s*\.proc_handler\s*=.*\n', new_entry)
        new_entry = new_entry[:handler_line.start()] + (
            "\t\t.extra1\t\t= &sched_minimum_zero,\n"
        ) + new_entry[handler_line.start():]
        edits.append((start, end, new_entry))
        changed.append(name)
        continue

    if handler_name == "proc_douintvec":
        # Unsigned parser naturally accepts [0, UINT_MAX], with no sysctl cap.
        if ".extra2" in entry:
            raise SystemExit(f"{name}: unsigned plain handler unexpectedly has extra2")
        already_unbounded.append(name)
        continue

    if ".extra2" in entry:
        raise SystemExit(
            f"{name}: unrecognized custom handler {handler_name} still has an upper bound"
        )
    custom_handlers.append(f"{name}:{handler_name}")
    already_unbounded.append(name)

# Apply edits from the end so source offsets remain valid.
for start, end, replacement in sorted(edits, key=lambda item: item[0], reverse=True):
    source = source[:start] + replacement + source[end:]

# Apply zero lower bounds after table edits so original source offsets stay valid.
for minimum_name in sorted(declared_minimums):
    decl = re.compile(
        r'(?m)^(\s*static\s+int\s+' + re.escape(minimum_name) +
        r'\s*)(?:=\s*[^;]*)?;'
    )
    source, count = decl.subn(r'\1= 0;', source, count=1)
    if count != 1:
        raise SystemExit(f"minimum declaration {minimum_name} not found exactly once")

# Audit every non-protected scheduler table entry: no extra2 maximum survives.
for match in list(re.finditer(r'\.procname\s*=\s*"([^"]+)"', source)):
    name = match.group(1)
    if not name.startswith("sched_") or name in SCHED_PROTECTED:
        continue
    start = source.rfind("{", 0, match.start())
    end = matching_brace(source, start)
    entry = source[start:end]
    if ".extra2" in entry:
        raise SystemExit(f"{name}: scheduler maximum pointer remains")
    if name in changed and ".extra1" not in entry and "proc_douintvec" not in entry:
        raise SystemExit(f"{name}: scheduler zero minimum pointer missing")

if "static int sched_minimum_zero = 0;" not in source:
    raise SystemExit("signed scheduler zero value missing")
for required in ('"sched_base_slice"', '"sched_walt_cpu_high_irqload"',
                 '"extfrag_threshold"', '"watermark_scale_factor"', '"swappiness"'):
    if required not in source:
        raise SystemExit(f"required tunable missing from sysctl.c: {required}")

path.write_text(source)
audit.parent.mkdir(parents=True, exist_ok=True)
audit.write_text(
    "result=PASS\n"
    "scope=all numeric scheduler sysctls except protected booleans/enums/RT-coupled controls\n"
    "scheduler_minimum=0\n"
    "scheduler_maximum=no extra2 sysctl pointer; natural C storage/type limits remain\n"
    "scheduler_bounds_normalized=" + (",".join(sorted(changed)) or "none") + "\n"
    "scheduler_already_unbounded=" + (",".join(sorted(already_unbounded)) or "none") + "\n"
    "vm_bounds_removed=" + (",".join(sorted(vm_changed)) or "none") + "\n"
    "eevdf_bounds=sched_base_slice remains 0..100000000 ns; EEVDF feature switches remain boolean 0..1\n"
    "sampling_rate=handled by existing DBS unlimited patch with overflow protection\n"
    "protected_semantics=" + ",".join(sorted(SCHED_PROTECTED)) + "\n"
    "custom_handlers_review=" + (",".join(sorted(custom_handlers)) or "none") + "\n"
    "natural_type_limits=retained; signed/unsigned storage and kernel arithmetic remain finite\n"
)
print(audit.read_text(), end="")

"""Backport the sched_class dequeue bool contract needed by Linux 6.18 EEVDF."""
from pathlib import Path
import re
import sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else "kernel-src")
audit = Path(sys.argv[2] if len(sys.argv) > 2 else "eevdf-dequeue-bool-audit.txt")

def read(path):
    return (root / path).read_text()

def write(path, content):
    (root / path).write_text(content)

def replace_once(path, old, new, label):
    src = read(path)
    count = src.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one anchor in {path}, found {count}")
    write(path, src.replace(old, new))

def find_body_end(src, open_brace):
    depth = 0
    state = "code"
    i = open_brace
    while i < len(src):
        ch = src[i]
        nxt = src[i + 1] if i + 1 < len(src) else ""
        if state == "line":
            if ch == "\n":
                state = "code"
        elif state == "block":
            if ch == "*" and nxt == "/":
                state = "code"
                i += 1
        elif state == "string":
            if ch == "\\":
                i += 1
            elif ch == '"':
                state = "code"
        elif state == "char":
            if ch == "\\":
                i += 1
            elif ch == "'":
                state = "code"
        else:
            if ch == "/" and nxt == "/":
                state = "line"
                i += 1
            elif ch == "/" and nxt == "*":
                state = "block"
                i += 1
            elif ch == '"':
                state = "string"
            elif ch == "'":
                state = "char"
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    raise SystemExit("unbalanced C function body")

def convert_dequeue_function(path, name):
    src = read(path)
    pattern = re.compile(r"(?m)^static\\s+void\\s+" + re.escape(name) + r"\\s*\\(")
    matches = list(pattern.finditer(src))
    if len(matches) != 1:
        raise SystemExit(f"{path}:{name}: expected one definition, found {len(matches)}")
    match = matches[0]
    open_brace = src.find("{", match.end())
    if open_brace < 0:
        raise SystemExit(f"{path}:{name}: opening brace not found")
    close_brace = find_body_end(src, open_brace)
    body = src[open_brace + 1:close_brace]
    if re.search(r"\\breturn\\s*;", body) or re.search(r"\\breturn\\s+[^;]+;", body):
        raise SystemExit(f"{path}:{name}: existing return path needs manual review")
    signature = src[match.start():match.end()].replace("static void", "static bool", 1)
    updated = (
        src[:match.start()] + signature + src[match.end():close_brace]
        + "\\n\\treturn true;\\n" + src[close_brace:]
    )
    write(path, updated)

# The bool contract is a prerequisite only: all existing classes still return
# true, preserving 4.19 behaviour until delayed dequeue is integrated.
replace_once(
    "kernel/sched/sched.h",
    "void (*dequeue_task) (struct rq *rq, struct task_struct *p, int flags);",
    "bool (*dequeue_task) (struct rq *rq, struct task_struct *p, int flags);",
    "sched_class dequeue_task return type",
)

replace_once(
    "kernel/sched/core.c",
    "static inline void dequeue_task(struct rq *rq, struct task_struct *p, int flags)",
    "static inline bool dequeue_task(struct rq *rq, struct task_struct *p, int flags)",
    "core dequeue_task wrapper return type",
)
replace_once(
    "kernel/sched/core.c",
    "\\tuclamp_rq_dec(rq, p);\\n\\tp->sched_class->dequeue_task(rq, p, flags);",
    "\\tuclamp_rq_dec(rq, p);\\n\\treturn p->sched_class->dequeue_task(rq, p, flags);",
    "core dequeue_task bool propagation",
)

classes = {
    "kernel/sched/deadline.c": "dequeue_task_dl",
    "kernel/sched/fair.c": "dequeue_task_fair",
    "kernel/sched/idle.c": "dequeue_task_idle",
    "kernel/sched/rt.c": "dequeue_task_rt",
    "kernel/sched/stop_task.c": "dequeue_task_stop",
}
for path, name in classes.items():
    convert_dequeue_function(path, name)

checks = {
    "class_pointer_bool": "bool (*dequeue_task)" in read("kernel/sched/sched.h"),
    "core_wrapper_bool": "static inline bool dequeue_task(" in read("kernel/sched/core.c"),
    "core_returns_class_result": "return p->sched_class->dequeue_task(rq, p, flags);" in read("kernel/sched/core.c"),
    "all_scheduler_classes_bool": all(
        re.search(r"static bool\\s+" + name + r"\\s*\\(", read(path)) is not None
        and "return true;" in read(path)[read(path).find(name):read(path).find(name) + 5000]
        for path, name in classes.items()
    ),
}
lines = [
    "Meys EEVDF Linux 6.18 backport — dequeue API prerequisite",
    "target=Fleux V11 / Linux 4.19.325",
    "scope=sched_class dequeue_task bool contract; no scheduling behaviour changed",
]
for name, ok in checks.items():
    lines.append(("PASS=" if ok else "FAIL=") + name)
lines += [
    "delay_dequeue=NOT_IMPLEMENTED",
    "delay_zero=NOT_IMPLEMENTED",
    "build_status=NOT_RUN_BY_PATCHER",
    "device_boot_status=NOT_TESTED",
    "result=" + ("PASS" if all(checks.values()) else "FAIL"),
]
audit.parent.mkdir(parents=True, exist_ok=True)
audit.write_text("\\n".join(lines) + "\\n")
print("\\n".join(lines))
if not all(checks.values()):
    raise SystemExit("dequeue bool API audit failed")

#!/usr/bin/env python3
import pathlib, re, shutil, sys, urllib.request

kernel = pathlib.Path(sys.argv[1]).resolve()
govsrc = pathlib.Path(sys.argv[2]).resolve()
cpufreq = kernel / "drivers/cpufreq"
kconfig = cpufreq / "Kconfig"
makefile = cpufreq / "Makefile"
defconfig = kernel / "arch/arm64/configs/fleur_defconfig"

# Only governors with real C implementations in the pinned source collection.
# Names that are aliases, hotplug controllers, or lack a compatible source are
# deliberately not fabricated as CPUFreq governors.
items = [
    # Removed: Intelliactive requires unavailable asm/cputime.h on Fleux 4.19.
    ("IMPULSE", "impulse"),
    ("BLU_ACTIVE", "blu_active"),
    ("SMARTASS2", "smartass2"),
    ("SMARTMAX", "smartmax"),
    ("SMARTMAX_EPS", "smartmax_eps"),
    ("LIONHEART", "lionheart"),
    ("WHEATLEY", "wheatley"),
    ("LAGFREE", "lagfree"),
    ("ALUCARD", "alucard"),
    ("DARKNESS", "darkness"),
    ("NIGHTMARE", "nightmare"),
    ("DANCEDANCE", "dancedance"),
    ("PEGASUSQ", "pegasusq"),
    ("LAZY", "lazy"),
    ("ZZMOOVE", "zzmoove"),
    ("SLP", "slp"),
    ("INTELLIMM", "intellimm"),
]
extra_sources = {
    "lazy": "https://raw.githubusercontent.com/CyanogenMod-Atrix/android_kernel_motorola_olympus/84f8f2605eb02002edc40b3a74aed7fce6b5951d/drivers/cpufreq/cpufreq_lazy.c",
    "zzmoove": "https://raw.githubusercontent.com/jollaman999/jolla-kernel_bullhead/bf1729ad11762767a4a594b3e2461cdcfcb53953/drivers/cpufreq/cpufreq_zzmoove.c",
    "slp": "https://raw.githubusercontent.com/agat63/AGAT_L720_kernel/9ad2fff5b692de31a11dfd4081801602064678e1/drivers/cpufreq/cpufreq_slp.c",
    "intellimm": "https://raw.githubusercontent.com/GrifoDev/SuperKernel/32c3130d8ec98f5f3b8846d7d56f224c66189093/drivers/cpufreq/cpufreq_intellimm.c",
}
added = []
missing = []
for symbol, name in items:
    filename = f"cpufreq_{name}.c"
    candidates = [govsrc / filename, govsrc / "sammy gov_freq" / filename]
    source = next((p for p in candidates if p.is_file()), None)
    if source is None and name in extra_sources:
        source = govsrc / filename
        try:
            urllib.request.urlretrieve(extra_sources[name], source)
        except Exception as error:
            print(f"Could not download {name}: {error}")
            source = None
    if source is None:
        missing.append(name)
        continue
    target = cpufreq / filename
    shutil.copy2(source, target)
    # Android's legacy Interactive governor includes asm/cputime.h, which
    # does not exist on this ARM64 4.19 tree. The header is unused by this
    # implementation (idle accounting comes from linux/tick.h).
    if name == "interactive":
        text = target.read_text()
        text = text.replace("#include <asm/cputime.h>", "")
        trace_stub = """/*
 * This 4.19 base does not ship the Android Interactive trace header.
 * Keep the governor functional while compiling out optional trace events.
 */
#define trace_cpufreq_interactive_notyet(...) do { } while (0)
#define trace_cpufreq_interactive_already(...) do { } while (0)
#define trace_cpufreq_interactive_target(...) do { } while (0)
#define trace_cpufreq_interactive_setspeed(...) do { } while (0)
#define trace_cpufreq_interactive_boost(...) do { } while (0)
#define trace_cpufreq_interactive_unboost(...) do { } while (0)
"""
        text = text.replace(
            "#define CREATE_TRACE_POINTS" + chr(10) + "#include <trace/events/cpufreq_interactive.h>",
            trace_stub.rstrip(),
        )
        if "trace/events/cpufreq_interactive.h" in text or "asm/cputime.h" in text:
            raise SystemExit("Interactive compatibility headers were not removed")
        target.write_text(text)
    added.append((symbol, name, filename))

k = kconfig.read_text()
marker = 'comment "CPU frequency scaling drivers"'
if marker not in k:
    raise SystemExit("Kconfig insertion marker not found")
blocks = []
for symbol, name, filename in added:
    key = f"config CPU_FREQ_GOV_{symbol}"
    if key in k:
        continue
    blocks.append(
        f'config CPU_FREQ_GOV_{symbol}\n'
        f'\ttristate "\'{name}\' CPUFreq governor"\n'
        f'\tdepends on CPU_FREQ\n'
        f'\tselect CPU_FREQ_GOV_COMMON\n'
        f'\thelp\n'
        f'\t  Enable the {name} CPU frequency governor.\n'
    )
k = k.replace(marker, "\n".join(blocks) + "\n" + marker, 1)
kconfig.write_text(k)

m = makefile.read_text()
marker = "# CPUfreq governors"
if marker not in m:
    raise SystemExit("Makefile insertion marker not found")
entries = []
for symbol, name, filename in added:
    line = f"obj-$(CONFIG_CPU_FREQ_GOV_{symbol})\t+= {filename[:-2]}.o"
    if line not in m:
        entries.append(line)
m = m.replace(marker, marker + "\n" + "\n".join(entries), 1)
makefile.write_text(m)

cfg = defconfig.read_text()
cfg = re.sub(r"^CONFIG_CPU_FREQ_DEFAULT_GOV_[A-Z0-9_]+=.*\n", "", cfg, flags=re.M)
cfg = re.sub(r"^# CONFIG_CPU_FREQ_DEFAULT_GOV_[A-Z0-9_]+ is not set\n", "", cfg, flags=re.M)
for symbol, name, filename in added:
    cfg = re.sub(rf"^(?:CONFIG_CPU_FREQ_GOV_{symbol}=.*|# CONFIG_CPU_FREQ_GOV_{symbol} is not set)\n", "", cfg, flags=re.M)
cfg += "\n# MX Guardian CPUFreq governors\nCONFIG_CPU_FREQ_DEFAULT_GOV_SCHEDUTIL=y\n"
for symbol, name, filename in added:
    cfg += f"CONFIG_CPU_FREQ_GOV_{symbol}=y\n"
defconfig.write_text(cfg)

print("MX Guardian governors added:")
for symbol, name, filename in added:
    print(f"  {name}: {filename}")
print("Not available in pinned source collection: " + (", ".join(missing) if missing else "none"))
print("Not implemented as standalone CPUFreq governors: interactiveX, lionheartX, hotplug")

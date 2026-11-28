# Conservative CPUFreq governor and DBS sampling

This folder contains the conservative-governor audit/documentation and the DBS sampling-rate patch script.

The conservative governor itself is provided by the Fleux kernel source/configuration; this archive does not claim a new governor implementation. The DBS sampling-rate change is a separate patch and must only be treated as active when a build workflow explicitly applies it.

See `conservative-governor.md` for configuration and runtime validation notes. Active scripts/docs remain under `scripts/` and `docs/`.

# Scheduler and VM tunable limits

This folder archives `apply_tunable_limits.py` and the associated limit specification.

The patch changes sysctl validation bounds for the targeted scheduler/VM controls while preserving protected booleans, enumerations, and coupled real-time controls. It does not imply that every parameter is safe at every accepted value; native type limits, arithmetic constraints, and runtime stability still apply.

The active build entry point is `scripts/apply_tunable_limits.py`. Keep this archive synchronized with the active script.

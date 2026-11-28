# Scheduler modes and scheduler experiments

This folder archives the HMP/EAS/Hybrid mode patch and the scheduler latency experiment.

- `apply_scheduler_modes.py`: adds the Fleur scheduler-mode interface and its mode selection integration.
- `apply_sched_nr_latency_1.sh`: historical latency experiment; this is not the default scheduler configuration and should not be assumed active in current builds.

EEVDF core and legacy-interface cleanup are archived separately under `patches/eevdf/`. Active build scripts remain under `scripts/`.

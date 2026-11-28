# CPU capacity and schedutil integration

This folder contains the capacity-margin variants and schedutil capacity/frequency integration patches.

## Contents
- `apply_capacity_margin_1.py`, `apply_capacity_margin_10.py`, `apply_capacity_margin_stock.py`, `apply_capacity_margin_zero.py`: explicit capacity-margin variants. Their values and semantics are distinct; do not substitute one for another without a requested test.
- `apply_schedutil_capacity_frequency.py`, `apply_schedutil_static_capacity.py`: schedutil capacity/frequency behavior patches.

Only the variant explicitly selected by a build workflow is active in that build. The presence of a patch here does not mean it is enabled in the current kernel.

Active build scripts remain under `scripts/`; synchronize archive copies after any change.

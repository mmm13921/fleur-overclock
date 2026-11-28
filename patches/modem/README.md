# MT6781 modem power-management compatibility

This folder archives the DPMAIF syscore suspend/resume compatibility patch and its comparison notes.

The patch adds modem-state and DPMAIF-state guards around resume restoration and keeps the existing Fleux syscore path. It is a targeted PM compatibility change, not a general modem performance patch.

The active build entry point remains `scripts/apply_modem_pm_compat.py`; keep the archived copy synchronized.

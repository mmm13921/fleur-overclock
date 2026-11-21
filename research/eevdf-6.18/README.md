# Linux 6.18 EEVDF backport work

This directory contains the source-level compatibility audit for the V11 kernel tree.

The V11 baseline already contains the EEVDF core (weighted virtual-time accounting, lag tracking, eligibility, virtual deadlines, and the augmented minimum-deadline tree). The audit separately checks the Linux 6.18 extensions that are not implied by the presence of that core: minimum-slice tree augmentation, protected slices, short-slice preemption, relative-deadline placement, delayed dequeue/zero-lag handling, and custom slices.

A PASS from the audit means the named source symbols and integration points exist; it is not a substitute for a successful kernel build, scheduler stress tests, or device boot validation. The Build 30 filesystem/Project-ID baseline remains the source of truth and must be preserved by all subsequent build changes.

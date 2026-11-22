# Meys V1 — EEVDF Linux 6.18 backport

این پوشه محل اصلی نگهداری فایل‌های EEVDF است.

## ساختار
- `audit_eevdf_618.py`: ممیزی نمادها و قابلیت‌های EEVDF موجود در سورس V11 در برابر قابلیت‌های موردنیاز Linux 6.18.
- `patches/0001-eevdf-core-618.py`: لایه اول EEVDF و رابط custom slice؛ در build روی سورس V11 اعمال می‌شود.
- `patches/0002-dequeue-bool.py`: پیش‌نیاز تغییر قرارداد dequeue به bool.
- پارامترهای `/proc/sys/kernel`: `sched_base_slice`, `sched_eevdf_place_lag`, `sched_eevdf_place_deadline_initial`, `sched_eevdf_place_rel_deadline`, `sched_eevdf_run_to_parity`, `sched_eevdf_preempt_short`.
- `sched_attr.sched_runtime` برای custom slice وظیفه‌های fair؛ مقدار صفر یعنی استفاده از base slice.
- `series`: ترتیب اعمال پچ‌ها پس از آماده‌شدن اولین پچ.

## وضعیت فعلی
لایه اول شامل min_vruntime/min_slice tree، protected slice، PREEMPT_SHORT، PLACE_REL_DEADLINE و sched_base_slice است. رابط custom_slice نیز از طریق sched_attr.sched_runtime پیاده‌سازی شده است: تغییر slice در همان policy تشخیص داده می‌شود و sched_getattr مقدار مؤثر را گزارش می‌کند. پیش‌نیاز API برای بازگشت bool از sched_class::dequeue_task اضافه شده؛ فعلاً همه‌ی کلاس‌ها true برمی‌گردانند. DELAY_DEQUEUE/DELAY_ZERO هنوز پیاده‌سازی نشده‌اند. build و بوت دستگاه باید جداگانه تأیید شوند.

## قواعد حفظ مبنا
شاخه‌ی کار `meys-eevdf-618-full` است و از آخرین مبنای موفق پچ‌شده‌ی Build 38 (`meys-build38-boot-patches`) ساخته شده است. مبنای فایل‌سیستم، F2FS، Project ID/Quota، مودم و HMP حفظ می‌شود؛ تغییرات EEVDF نباید این مبنا را بازنویسی یا حذف کنند.

مرجع upstream: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/kernel/sched/fair.c?h=v6.18

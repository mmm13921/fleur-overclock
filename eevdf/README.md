# Meys V1 — EEVDF Linux 6.18 backport

این پوشه محل اصلی نگهداری فایل‌های EEVDF است.

## ساختار
- `audit_eevdf_618.py`: ممیزی نمادها و قابلیت‌های EEVDF موجود در سورس V11 در برابر قابلیت‌های موردنیاز Linux 6.18.
- `patches/0001-eevdf-core-618.py`: لایه اول بک‌پورت اجرایی؛ در build روی سورس V11 اعمال می‌شود.
- `series`: ترتیب اعمال پچ‌ها پس از آماده‌شدن اولین پچ.

## وضعیت فعلی
لایه اول شامل min_vruntime/min_slice tree، protected slice، PREEMPT_SHORT، PLACE_REL_DEADLINE و sched_base_slice است. DELAY_DEQUEUE/DELAY_ZERO و custom_slice هنوز در لایه‌های بعدی پیاده‌سازی می‌شوند؛ build و بوت دستگاه باید جداگانه تأیید شوند.

## قواعد حفظ مبنا
شاخه‌ی کار `meys-v1-eevdf` است. مبنای فایل‌سیستم، F2FS، Project ID/Quota و HMP همان Build 30 با تگ `meys-projectid-30` باقی می‌ماند. تغییرات EEVDF نباید این مبنا را بازنویسی یا حذف کنند.

مرجع upstream: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/kernel/sched/fair.c?h=v6.18

# Meys V1 — EEVDF Linux 6.18 backport

این پوشه محل اصلی نگهداری فایل‌های EEVDF است.

## ساختار
- `audit_eevdf_618.py`: ممیزی نمادها و قابلیت‌های EEVDF موجود در سورس V11 در برابر قابلیت‌های موردنیاز Linux 6.18.
- `patches/`: محل پچ‌های واقعی بک‌پورت؛ هر پچ باید مستقل، قابل اعمال با `git apply` و همراه با توضیح وابستگی‌ها باشد.
- `series`: ترتیب اعمال پچ‌ها پس از آماده‌شدن اولین پچ.

## وضعیت فعلی
در حال حاضر فایل‌های ممیزی و مستندات منتقل شده‌اند، اما هنوز پچ اجرایی scheduler برای قابلیت‌های جاافتاده‌ی EEVDF 6.18 ساخته و build-test نشده است. فایل placeholder پچ به‌عنوان پچ واقعی معرفی نمی‌شود.

## قواعد حفظ مبنا
شاخه‌ی کار `meys-v1-eevdf` است. مبنای فایل‌سیستم، F2FS، Project ID/Quota و HMP همان Build 30 با تگ `meys-projectid-30` باقی می‌ماند. تغییرات EEVDF نباید این مبنا را بازنویسی یا حذف کنند.

مرجع upstream: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/kernel/sched/fair.c?h=v6.18

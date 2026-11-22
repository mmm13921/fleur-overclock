# فهرست خطاهای بیلد و workflow

این index باید برای هر خطای جدید با یک مورد جدید تکمیل شود. جزئیات EEVDF در [eevdf-618.md](eevdf-618.md) و خطاهای عمومی در [known-ci-failures.md](known-ci-failures.md) ثبت شده‌اند.

## خطاهای ثبت‌شده

| خطا | زمینه | درس |
|---|---|---|
| `cfs_rq_throttled` قبل از declaration | EEVDF delayed dequeue | prototype با امضای دقیق 4.19 لازم است |
| `struct lb_env.migration_type` وجود ندارد | EEVDF migration | API مقصد را بررسی کن، کد نسخهٔ جدید را کپی نکن |
| `migrate_load` تعریف نشده | EEVDF migration | enum مقصد را بررسی کن |
| audit `migration_load_balance_guard` شکست خورد | EEVDF run 45074713511 | patcher و audit باید روی خروجی واقعی یکسان باشند |
| AnyKernel `Unsupported device Aborting` | packaging | device props و whitelist را با دستگاه واقعی تطبیق بده |
| Android 13 `thrashing_limit=300` موجب bootloop | VM/LMKD tuning | مقادیر userspace و kernel را تفکیک کن؛ تغییر را بدون rollback تکرار نکن |
| app data / Recorder / Telegram رفتار نادرست | storage/media | علت را بدون logcat و تفکیک FUSE/F2FS/MediaProvider فرض نکن |

## فرمت ثبت خطای جدید

- تاریخ و شناسهٔ run:
- branch و commit:
- workflow/job/step:
- اولین خطای واقعی:
- root cause: قطعی / محتمل / نامشخص
- فایل و patch:
- fix commit:
- rerun IDs:
- audit / compile / package / artifact / boot / device test:
- ریسک یا مورد حل‌نشده:

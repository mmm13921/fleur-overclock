# فهرست خطاهای بیلد و workflow

این index باید با هر خطای جدید تکمیل شود. قبل از هر بیلد آن را بخوان و علت‌های ثبت‌شده را دوباره تولید نکن. جزئیات EEVDF در [eevdf-618.md](eevdf-618.md) و خطاهای عمومی در [known-ci-failures.md](known-ci-failures.md) آمده‌اند.

## خطاهای ثبت‌شده

| خطا | زمینه | درس / اقدام پیشگیرانه |
|---|---|---|
| `cfs_rq_throttled` قبل از declaration | EEVDF delayed dequeue | prototype با امضای دقیق سورس مقصد لازم است |
| `struct lb_env.migration_type` وجود ندارد | EEVDF migration در 4.19.325 | API مقصد را بررسی کن؛ کد 6.18 را مستقیم کپی نکن |
| `migrate_load` تعریف نشده | EEVDF migration | enum مقصد را بررسی کن |
| audit `migration_load_balance_guard` شکست خورد | EEVDF run 45074713511 | patcher و audit باید guard واقعی و یکسان را بررسی کنند |
| audit assertion قدیمی `env->migration_type != migrate_load` | EEVDF run 45075293762 | پس از تغییر patcher، assertion audit نیز اصلاح شود |
| AnyKernel `Unsupported device Aborting` | packaging | device props و whitelist را با دستگاه واقعی تطبیق بده |
| Android 13 `thrashing_limit=300` موجب bootloop | VM/LMKD tuning | مقادیر userspace و kernel را تفکیک کن؛ بدون rollback تکرار نکن |
| app data / Recorder / Telegram رفتار نادرست | storage/media | علت را بدون logcat و تفکیک FUSE/F2FS/MediaProvider فرض نکن |
| Build 48 و Build 49 مشکل storage را رفع نکردند | FUSE/F2FS/Project ID | این buildها را storage fix معرفی نکن؛ FUSE 4.14 نیز هنوز full port نشده |
| جمع‌آوری modem log با `Bad system call` | MT Manager | علت محیط اجرا نامشخص؛ این خطا را خرابی مودم تلقی نکن |
| EEVDF build error گزارش‌شده در 2026-11-23 | گفتگو؛ run/commit در پیام موجود مشخص نشده | شناسهٔ run و اولین خطای واقعی باید از Actions بازیابی شود؛ علت را حدس نزن |

## شناسه‌های CI تاریخی

- Build run 45073299374 failed: https://github.com/mmm13921/fleur-overclock/actions/runs/45073299374
- Build run 45074244232 failed: https://github.com/mmm13921/fleur-overclock/actions/runs/45074244232
- Audit run 45071909603 success (static checks only): https://github.com/mmm13921/fleur-overclock/actions/runs/45071909603
- Audit run 45074244223 success for commit 323710e7... but paired kernel build failed: https://github.com/mmm13921/fleur-overclock/actions/runs/45074244223
- Build run 45074713510 failed at `Apply EEVDF layers`: https://github.com/mmm13921/fleur-overclock/actions/runs/45074713510
- Audit run 45074713511 failed at migration guard assertion: https://github.com/mmm13921/fleur-overclock/actions/runs/45074713511
- Audit run 45075293762 failed because the audit expected the obsolete migration guard: https://github.com/mmm13921/fleur-overclock/actions/runs/45075293762
- Rerun pair after audit assertion fix: Build 45075426116 and Audit 45075426097; historical status at time of note was queued, so final result must be rechecked.

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

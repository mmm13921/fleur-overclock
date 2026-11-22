# خطاهای CI و درس‌های مشترک

این فایل برای خطاهای بین‌حوزه‌ای است. خطاهای اختصاصی EEVDF در [eevdf-618.md](eevdf-618.md) و index در [build-failures-index.md](build-failures-index.md) آمده‌اند.

## AnyKernel3: Unsupported device Aborting
- در تلاش‌های قبلی گزارش شده است.
- علت محتمل: mismatch بین device name properties و getpropهای واقعی ROM یا whitelist.
- پیشگیری: قبل از release فایل‌های AnyKernel، device props، slot behavior و اسکریپت تشخیص را با دستگاه واقعی تطبیق بده؛ `fleur`, `miel`, `missi` را بی‌دلیل معادل فرض نکن.
- root cause قطعی run تاریخی در دسترس نیست.

## Workflow و source patcher
- پیش از ایجاد workflow جدید، workflowهای موجود و triggerها را بررسی کن؛ job تکراری نساز.
- patcher باید anchorها را دقیق و fail-fast بررسی کند؛ substring داخل comment تعریف function یا macro نیست.
- پس از patch فایل C/headers تولیدشده را inspect کن.
- static audit موفق، compile را اثبات نمی‌کند؛ compile موفق، packaging را اثبات نمی‌کند؛ packaging موفق، boot و runtime را اثبات نمی‌کند.
- patcher و audit باید روی source/guard واقعی یکسان assert داشته باشند.
- برای هر شکست، اولین خطای واقعی از log استخراج شود؛ پیام‌های cascading پایین‌تر root cause نیستند.

## Storage و modem
- Build 48 و 49 مشکل app-data/storage را حل نکردند؛ reinstall تلگرام fix کرنل محسوب نمی‌شود.
- Full FUSE 4.14 port و full modem 4.14 port تأیید نشده‌اند.
- خطای `Bad system call` هنگام جمع‌آوری modem log علت نامشخص دارد و نباید به‌عنوان خرابی driver ثبت شود.
- هر تغییر storage باید FBE/fscrypt، inline crypto، F2FS و دادهٔ کاربر را حفظ کند؛ هیچ wipe/format انجام نشود.

## خطاهای EEVDF شناخته‌شده
- Build run 45073299374 failed: https://github.com/mmm13921/fleur-overclock/actions/runs/45073299374
- Build run 45074244232 failed: https://github.com/mmm13921/fleur-overclock/actions/runs/45074244232
- Audit run 45071909603 success (static checks only): https://github.com/mmm13921/fleur-overclock/actions/runs/45071909603
- Audit run 45074244223 success for commit 323710e7... while paired build failed: https://github.com/mmm13921/fleur-overclock/actions/runs/45074244223
- Build 45074713510 failed in Apply EEVDF layers: https://github.com/mmm13921/fleur-overclock/actions/runs/45074713510
- Audit 45074713511 failed migration guard check: https://github.com/mmm13921/fleur-overclock/actions/runs/45074713511
- Audit 45075293762 failed due to stale assertion after patcher change: https://github.com/mmm13921/fleur-overclock/actions/runs/45075293762
- Reruns 45075426116 (Build) and 45075426097 (Audit) were queued at the time of historical note; recheck actual final status before relying on them.

## EEVDF build error mentioned 2026-11-23
A further EEVDF build error was reported in conversation, but the message available for this archive did not include a run ID, commit SHA, or log excerpt. Record it as an unresolved report only. Do not invent a root cause; retrieve the matching Actions run and append the first real error before fixing.

## الزام ثبت برای بیلدهای بعدی
هر run باید branch، commit SHA، workflow name، run ID و URL، مرحلهٔ failure، 30–100 خط اطراف اولین خطای واقعی، root cause certainty، فایل‌های تغییرکرده، fix commit و وضعیت audit/build/package/artifact/device test داشته باشد.

# خطاهای CI و درس‌های مشترک

این فایل برای ثبت خطاهای بین‌حوزه‌ای است. خطاهای اختصاصی EEVDF در [eevdf-618.md](eevdf-618.md) آمده‌اند.

## خطاهای بسته‌بندی و دستگاه

### AnyKernel3: Unsupported device Aborting
- گزارش شده در تلاش‌های قبلی AnyKernel.
- علت محتمل در سوابق: mismatch بین device name properties و getpropهای واقعی دستگاه/ROM یا نام‌های پشتیبانی‌شده در AnyKernel.
- روش پیشگیری: قبل از release، فایل‌های AnyKernel، device props و اسکریپت تشخیص را با دستگاه واقعی بررسی کن؛ نام‌های `fleur`, `miel`, `missi` را بی‌دلیل معادل فرض نکن.
- وضعیت: علت دقیق آن run تاریخی با لاگ کامل در این گزارش موجود نیست؛ بنابراین root cause قطعی ثبت نمی‌شود.

## خطاهای workflow و source patcher

- چندین بار CI در مراحل patching/compile شکست خورده و کاربر درخواست اصلاح ریشه‌ای داشته است.
- patcher باید anchorها را دقیق بررسی کند؛ جستجوی substring می‌تواند به‌خاطر comment یا نام متغیر، وجود macro/function واقعی را اشتباه تشخیص دهد.
- بعد از تغییر patcher باید source generated را inspect کرد؛ موفقیت اجرای Python یا static audit، صحت خروجی C را تضمین نمی‌کند.
- workflowهای قدیمی/تکراری باید از بیلد اصلی تفکیک شوند؛ قبل از ایجاد workflow تازه، فایل‌های موجود و triggerها را بررسی کن.

## خطاهای CI EEVDF که ثبت شده‌اند

- Build run 45073299374 failed: https://github.com/mmm13921/fleur-overclock/actions/runs/45073299374
- Build run 45074244232 failed: https://github.com/mmm13921/fleur-overclock/actions/runs/45074244232
- Audit run 45071909603 success (static checks only): https://github.com/mmm13921/fleur-overclock/actions/runs/45071909603
- Audit run 45074244223 success for commit 323710e7... but paired kernel build failed: https://github.com/mmm13921/fleur-overclock/actions/runs/45074244223

## الزام ثبت برای بیلدهای بعدی

برای هر run ذخیره شود:
- branch, commit SHA, workflow name, run ID و URL.
- مرحلهٔ دقیق failure و 30–100 خط log اطراف اولین خطای واقعی.
- علت ریشه‌ای (قطعی/محتمل/نامشخص).
- فایل‌های تغییرکرده و commit fix.
- نتیجهٔ audit/build/package/artifact/device test به‌صورت جدا.
- آیا failure جدید است یا regression تکراری.

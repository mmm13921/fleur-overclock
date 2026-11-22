# Kernel Project Knowledge Base

این پوشه مرجع مرکزی دانش پروژه است؛ از تاریخچهٔ اولیه تا مودم، دادهٔ برنامه‌ها، HMP، EEVDF، فایل‌سیستم، فرکانس‌ها و خطاهای CI. قبل از هر تغییر یا بیلد، اسناد مرتبط را بخوان و از تکرار خطاهای ثبت‌شده جلوگیری کن.

## قوانین اجباری

- هر بیلد باید گزارش مستقل در `builds/` داشته باشد؛ حتی اگر بیلد موفق باشد.
- برای هر خطا: run ID، branch، commit، مرحله، اولین خطای واقعی، علت ریشه‌ای، فایل/commit اصلاح و نتیجهٔ اجرای بعدی ثبت شود.
- وضعیت‌های Audit، compile، AnyKernel packaging، artifact upload، boot و device testing جدا هستند.
- هرگز فقط با موفقیت static audit ادعای build success نکن.
- قبل از استفاده از symbol/field/enum جدید در backport، وجود و امضای آن را در **سورس مقصد** بررسی کن.
- patcher را از نظر anchor و فایل C تولیدشده inspect کن؛ وجود substring در comment را وجود macro/function تلقی نکن.
- تغییرات مودم، storage، scheduler و DTB تا جای ممکن تفکیک و قابل rollback باشند.
- برای storage، حفظ user data، FBE/fscrypt، inline crypto، F2FS و deletion fix اجباری است. هیچ format، wipe یا پاک‌سازی داده انجام نشود.
- workaround برنامه (مثلاً reinstall) را به‌عنوان fix کرنل ثبت نکن.
- اطلاعات تأییدنشده باید صریحاً با «نامشخص/تأییدنشده» مشخص شوند.

## مشخصات و مرجع پروژه

- مخزن: https://github.com/mmm13921/fleur-overclock
- دستگاه: Redmi Note 11S 4G / fleur / MT6781 / Helio G96
- مرجع پایدار قبلی: Build 38 — https://github.com/mmm13921/fleur-overclock/releases/tag/meys-projectid-30-eevdf-modem-38
- Build 30: https://github.com/mmm13921/fleur-overclock/releases/tag/meys-projectid-30
- Build 49: https://github.com/mmm13921/fleur-overclock/releases/tag/scheduler-hmp-eas-hybrid-49
- شاخهٔ فعال EEVDF در سوابق: `meys-eevdf-618-porting`
- مبنای موردنظر کارهای آینده: Fleux V12؛ ورودی برخی workflowهای فعلی EEVDF هنوز V11 است و باید قبل از هر بیلد کنترل شود.
- Release credits: عبارت Based on Fleux و لینک https://github.com/daliboss/Fleux حفظ شود.

## راهنمای اسناد

| سند | موضوع |
|---|---|
| [تاریخچه جامع](history.md) | مسیر پروژه و تصمیم‌های مهم |
| [دستگاه و پلتفرم](device-platform.md) | مشخصات fleur، boot، DTB، CPU/GPU و سازگاری |
| [Build baselines](build-baselines.md) | Build 30، 38، 49 و نسخه‌های EEVDF |
| [مودم و DPMAIF](modem-dpmaif.md) | PM guard، تلاش‌های modem 4.14 و تست رادیو |
| [باگ داده و storage](storage-data.md) | Telegram، Recorder، FUSE، F2FS، Project ID و MediaProvider |
| [HMP/EAS/Hybrid](hmp-scheduler.md) | selector، topology و تنظیمات scheduler |
| [EEVDF 6.18](builds/eevdf-618.md) | بک‌پورت، خطاهای compile و بررسی معنایی |
| [خطاهای CI](builds/known-ci-failures.md) | AnyKernel و خطاهای عمومی workflow/build |

## ساختار پیشنهادی برای گزارش بیلد

`builds/build-<id>.md` شامل:
1. هدف، baseline و source ref
2. تغییرات دقیق و commitها
3. CI runها و نتیجهٔ جداگانهٔ audit/compile/package/artifact
4. اولین خطای واقعی و root cause
5. fix و نتیجهٔ rerun
6. runtime/device test و لاگ‌ها
7. باگ‌های باز و مواردی که نباید تکرار شوند

## وضعیت دانش

این آرشیو بر اساس سوابق موجود در گفتگوها، release notes، شاخه‌ها و runهای قابل بازیابی نوشته شده است. برای بعضی buildهای قدیمی log کامل یا commit دقیق در دسترس نیست؛ آن موارد به‌عنوان تاریخچهٔ گزارش‌شده یا علت نامشخص ثبت شده‌اند، نه حقیقت اثبات‌شده.

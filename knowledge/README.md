# Kernel Project Knowledge Base

این پوشه مرجع مرکزی و دائمی دانش پروژه MEYS VX برای Redmi Note 11S 4G / fleur است. تاریخچه از شروع پروژه، تصمیم‌ها، baselineها، patchها، باگ‌های مودم و دیتای برنامه‌ها، HMP/EAS، EEVDF، فایل‌سیستم، DTB، عملکرد و تمام خطاهای شناخته‌شده باید اینجا نگهداری شود.

## قانون اصلی قبل از هر تغییر یا بیلد

**ابتدا [چک‌لیست اجباری پیش از بیلد](preflight.md) را بخوان.** سپس اسناد حوزه‌ای را مرور کن، خطاهای قبلی را جست‌وجو کن و source ref/commit واقعی را بررسی کن. هیچ patch یا workflow را صرفاً برای سبز شدن CI تکرار یا حدس نزن.

## قوانین غیرقابل‌چشم‌پوشی

- هر بیلد، حتی موفق، باید گزارش مستقل در `builds/` داشته باشد.
- هر خطا باید با run ID، URL، branch، commit SHA، workflow/job/step، اولین خطای واقعی، علت ریشه‌ای، فایل و commit اصلاح و نتیجهٔ rerun ثبت شود.
- وضعیت‌های source audit، patch generation، compile، AnyKernel packaging، artifact upload، boot و تست واقعی دستگاه جدا هستند.
- موفقیت audit یا compile به معنی ZIP سالم، بوت، پایداری مودم یا سلامت داده نیست.
- پیش از استفاده از symbol/field/enum جدید در backport، وجود و امضای آن را در سورس مقصد بررسی کن.
- patcher باید هم از نظر anchor و هم از نظر فایل C نهایی inspect شود؛ substring در comment، تعریف واقعی function/macro نیست.
- تغییرات modem، storage، scheduler، DTB و performance تا جای ممکن مستقل و قابل rollback باشند.
- برای storage، حفظ user data، FBE/fscrypt، inline crypto، F2FS و deletion fix الزامی است؛ هیچ format، wipe یا پاک‌سازی داده انجام نشود.
- workaround اپ (مانند reinstall) را fix کرنل ثبت نکن.
- هر ادعای تأییدنشده را با «نامشخص/تأییدنشده» برچسب بزن.
- baseline فقط با اعلام صریح کاربر مبنی بر stable شدن تغییر می‌کند؛ بیلد آزمایشی، ناموفق یا صرفاً CI-green مبنا را عوض نمی‌کند.
- مبنای سورس کارهای آینده Fleux V12 است؛ workflowهایی که هنوز V11 می‌گیرند باید پیش از اجرا اصلاح یا صریحاً به‌عنوان V11 ثبت شوند.
- Credits در release/readme باید عبارت Based on Fleux و لینک https://github.com/daliboss/Fleux را حفظ کند.

## مرجع پروژه و baseline

- مخزن: https://github.com/mmm13921/fleur-overclock
- دستگاه: Redmi Note 11S 4G / `fleur` / MT6781 / Helio G96
- Build 30: مرجع پایدار قبلی که در سوابق کاربر به‌عنوان baseline مهم Project ID/F2FS تعیین شده است.
- Build 38: انتشار تاریخی مهم با EEVDF اولیه و DPMAIF PM guard؛ این build پورت کامل EEVDF یا مودم 4.14 نیست.
- Build 49: انتشار Fleux V11 / Linux 4.19.325 با HMP/EAS/Hybrid؛ مشکل app-data را حل نکرد.
- قاعده: در صورت تعارض بین baselineهای تاریخی، آخرین build که کاربر صریحاً stable اعلام کرده ملاک است؛ release آزمایشی یا ناموفق جایگزین آن نمی‌شود.
- سورس توسعهٔ بعدی: Fleux V12، مگر درخواست صریح دیگر.

## راهنمای اسناد

| سند | موضوع |
|---|---|
| [تاریخچه جامع](history.md) | مسیر پروژه و تصمیم‌های مهم |
| [دستگاه و پلتفرم](device-platform.md) | مشخصات fleur، DTB، CPU/GPU و سازگاری |
| [Boot و AnyKernel](boot-anykernel.md) | boot image، DTB، خطای Unsupported device و انتشار ZIP |
| [Build baselines](build-baselines.md) | Build 30، 38، 49 و نسخه‌های EEVDF |
| [مودم و DPMAIF](modem-dpmaif.md) | مرجع رسمی 4.14.186، DPMAIF، PM و تست رادیو |
| [باگ داده و storage](storage-data.md) | Telegram، Recorder، FUSE، F2FS، Project ID و MediaProvider |
| [Screen Recorder EACCES](screenrecorder-eacces.md) | شکست open فایل موقت MediaStore و بررسی FUSE/مجوزها |
| [HMP/EAS/Hybrid](hmp-scheduler.md) | selector، topology و تنظیمات scheduler |
| [Performance و Touch/GPU](performance-touch-gpu.md) | COD، لمس، فرکانس‌ها، VM و app retention |
| [EEVDF 6.18](builds/eevdf-618.md) | بک‌پورت، خطاهای compile و بررسی معنایی |
| [خطاهای CI](builds/known-ci-failures.md) | خطاهای عمومی workflow/build |
| [فهرست خطاهای بیلد](builds/build-failures-index.md) | index خطاهای شناخته‌شده و root causeها |
| [Preflight](preflight.md) | روند اجباری قبل از هر build و جلوگیری از تکرار خطا |

## قالب گزارش هر بیلد

`builds/build-<id>.md` باید شامل baseline/source ref، هدف، تغییرات و commitها، workflow/run IDs، نتایج مستقل audit/compile/package/artifact، خطاها و root cause، fix/rerun، تست دستگاه و باگ‌های باز باشد.

## وضعیت آرشیو

این دانش از گفتگوها، release notes، branch names و سوابق قابل بازیابی GitHub گردآوری شده است. هر جا log کامل یا commit دقیق موجود نبوده، مورد به‌عنوان گزارش تاریخی یا علت نامشخص ثبت می‌شود. این آرشیو باید در هر بیلد جدید به‌روزرسانی شود، نه اینکه فقط یک بار نوشته شود.

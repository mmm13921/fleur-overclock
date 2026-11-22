# تاریخچهٔ جامع پروژه

این فایل نمای کلی مسیر پروژه از کارهای اولیه تا شاخه‌های فعلی است. جزئیات هر حوزه در فایل مستقل آمده است.

## خط زمانی و نقاط مرجع

- **پایه‌های اولیه fleur:** کار روی سورس‌های Xiaomi/Fleux و هدف‌گیری MT6781؛ در تاریخچهٔ قدیمی، سورس رسمی fleur با Linux 4.14.x و Fleux با Linux 4.19.325 دو شاخهٔ متمایز بوده‌اند. این دو را نباید بدون بررسی vendor modules/DTB/ROM با هم مخلوط کرد.
- **Build 30 / `meys-projectid-30`:** مرجع مهم Project ID و F2FS؛ شامل HMP/EAS/Hybrid selector با HMP به‌عنوان حالت پیش‌فرض و پیاده‌سازی native F2FS Project ID برگرفته از Xiaomi sea-t-oss 4.19.191.
- **Build 38 / `meys-projectid-30-eevdf-modem-38`:** انتشار مهم پروژه؛ تغییرات Build 30 در Project ID/F2FS را حفظ کرد و لایهٔ اولیهٔ EEVDF و guard مربوط به MT6781 DPMAIF PM را افزود.
- **Build 49 / `scheduler-hmp-eas-hybrid-49`:** انتشار MEYS VX V15 روی Fleux V11 / Linux 4.19.325؛ AnyKernel3 package و HMP/EAS/Hybrid work. وضعیت release آن «successful build — device testing required» ذکر شده؛ این عبارت به‌تنهایی اثبات تست کامل رادیو/پایداری نیست.
- **شاخه‌های EEVDF 6.18:** چند شاخهٔ آزمایشی برای انتقال تدریجی EEVDF؛ شاخهٔ فعال ثبت‌شده `meys-eevdf-618-porting` است. نسخهٔ ورودی CI در این مسیر Fleux V11 است، درحالی‌که ترجیح ثبت‌شده برای کارهای آتی استفاده از Fleux V12 است.
- **Storage / MediaProvider:** بررسی جداگانهٔ FUSE، F2FS Project ID و Android 13 MediaProvider؛ bridge مربوط به MediaProvider یک patch سمت userspace است، نه بخشی از ZIP کرنل.

## تصمیم‌های لازم‌الاجرا

1. Build 30 را به‌عنوان مرجع پایدار Project ID/F2FS حفظ کن؛ baseline نهایی فقط با اعلام صریح کاربر تغییر می‌کند.
2. سورس پایهٔ کارهای آینده Fleux V12 باشد، مگر درخواست صریح دیگر؛ هر workflow که هنوز V11 می‌گیرد باید این موضوع را آشکارا گزارش کند.
3. هر تغییر مودم، فایل‌سیستم، scheduler یا DTB باید مستقل و قابل ردیابی باشد.
4. ادعای «بیلد موفق»، «فلش‌شدنی»، «بوت‌شده» و «تست‌شده روی دستگاه» را از هم جدا کن.
5. برای تغییرات مرتبط با داده، FBE/fscrypt، inline crypto، F2FS، FUSE و Project ID، حفظ دادهٔ کاربر اولویت اجباری است؛ هرگز فرمت یا پاک‌سازی داده انجام نده.
6. برای هر release نام کوتاه مانند `meys-patched` و توضیح کوتاه ترجیح داده شده؛ در Credits عبارت Based on Fleux و لینک منبع حفظ شود.

## منابع و نقاط بازیابی

- Build 30: https://github.com/mmm13921/fleur-overclock/releases/tag/meys-projectid-30
- Build 38: https://github.com/mmm13921/fleur-overclock/releases/tag/meys-projectid-30-eevdf-modem-38
- Build 49: https://github.com/mmm13921/fleur-overclock/releases/tag/scheduler-hmp-eas-hybrid-49
- همهٔ Releaseها: https://github.com/mmm13921/fleur-overclock/releases
- شاخه‌ها: https://github.com/mmm13921/fleur-overclock/branches
- Fleux upstream: https://github.com/daliboss/Fleux
- Xiaomi kernel sources: https://github.com/MiCode/Xiaomi_Kernel_OpenSource

## تکمیل تاریخچه از گفتگوهای قدیمی‌تر تا 2026-11-23

### شاخه‌های اولیه و سورس‌ها
- پروژه بین سورس رسمی Xiaomi fleur با Linux 4.14.x و Fleux با Linux 4.19.325 حرکت کرده است. این دو درخت API، driver integration و DTB یکسان ندارند؛ cherry-pick یا جایگزینی driver باید موردی باشد.
- هدف نام محصول MEYS VX است. کاربر محیط توسعهٔ بدون PC محلی را گزارش کرده؛ workflowهای GitHub Actions و خروجی AnyKernel3 باید قابل استفاده باشند.
- ترجیح نهایی کاربر برای کارهای آینده: Fleux V12. هر workflow قدیمی که V11 یا source قدیمی‌تر را می‌گیرد باید پیش از build مشخص و اصلاح شود.

### مودم و آنتن‌دهی
- در 2026-11-22 کاربر خواست مسیر modem/radio از سورس رسمی fleur 4.14.186 بررسی و با Fleux تطبیق داده شود تا آنتن‌دهی قطع نشود.
- شاخهٔ پژوهشی `meys-vx-modem-4.14-port` و اسناد `modem/README.md`، `modem/fleur-4.14-reference.config`، `modem/PORT_STATUS.md` در سوابق ذکر شده‌اند؛ مرجع شامل ECCCI، MD6295، MD1 و C2K بوده است.
- به علت نبود سورس کامل/وابستگی‌های لازم در آن مرحله، full driver port و ZIP اصلاح‌شده تولید نشدند. اجرای جمع‌آوری log در MT Manager با `Bad system call` شکست خورد؛ علت محیط اجرا نامشخص ماند.
- پورت کورکورانهٔ DPMAIF 4.14 به مسیر syscore در Fleux 4.19 رد شد؛ ساختار PM این دو نسخه لزوماً یکسان نیست.

### Storage و دادهٔ برنامه‌ها
- Build 48 مشکل storage را حل نکرد. در سوابق، FUSE 4.14 در آن build پورت نشده بود؛ HMP V2 باید دست‌نخورده می‌ماند.
- Build 49 نیز باگ app-data را رفع نکرد. کاربر گفت Telegram پس از uninstall/reinstall درست شد، ولی Recorder و برخی برنامه‌ها همچنان مشکل داشتند. این reinstall فقط workaround برنامه است و اثبات fix کرنل نیست.
- علت قطعی هنوز از شواهد موجود استخراج نشده؛ مسیر private app data، FUSE/emulated storage، MediaProvider، SELinux/AppOps و F2FS/Project ID باید جدا بررسی شوند.

### HMP و boot patches
- Build 30 به‌عنوان baseline مهم Project ID/F2FS و HMP/EAS/Hybrid حفظ شود؛ baseline هرگز با build آزمایشی یا CI صرفاً سبز عوض نشود.
- کاربر برای Build 38 boot-patches خواست: sched-u32 min/max، vm.extfrag_threshold، حذف حداقل ondemand sampling_rate، cpu_capacity per-CPU و حذف سقف 1024، جدول‌های CPU/GPU/DTB. گزینه‌های sysctl-all، ged-all، cpuset-empty، swap-max و wm-max اعمال نشدند؛ حداقل فرکانس CPU به علت bootloop غیرفعال ماند.
- این patch list گزارش درخواست/تلاش است؛ قبل از استفاده باید با commit و سورس همان شاخه تطبیق داده شود.

### EEVDF و CI
- Build 14 با SHA `3db23a1ab1f880e436e8daad8a8a440426b229fb` در یک مرحله به‌عنوان EEVDF build موفق و AnyKernel3 package موفق گزارش شده؛ انتشار جدیدتر Build 14 شکست خورده و baseline نشد.
- شاخهٔ `meys-eevdf-baseline-test` run #1 با commit `8db50399b2` آماده‌سازی را آغاز کرد اما Cancelled شد؛ compile و ZIP نهایی تأیید نشدند.
- فهرست کامل‌تر خطاهای EEVDF در `builds/eevdf-618.md` ثبت شده است. compile/audit failures نباید به‌عنوان بیلد قابل فلش تلقی شوند.

### قاعدهٔ baseline نهایی
آخرین buildی که کاربر صریحاً stable اعلام کرده ملاک است. Build 30 به‌عنوان مرجع پایدار قبلی و Build 38 به‌عنوان انتشار تاریخی مهم حفظ شوند؛ اگر نام stable متفاوتی در گفتگوی بعدی تعیین شد، همان تصمیم صریح جدید اولویت دارد. سورس توسعهٔ بعدی Fleux V12 است.

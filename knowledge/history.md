# تاریخچهٔ جامع پروژه

این فایل نمای کلی مسیر پروژه از کارهای اولیه تا شاخه‌های فعلی است. جزئیات هر حوزه در فایل مستقل آمده است.

## خط زمانی و نقاط مرجع

- **پایه‌های اولیه fleur:** کار روی سورس‌های Xiaomi/Fleux و هدف‌گیری MT6781؛ در تاریخچهٔ قدیمی، سورس رسمی fleur با Linux 4.14.x و Fleux با Linux 4.19.325 دو شاخهٔ متمایز بوده‌اند. این دو را نباید بدون بررسی vendor modules/DTB/ROM با هم مخلوط کرد.
- **Build 30 / `meys-projectid-30`:** مرجع مهم Project ID و F2FS؛ شامل HMP/EAS/Hybrid selector با HMP به‌عنوان حالت پیش‌فرض و پیاده‌سازی native F2FS Project ID برگرفته از Xiaomi sea-t-oss 4.19.191.
- **Build 38 / `meys-projectid-30-eevdf-modem-38`:** مرجع پایدار قبلی پروژه و مبنای تغییرات بعدی طبق تصمیم کاربر. Build 38 تغییرات Build 30 در Project ID/F2FS را حفظ کرد و لایهٔ اولیهٔ EEVDF و guard مربوط به MT6781 DPMAIF PM را افزود.
- **Build 49 / `scheduler-hmp-eas-hybrid-49`:** انتشار MEYS VX V15 روی Fleux V11 / Linux 4.19.325؛ AnyKernel3 package و HMP/EAS/Hybrid work. وضعیت release آن «successful build — device testing required» ذکر شده؛ این عبارت به‌تنهایی اثبات تست کامل رادیو/پایداری نیست.
- **شاخه‌های EEVDF 6.18:** چند شاخهٔ آزمایشی برای انتقال تدریجی EEVDF؛ شاخهٔ فعال ثبت‌شده `meys-eevdf-618-porting` است. نسخهٔ ورودی CI در این مسیر Fleux V11 است، درحالی‌که ترجیح ثبت‌شده برای کارهای آتی استفاده از Fleux V12 است.
- **Storage / MediaProvider:** بررسی جداگانهٔ FUSE، F2FS Project ID و Android 13 MediaProvider؛ bridge مربوط به MediaProvider یک patch سمت userspace است، نه بخشی از ZIP کرنل.

## تصمیم‌های لازم‌الاجرا

1. Build 38 را مرجع پایدار قبلی حفظ کن؛ تغییرات جدید نباید بی‌دلیل lineage آن را پاک کنند.
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

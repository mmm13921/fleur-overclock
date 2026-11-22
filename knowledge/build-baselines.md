# Build baselines و سوابق انتشار

## مرجع‌ها

| نام | نقش | جزئیات ثبت‌شده |
|---|---|---|
| Build 30 / `meys-projectid-30` | پایهٔ Project ID | HMP/EAS/Hybrid selector؛ HMP default؛ F2FS native Project ID backport از Xiaomi sea-t-oss 4.19.191 |
| Build 38 / `meys-projectid-30-eevdf-modem-38` | انتشار مهم و مرجع میانی | حفظ Build 30 filesystem/F2FS/Project ID؛ EEVDF semantic layer اولیه؛ DPMAIF PM guard |
| Build 49 / `scheduler-hmp-eas-hybrid-49` | انتشار MEYS VX V15 | Fleux V11، Linux 4.19.325، AnyKernel3؛ نیازمند تست دستگاه |
| EEVDF patch releases `meys-patched-6/8/16/17/18` | توسعهٔ آزمایشی EEVDF | بر پایهٔ Build 38؛ CPU/GPU/DTB, VM, ondemand, cpu_capacity patches؛ در نسخه‌های اولیه delayed dequeue/DELAY_ZERO ناقص بوده است |

## نکات مهم

- Build 30 مرجع پایدار Project ID/F2FS است؛ baseline فقط با اعلام صریح کاربر مبنی بر stable شدن build جدید تغییر می‌کند.
- Build 38 release notes صریحاً می‌گوید EEVDF `DELAY_DEQUEUE` و `DELAY_ZERO` هنوز وجود نداشتند؛ پس آن build «پورت کامل EEVDF 6.18» نیست.
- Build 38 DPMAIF change یک PM safety guard است، نه full modem driver port.
- Android 13 MediaProvider bridge یک asset جداگانه است و داخل kernel ZIP نیست.
- Release Build 38: https://github.com/mmm13921/fleur-overclock/releases/tag/meys-projectid-30-eevdf-modem-38
- Build 30: https://github.com/mmm13921/fleur-overclock/releases/tag/meys-projectid-30
- Build 49: https://github.com/mmm13921/fleur-overclock/releases/tag/scheduler-hmp-eas-hybrid-49

## جزئیات تاریخی تکمیلی و قواعد baseline

- Build 14 موفق EEVDF که در سوابق گزارش شد: SHA `3db23a1ab1f880e436e8daad8a8a440426b229fb`؛ AnyKernel3 output موفق بود. اجرای انتشار جدیدتر Build 14 شکست خورد.
- Build 48 مشکل storage را رفع نکرد؛ FUSE 4.14 در آن پورت نشده بود.
- Build 49 مشکل app-data را رفع نکرد؛ HMP/EAS/Hybrid حفظ شد و storage fix اثبات نشد.
- Build 38 release شامل DPMAIF PM guard و EEVDF semantic layer اولیه بود، نه full modem 4.14 یا complete Linux 6.18 EEVDF.
- Run #1 در شاخهٔ `meys-eevdf-baseline-test` با commit کوتاه‌شدهٔ `8db50399b2` لغو شد؛ compile و AnyKernel artifact نهایی تأیید نشد.

**قانون baseline:** فقط buildی که کاربر صریحاً stable اعلام کند جایگزین baseline قبلی می‌شود. Build 30 به‌عنوان مرجع پایدار Project ID/F2FS در تاریخچه حفظ شود؛ Build 38 و Build 49 اسناد انتشارهای مهم‌اند. در صورت اعلام صریح stable جدید از سوی کاربر، تاریخچه را append کن و سوابق قبلی را پاک نکن.

**قانون سورس:** برای کارهای جدید Fleux V12؛ هر workflowی که Fleux V11 می‌گیرد باید قبل از build کنترل شود و نباید بدون اطلاع کاربر مبنای کار جدید باشد.

# Build baselines و سوابق انتشار

## مرجع‌ها

| نام | نقش | جزئیات ثبت‌شده |
|---|---|---|
| Build 30 / `meys-projectid-30` | پایهٔ Project ID | HMP/EAS/Hybrid selector؛ HMP default؛ F2FS native Project ID backport از Xiaomi sea-t-oss 4.19.191 |
| Build 38 / `meys-projectid-30-eevdf-modem-38` | مرجع پایدار قبلی برای تغییرات | حفظ Build 30 filesystem/F2FS/Project ID؛ EEVDF semantic layer اولیه؛ DPMAIF PM guard |
| Build 49 / `scheduler-hmp-eas-hybrid-49` | انتشار MEYS VX V15 | Fleux V11، Linux 4.19.325، AnyKernel3؛ نیازمند تست دستگاه |
| EEVDF patch releases `meys-patched-6/8/16/17/18` | توسعهٔ آزمایشی EEVDF | بر پایهٔ Build 38؛ CPU/GPU/DTB, VM, ondemand, cpu_capacity patches؛ در نسخه‌های اولیه delayed dequeue/DELAY_ZERO ناقص بوده است |

## نکات مهم

- Build 38 مرجع پایدار قبلی تعیین‌شده از سوی کاربر است؛ آن را با Build 49 یا شاخهٔ جاری EEVDF اشتباه نگیر.
- Build 49 به‌عنوان انتشار «stable» نام‌گذاری شده بود اما notes آن نیز device testing required را ذکر می‌کند. برای اطمینان از boot و data behavior باید شواهد تست واقعی وجود داشته باشد.
- Build 38 release notes صریحاً می‌گوید EEVDF `DELAY_DEQUEUE` و `DELAY_ZERO` هنوز وجود نداشتند؛ پس آن build «پورت کامل EEVDF 6.18» نیست.
- Build 38 DPMAIF change یک PM safety guard است، نه full modem driver port.
- Android 13 MediaProvider bridge یک asset جداگانه است و داخل kernel ZIP نیست.
- Release Build 38: https://github.com/mmm13921/fleur-overclock/releases/tag/meys-projectid-30-eevdf-modem-38
- Build 30: https://github.com/mmm13921/fleur-overclock/releases/tag/meys-projectid-30
- Build 49: https://github.com/mmm13921/fleur-overclock/releases/tag/scheduler-hmp-eas-hybrid-49

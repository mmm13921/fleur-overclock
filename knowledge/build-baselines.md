

## جزئیات تاریخی تکمیلی و قواعد baseline

- Build 14 موفق EEVDF که در سوابق گزارش شد: SHA `3db23a1ab1f880e436e8daad8a8a440426b229fb`؛ AnyKernel3 output موفق بود. اجرای انتشار جدیدتر Build 14 شکست خورد و نباید با موفقیت قبلی اشتباه شود.
- Build 48 مشکل storage را رفع نکرد؛ FUSE 4.14 در آن پورت نشده بود.
- Build 49 مشکل app-data را رفع نکرد؛ HMP/EAS/Hybrid حفظ شد و storage fix اثبات نشد.
- Build 38 release شامل DPMAIF PM guard و EEVDF semantic layer اولیه بود، نه full modem 4.14 یا complete Linux 6.18 EEVDF.
- Run #1 در شاخهٔ `meys-eevdf-baseline-test` با commit کوتاه‌شدهٔ `8db50399b2` لغو شد؛ compile و AnyKernel artifact نهایی تأیید نشد.

**قانون baseline:** فقط buildی که کاربر صریحاً stable اعلام کند جایگزین baseline قبلی می‌شود. Build 30 به‌عنوان مرجع پایدار Project ID/F2FS در تاریخچه حفظ شود؛ Build 38 و Build 49 اسناد انتشارهای مهم‌اند، نه اینکه خودکار baseline جدید محسوب شوند. در صورت اعلام صریح stable جدید از سوی کاربر، تاریخچه را append کن و سوابق قبلی را پاک نکن.

**قانون سورس:** برای کارهای جدید Fleux V12؛ هر workflowی که Fleux V11 می‌گیرد باید قبل از build کنترل شود و نباید بدون اطلاع کاربر مبنای کار جدید باشد.

# مودم و MediaTek DPMAIF — تاریخچه و وضعیت

## Build 38: تغییر مودم دقیقاً چه بود؟

Release `meys-projectid-30-eevdf-modem-38` شامل **MT6781 DPMAIF syscore power-management resume safety guard** است.

این تغییر:
- یک محافظ PM برای مسیر resume مربوط به DPMAIF است.
- **پورت کامل درایور مودم Linux 4.14 به Fleux 4.19 نیست.**
- نباید در changelog یا گزارش‌ها به‌عنوان «پورت کامل مودم» معرفی شود.
- CI و بسته‌بندی Build 38 موفق اعلام شده بود؛ اما پایداری رادیو، تماس، دیتا، suspend/resume و تست میدانی مستقل از موفقیت build هستند.

Release: https://github.com/mmm13921/fleur-overclock/releases/tag/meys-projectid-30-eevdf-modem-38

## کارهای بعدی مودم

در شاخه‌های بعدی نام‌هایی مانند موارد زیر دیده شده‌اند:
- `meys-projectid-30-eevdf-modem`
- `meys-vx-v15-modem414-eevdf618`
- `meys-vx-v17-build30-eevdf618-modemaudit`
- `meys-build30-modem-eevdf-no-filesystem`

وجود نام «modem414» یا «modemaudit» به‌تنهایی ثابت نمی‌کند که تمام درایورهای مودم 4.14 منتقل شده‌اند یا runtime درست کار می‌کند. برای هر ادعا باید diff واقعی، فهرست فایل‌ها، وابستگی‌های PM/clock/IRQ/IOMMU/DPMAIF و تست دستگاه بررسی شود.

## چک‌لیست رگرسیون مودم

هر بیلدی که به DPMAIF، modem, PM, clock, regulator, interconnect یا IRQ دست می‌زند باید موارد زیر را ثبت کند:
1. تشخیص سیم‌کارت و registration شبکه.
2. تماس ورودی/خروجی و SMS در صورت پشتیبانی.
3. دیتای موبایل و جابه‌جایی بین شبکه‌ها.
4. airplane mode روشن/خاموش و restart رادیو.
5. suspend/resume و screen-off طولانی.
6. reboot سرد و گرم.
7. لاگ‌های kernel/Radio/MTK در صورت بروز مشکل.

## خطاها و درس‌های تاریخی

- کاربر چندین بار گزارش کرده بود که اصلاحات مودم «کامل» به نظر نمی‌رسند؛ به همین دلیل لازم است قبل از هر ادعای fix، ممیزی کل مسیر مودم انجام شود، نه فقط وجود یک patch.
- چند بار CIهای ناموفق رخ داده و درخواست «اصلاح ریشه‌ای» مطرح شده است؛ هر خطا باید با run ID و commit دقیق در `knowledge/builds/` ثبت شود.
- در صورت شکست build، از بازگرداندن تغییرات filesystem یا data به‌صورت تصادفی برای حل خطای مودم خودداری شود؛ حوزه‌ها باید commitهای جدا یا حداقل patchهای تفکیک‌شده داشته باشند.

## وضعیت قطعیت

- DPMAIF PM guard در Build 38: در release notes ثبت‌شده.
- پورت کامل مودم 4.14: **تأیید نشده**.
- پایداری کامل شبکه و دیتای موبایل در همهٔ ROMها: **تأیید نشده**.



## مرجع تاریخی مودم رسمی fleur 4.14.186

در گفتگوهای 2026-11-22 کاربر خواست مسیر مودم و آنتن‌دهی از سورس رسمی fleur 4.14.186 بررسی و به Fleux تطبیق داده شود. خانواده/اجزای مرجع ثبت‌شده شامل موارد زیر هستند:
- ECCCI و رابط ارتباطی AP/MD
- MD6295 و مسیرهای MD1/C2K
- وابستگی‌های DPMAIF، IRQ، clock، regulator، IOMMU و power-management

در آن مرحله شاخهٔ پژوهشی `meys-vx-modem-4.14-port` و فایل‌های `modem/README.md`, `modem/fleur-4.14-reference.config`, `modem/PORT_STATUS.md` گزارش شدند. با این حال، به علت نبود سورس کامل/وابستگی‌های driver در checkout، **full modem driver port انجام نشد و ZIP فلش اصلاح‌شده تولید نشد**. وجود branch یا config reference را با port کامل اشتباه نگیر.

جمع‌آوری log مودم در MT Manager با `Bad system call` شکست خورد؛ علت دقیق در سوابق نامشخص است. این failure مدرک خرابی مودم یا kernel نیست.

## تاریخچهٔ تصمیم DPMAIF

- در Build 38 فقط MT6781 DPMAIF syscore PM resume safety guard ثبت شده است.
- DPMAIF 4.14 و مسیر syscore در Fleux 4.19 نباید کورکورانه با هم ادغام شوند؛ ابتدا call graph، registration order، PM callback، IRQ/clock ownership و error paths در دو سورس مقایسه شوند.
- شاخه‌هایی با نام `modem414` یا `modemaudit` تنها نام شاخه‌اند و دلیل تکمیل port نیستند.
- قبل از تغییر، baseline رادیو و logهای kernel/Radio/MTK ثبت شوند. هر تغییر modem باید جدا از EEVDF و filesystem commit شود.

## تفکیک وضعیت‌ها

| مورد | وضعیت تاریخی |
|---|---|
| DPMAIF syscore PM guard در Build 38 | در release notes ثبت شده؛ runtime کامل تأیید نشده |
| مرجع رسمی fleur 4.14.186 و ECCCI/MD6295/MD1/C2K | در گفتگو و شاخهٔ پژوهشی ثبت شده |
| Full driver port 4.14 به Fleux V12 | انجام‌شده نیست / تأیید نشده |
| آنتن‌دهی، تماس و mobile data بعد از port کامل | تست دستگاه موجود نیست |
| log collection با MT Manager | با `Bad system call` شکست؛ علت نامشخص |

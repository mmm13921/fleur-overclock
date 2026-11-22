# Boot image، DTB، AnyKernel3 و خطاهای فلش

## Boot image و DTB

- سوابق پروژه شامل boot image با header v2 است.
- در پورت‌های قبلی تأکید شده DTB در بخش صحیح boot image پچ شود؛ append کردن کورکورانهٔ DTB به `Image.gz-dtb` می‌تواند قالب اشتباه تولید کند.
- ramdisk، cmdline، AVB metadata و header باید تا حد امکان بدون تغییر بمانند.
- قبل از انتشار، kernel image و DTB و gzip مستقل validate شوند.
- gzip deterministic با `gzip -9n` استفاده شده است.
- خروجی باید با ابزار unpack/pack مناسب header همان ROM کنترل شود؛ صرفاً اندازهٔ فایل یا gzip test کافی نیست.

## AnyKernel3

- هدف معمول انتشار، AnyKernel3 ZIP قابل فلش است.
- در سابقه خطای `Unsupported device Aborting` رخ داده است.
- device names گزارش‌شده در config: `fleur`, `miel` و گاهی `missi`. هر سه را بدون تطبیق props و دستگاه واقعی در whitelist قرار نده.
- قبل از release، `device.name1`, `device.name2`, `device.name3`, slot behavior و مسیر نصب boot image را بازبینی کن.
- artifact باید پس از build واقعاً وجود داشته باشد، ZIP سالم باشد، updater script با device مطابقت داشته باشد و checksum تولید شود.

## نام‌گذاری و release

- نام کوتاه و ساده مانند `meys-patched` ترجیح داده شده.
- release notes کوتاه باشند.
- بخش credits باید بگوید Based on Fleux و لینک upstream را نگه دارد: https://github.com/daliboss/Fleux
- «CI build passed» با «روی دستگاه بوت شد» فرق دارد. release نباید وضعیت تست نشده را stable/boot-tested جلوه دهد.

## منابع

- AnyKernel3: https://github.com/osm0sis/AnyKernel3
- Xiaomi kernel sources: https://github.com/MiCode/Xiaomi_Kernel_OpenSource
- Fleux: https://github.com/daliboss/Fleux

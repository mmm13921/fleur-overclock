

## تکمیل تاریخچهٔ باگ دیتا و برنامه‌ها

### رفتار گزارش‌شدهٔ اپ‌ها
- Telegram در یک مرحله مشکل داشت؛ پس از حذف و نصب مجدد درست شد. این فقط نشان می‌دهد state/cache یا نصب اپ ممکن است دخیل بوده باشد؛ علت کرنلی را اثبات نمی‌کند.
- پس از آن کاربر گفت بعضی برنامه‌ها از جمله Recorder هنوز درست کار نمی‌کنند. دقیقاً مشخص نشده آیا فایل ایجاد نمی‌شود، نوشتن fail می‌شود، یا فایل ایجاد شده ولی در MediaStore/UI نمایش داده نمی‌شود.
- Build 48 و Build 49 مشکل storage/app-data را حل نکردند؛ پس هر backport یا patch قبلی نباید به‌عنوان fix قطعی معرفی شود.

### Build 49 و Project ID
- Build 49 شامل `project_quota` / `extra_attr` feature exposure، `CONFIG_QUOTA=y` و F2FS/XATTR بود؛ با این حال mountهای مشاهده‌شده `prjquota` نداشتند.
- Build 30/38 Project ID inode persistence، quota transfer و project inheritance را از Xiaomi sea-t-oss 4.19.191 حفظ می‌کنند.
- project quota واقعی به پشتیبانی on-disk سازگار `EXTRA_ATTR` و `PRJQUOTA` و mount/runtime configuration درست نیاز دارد. sysfs feature flag به‌تنهایی کافی نیست.

### FUSE backport — تصمیم محافظه‌کارانه
- کاربر گفت اگر Build 49 storage را حل نکرد، FUSE 4.14 بررسی/بک‌پورت شود؛ Build 49 نیز مشکل را حل نکرد.
- در سوابق فنی، FUSE stock 4.14.186 protocol minor 26 و Fleux 4.19.325 minor 31 به همراه passthrough دارد. بنابراین جایگزینی کامل FUSE جدیدتر با کد قدیمی 4.14 می‌تواند regression و حذف قابلیت ایجاد کند.
- قبل از هر تصمیم FUSE، لاگ mount/F2FS، dmesg و logcat برای FUSE، fscrypt، project/quota و EACCES/EIO/ENOSPC جمع‌آوری شود. HMP V2 نباید ناخواسته تغییر کند.
- Android 13 MediaProvider Project ID ioctl bridge یک patch userspace مستقل است؛ build کامل MediaProvider و validation روی ROM هدف لازم است و داخل kernel ZIP نیست.

### چک‌لیست اپ‌های رگرسیون
حداقل Telegram، Recorder، Camera/Media, Downloads و اپ‌های scoped-storage باید روی baseline و build جدید با مسیر ذخیره‌سازی یکسان تست شوند. فایل باید با shell/root بررسی شود: آیا ایجاد شده؟ اندازه تغییر می‌کند؟ owner و SELinux context چیست؟ سپس MediaStore visibility جدا بررسی شود.

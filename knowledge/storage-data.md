# باگ دادهٔ برنامه‌ها، FUSE، F2FS و Project ID

این بخش برای جلوگیری از تکرار regressions مرتبط با ذخیره‌سازی و دادهٔ برنامه‌هاست. اصل غیرقابل‌مذاکره: **هیچ دادهٔ کاربر پاک، فرمت یا بازسازی نشود.**

## گزارش مشکل

کاربر گزارش کرده بود برخی برنامه‌ها با دسترسی/ذخیره‌سازی داده مشکل دارند؛ Telegram در یک مقطع مشکل داشت و پس از حذف و نصب مجدد درست شد، اما برنامه‌هایی مانند Recorder همچنان مشکوک بودند. رفتار Recorder دقیقاً مشخص نشده بود: هنوز معلوم نیست ضبط انجام نمی‌شود یا فایل ذخیره می‌شود اما index/visibility آن مشکل دارد. این دو حالت باید جداگانه تشخیص داده شوند.

## تفکیک لایه‌ها

- `/data` روی F2FS است.
- `/storage/emulated` از FUSE عبور می‌کند.
- در خروجی mountهای گزارش‌شده، `/Android/data` و `/Android/obb` مستقیم روی F2FS دیده شده‌اند.
- `/data/user/0/<package>` دادهٔ خصوصی اپ است و با FUSE مربوط به shared/emulated storage یکی نیست.
- خطای برنامه ممکن است از MediaProvider/MediaStore، permission/AppOps/SELinux، FUSE, F2FS, quota/project ID یا خود اپ باشد. بدون logcat و تفکیک مسیر، علت را به کرنل نسبت نده.

## بررسی‌های قبلی

- dmesg و mount outputهای گزارش‌شده fsck/mount موفق را نشان می‌دادند؛ خطاهای صریح FUSE/F2FS/EIO/ENOSPC/project در نمونه‌های بررسی‌شده مشاهده نشدند.
- تنها SELinux cgroup-quota denials در لاگ‌های ذکرشده گزارش شده بود؛ این به‌تنهایی اثبات علت خرابی Recorder یا همهٔ اپ‌ها نیست.
- Build 48 مشکل را حل نکرد؛ در آن FUSE قدیمی 4.14 port نشده بود و تغییرات عمدتاً شامل F2FS 4.19.191 و legacy remount بود.
- Build 49 نیز مشکل app-data را برطرف نکرد.
- Build 49 دارای `project_quota`/`extra_attr` sysfs featureها و `CONFIG_QUOTA=y` و F2FS/XATTR بود؛ اما mountهای مشاهده‌شده `prjquota` نداشتند. نبودن `prjquota` به‌تنهایی اثبات نمی‌کند ioctl پروژه کار نمی‌کند یا کار می‌کند.
- Build 30/38 شامل backport بومی F2FS Project ID از Xiaomi sea-t-oss 4.19.191 بود: inode project-ID persistence، quota transfer و project inheritance. استفادهٔ واقعی از project quota به ویژگی‌های on-disk سازگار `EXTRA_ATTR` و `PRJQUOTA` نیاز دارد.

## FUSE و Android 13 MediaProvider

- سورس stock Xiaomi fleur-s-oss گزارش‌شده Linux 4.14.186، FUSE protocol minor 26 دارد.
- Fleux V11 / 4.19.325 دارای FUSE protocol minor 31 و قابلیت‌های بیشتری از جمله passthrough است.
- در Fleux V11 فایل `fs/fuse/passthrough.c` و UAPIهای `FUSE_PASSTHROUGH` و `FUSE_DEV_IOC_PASSTHROUGH_OPEN` وجود دارند.
- بنابراین جایگزینی کامل FUSE 4.19 با درخت قدیمی 4.14 توصیه نمی‌شود؛ ممکن است قابلیت‌های جدیدتر را حذف کند.
- Release Build 38 یک Android 13 MediaProvider FUSE Project ID ioctl bridge را به‌صورت patch جداگانه ارائه کرده بود. این patch userspace است، در ZIP کرنل قرار ندارد و بدون build کامل MediaProvider و validation روی ROM هدف، fix آمادهٔ نصب محسوب نمی‌شود.
- workflowهای بعدی نیز patchهای `research/android13-mediaprovider` و audit مربوط را دارند؛ این bridge نباید با kernel driver اشتباه گرفته شود.

## فایل‌ها/اسکریپت‌های مرتبط در شاخه‌های کاری

- `scripts/apply_official_419191_fs_mount.py`
- `scripts/apply_f2fs_projectid_compat.py`
- `scripts/audit_android_storage.py`
- `scripts/configure_hyperos_fs.sh`
- `scripts/configure_cgroup_v2.sh`
- `research/android13-mediaprovider/README.md`
- `research/android13-mediaprovider/apply_projectid_ioctl_bridge.py`

این مسیرها در شاخهٔ کاری ثبت شده‌اند؛ قبل از استفاده روی main یا هر شاخهٔ دیگر، وجود و محتوای دقیق آن‌ها را در همان ref بررسی کن.

## پروتکل عیب‌یابی اجباری

1. تعیین کن اپ واقعاً نمی‌تواند بنویسد یا فایل ایجاد شده ولی در MediaStore/گالری/Recorder UI دیده نمی‌شود.
2. مسیر واقعی خروجی را بررسی کن: private app data، `/storage/emulated/0/...`، یا `/Android/data`.
3. هنگام بازتولید مشکل، logcat فیلترشده برای MediaProvider, FUSE, vold, app, AppOps و SELinux بگیر.
4. `dmesg` را برای FUSE/F2FS/crypto/I/O/quota/project errors بررسی کن.
5. mount options و feature flags واقعی را ثبت کن؛ فقط sysfs flag را معادل فعال بودن quota روی mount ندان.
6. بررسی کن فایل با shell/root وجود دارد، اندازه‌اش تغییر می‌کند و مالکیت/SELinux context درست است.
7. فقط پس از یافتن علت، patch محدود و قابل rollback انجام بده؛ FBE/fscrypt، inline crypto، F2FS و deletion fix را حفظ کن.
8. پس از patch، اپ‌های Recorder، Telegram، camera/media, downloads و چند اپ با scoped storage را تست کن؛ نصب مجدد اپ workaround است، نه اثبات fix کرنل.

## وضعیت قطعیت

- Project ID F2FS در Build 30/38: در release notes ثبت شده.
- مشکل عمومی app-data با FUSE/F2FS حل شده: **خیر؛ شواهد موجود حل کامل را ثابت نمی‌کنند**.
- علت دقیق مشکل Recorder: **نامشخص**.
- جایگزینی کامل FUSE 4.14 به‌جای 4.19: **انجام نشود مگر دلیل فنی و بررسی regression وجود داشته باشد**.

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

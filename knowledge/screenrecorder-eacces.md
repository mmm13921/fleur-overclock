# Screen Recorder — EACCES در ایجاد فایل موقت

## نتیجهٔ لاگ واقعی

منبع: `debug/telegram_debug_logcat.txt`، ضبط 2026-11-24، حدود 00:38:29.

ترتیب رخدادها:
1. `c2.mtk.avc.encoder` با موفقیت configure و start می‌شود؛ `C2MtkVenc` نیز start موفق دارد.
2. `StableScreenRecorderLegacy` برای MediaStore یک URI و نام فایل موقت می‌سازد:
   `/storage/emulated/0/DCIM/ScreenRecorder/.Screenrecorder-2026-11-24-00-38-29-363.mp4`
3. بازکردن فایل از مسیر MediaStore با `FileNotFoundException: open failed: EACCES (Permission denied)` شکست می‌خورد.
4. مسیر fallback و ساخت MediaMuxer سنتی نیز با همان EACCES شکست می‌خورد.
5. سپس کد ScreenRecorder به `NullPointerException` در مسیر recording می‌رسد و `miui.screenrecorder.record.fail` ارسال می‌شود.

بنابراین encoder/codec شروع می‌شود؛ شکست قبل از نوشتن خروجی MP4 و در دسترسی به فایل موقت رخ می‌دهد. خطاهای بعدی MediaCodec و NPE پیامد توقف‌اند، نه علت اولیه.

## تفکیک kernel از userspace

- در سورس Fleux V11، `fuse_permission()` از `fuse_allow_current_process()` استفاده می‌کند. اگر mount فاقد `allow_other` باشد، UID متفاوت از mount owner می‌تواند `-EACCES` بگیرد.
- در سورس رسمی Xiaomi fleur 4.14 نیز همین مدل دسترسی وجود دارد؛ پس جایگزینی کورکورانه FUSE 4.14 این شرط را برطرف نمی‌کند.
- در Fleux V11، شرط `allow_other` علاوه بر آن `current_in_userns(fc->user_ns)` را می‌سنجد. این تفاوت فقط وقتی مهم است که mount و process در user namespaceهای متفاوت باشند؛ لاگ موجود این وضعیت را اثبات نمی‌کند.
- در لاگ dmesg موجود، denial متناظر با مسیر ScreenRecorder یا خطای F2FS/FUSE با EIO/ENOSPC ثبت نشده است. AVC مربوط به `.screenrecorder` فقط خواندن `qemu_hw_prop` را رد می‌کند و به مسیر فایل مربوط نیست.
- چون خطا در مرحلهٔ open است، پل ioctl مربوط به `FS_IOC_FSSETXATTR` در MediaProvider به‌تنهایی توضیح این EACCES نیست؛ ioctl پس از بازشدن فایل قابل اجراست.

## موارد لازم برای اثبات علت نهایی

بدون تغییر داده یا دورزدن کنترل دسترسی، این موارد باید روی همان build و ROM ثبت شوند:
- mount options واقعی `/mnt/user/0/emulated` و `/storage/emulated`، مخصوصاً وجود `allow_other` و `default_permissions`.
- owner، group، mode و SELinux context مسیرهای `/data/media/0/DCIM` و `/data/media/0/DCIM/ScreenRecorder`.
- خطاهای MediaProvider/FuseDaemon هم‌زمان با درخواست بازکردن URI.
- نتیجهٔ بازکردن یک فایل آزمایشی غیرمخفی در همان پوشه با همان UID، برای تفکیک مشکل dotfile از مجوز پوشه.

دستورهای read-only برای جمع‌آوری:
```sh
echo "=== FUSE MOUNTS ==="
grep -E '(/mnt/user/0/emulated|/storage/emulated)' /proc/self/mountinfo
echo "=== DIRECTORY METADATA ==="
ls -ldnZ /data/media/0/DCIM /data/media/0/DCIM/ScreenRecorder
stat -c '%A %a %u:%g %n' /data/media/0/DCIM /data/media/0/DCIM/ScreenRecorder
echo "=== SELINUX ==="
getenforce
echo "=== RELEVANT LOGS ==="
dmesg | grep -iE 'fuse|f2fs|screenrecorder|avc: denied|EACCES|EIO|ENOSPC' | tail -n 200
logcat -b all -d -v threadtime | grep -iE 'MediaProvider|FuseDaemon|ScreenRecorder|EACCES|permission denied' | tail -n 300
```

## تصمیم patch

فعلاً هیچ bypass برای `fuse_allow_current_process` و هیچ تغییر permission/SELinux سراسری اعمال نشود. چنین تغییری می‌تواند جداسازی دسترسی کاربران به emulated storage را تضعیف کند. اگر mount options یا metadata نادرست باشند، اصلاح باید در مسیر mount/MediaProvider/ROM انجام شود؛ اگر FUSE daemon مجوز را درست صادر کند ولی kernel رد کند، آن‌وقت patch محدود و قابل rollback با trace اثبات‌شده بررسی می‌شود.

## وضعیت

- MediaCodec start: موفق در لاگ.
- MediaStore/FUSE open: شکست با EACCES.
- علت دقیق بین mount option، directory metadata و MediaProvider hidden-temp-file policy: هنوز نیازمند دادهٔ mount/runtime است.
- kernel-only fix تأییدشده: فعلاً وجود ندارد.

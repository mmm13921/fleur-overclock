# Mandatory Build Preflight — جلوگیری از تکرار خطا

این سند قبل از **هر** بیلد و هر backport باید خوانده و تیک‌خورده شود. هدف آن جلوگیری از تکرار خطاهای شناخته‌شده و حفظ تغییرات تأییدشده است.

## 1. تثبیت baseline و سورس

- [ ] آخرین build که کاربر صریحاً stable اعلام کرده را پیدا کن؛ هیچ build آزمایشی/ناموفق را baseline نکن.
- [ ] برای کارهای آینده از Fleux V12 استفاده کن. اگر workflow هنوز V11 را clone می‌کند، قبل از build آن را اصلاح کن یا mismatch را آشکارا گزارش بده.
- [ ] branch، commit SHA، tag، kernel version و source URL را ثبت کن.
- [ ] تغییرات را نسبت به baseline پایدار مقایسه کن؛ فایل‌ها/patchهای تأییدشده را بی‌دلیل overwrite یا حذف نکن.
- [ ] قبل از ساخت workflow جدید، workflowهای موجود را بررسی کن؛ jobهای تکراری نساز و فقط یک مسیر build مرجع نگه دار.

## 2. جست‌وجوی دانش پیشین

- [ ] `knowledge/builds/build-failures-index.md` و `known-ci-failures.md` را بخوان.
- [ ] اگر EEVDF تغییر می‌کند، `knowledge/builds/eevdf-618.md` و تمام patcher/auditهای مربوط را بخوان.
- [ ] اگر modem/DPMAIF تغییر می‌کند، `knowledge/modem-dpmaif.md` را بخوان.
- [ ] اگر app data/storage/FUSE/F2FS تغییر می‌کند، `knowledge/storage-data.md` را بخوان.
- [ ] اگر HMP/EAS/Hybrid تغییر می‌کند، `knowledge/hmp-scheduler.md` را بخوان.
- [ ] اگر boot/DTB/AnyKernel تغییر می‌کند، `knowledge/boot-anykernel.md` را بخوان.

## 3. قوانین backport و patcher

- [ ] هر symbol، struct field، enum، callback و helper را در **سورس مقصد** پیدا کن؛ وجود آن در Linux 6.18 یا سورس upstream به‌تنهایی کافی نیست.
- [ ] ترتیب declaration/definition و prototypeها را کنترل کن.
- [ ] هیچ API نسخهٔ جدید را بدون adapter/compat layer به کرنل 4.19 وارد نکن.
- [ ] patcher باید fail-fast باشد: تعداد anchorهای مورد انتظار را دقیق assert کند و در صورت نبودن/تکرار anchor متوقف شود.
- [ ] جست‌وجوی substring داخل comment را به‌عنوان وجود macro/function/guard نپذیر.
- [ ] پس از patch، فایل C/headers تولیدشده را بازبینی کن؛ صرف موفقیت Python یا static audit کافی نیست.
- [ ] patcher و audit باید دقیقاً یک رفتار/guard را assert کنند؛ assertionهای قدیمی را بعد از تغییر patcher اصلاح کن.
- [ ] از حذف guard، خاموش‌کردن warning یا تغییر بی‌ضابطهٔ منطق برای سبز شدن CI خودداری کن.

## 4. حوزه‌های حساس

### Modem / DPMAIF
- DPMAIF syscore PM guard را با full modem 4.14 port اشتباه نگیر.
- سورس مرجع رسمی fleur 4.14.186، ECCCI/MD6295/MD1/C2K و وابستگی‌های IRQ/clock/regulator/IOMMU/PM را قبل از هر port کامل بررسی کن.
- تغییر مودم باید مستقل باشد و تست SIM registration، تماس، SMS، mobile data، airplane toggle، suspend/resume و reboot داشته باشد.

### App data / storage
- هیچ format/wipe/data cleanup انجام نده.
- FBE/fscrypt، inline crypto، F2FS، FUSE و deletion fix را حفظ کن.
- Telegram reinstall شدن را fix کرنل تلقی نکن؛ Recorder و MediaProvider را جداگانه بررسی کن.
- مسیر private app data را از emulated storage/FUSE و MediaStore جدا کن.
- FUSE 4.19 را بدون بررسی کامل قابلیت‌ها با درخت 4.14 جایگزین نکن.

### HMP / EAS / EEVDF
- HMP/EAS/Hybrid را از EEVDF semantic changes جدا نگه دار.
- در EEVDF delayed dequeue، rb-tree membership، rq locking، migration, wakeup, entity lifetime، cgroup, PELT/PSI، IOWAIT، throttling، task exit، policy change و CPU hotplug را بررسی کن.
- Compile success به معنی scheduler correctness نیست.

### Boot / AnyKernel
- DTB را در محل صحیح boot image/header قرار بده؛ کورکورانه به Image.gz-dtb append نکن.
- ramdisk، cmdline، AVB و header را ناخواسته تغییر نده.
- device props واقعی ROM و whitelist AnyKernel را تطبیق بده؛ خطای شناخته‌شده `Unsupported device Aborting` را دوباره ایجاد نکن.

## 5. ترتیب مراحل CI و gateها

1. Source checkout و ثبت SHA.
2. Preflight source/config.
3. Patch generation و fail-fast anchor checks.
4. Static audit روی source واقعی تولیدشده.
5. Syntax/build compile کامل.
6. Kernel image/DTB validation.
7. AnyKernel3 packaging و device detection validation.
8. ZIP integrity + artifact existence + checksum.
9. Release فقط پس از موفقیت مراحل لازم و با وضعیت تست صادقانه.
10. تست واقعی دستگاه: boot، radio/data، storage/app data، scheduler/performance، thermal.

هر مرحله status مستقل داشته باشد: `PASS`, `FAIL`, `SKIPPED`, `NOT TESTED`. هیچ مرحله‌ای را با نتیجهٔ مرحلهٔ دیگر جایگزین نکن.

## 6. ثبت خطا و جلوگیری از تکرار

برای هر خطا فوراً یک گزارش در `knowledge/builds/build-<run-id>.md` یا گزارش جلسه ایجاد کن و index را به‌روز کن:

- Date/time:
- Workflow / job / step:
- Run ID + URL:
- Branch + commit SHA:
- Source baseline/version:
- First real error (log excerpt):
- Root cause: confirmed / probable / unknown:
- Affected file(s):
- Fix commit + exact change:
- Rerun IDs and outcomes:
- Compile / package / artifact / boot / device-test status:
- Regression risk and prevention rule:

اگر علت هنوز مشخص نیست، آن را حدس نزن. لاگ کامل را دریافت کن، اولین خطای واقعی را پیدا کن و تا آن زمان فقط «علت نامشخص» ثبت کن.

## 7. پایان هر بیلد

- [ ] گزارش build کامل شد.
- [ ] خطاهای جدید به failure index اضافه شدند.
- [ ] درس جدید به سند حوزه‌ای مربوطه اضافه شد.
- [ ] نتیجهٔ موفق/ناموفق و تست دستگاه جداگانه ثبت شد.
- [ ] هیچ تغییر آزمایشی به‌عنوان stable ثبت نشد.

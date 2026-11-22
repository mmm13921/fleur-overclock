# CPU/GPU، لمس، نمایشگر و کارایی بازی

## هدف عملکردی

کاربر عمدتاً روی COD Mobile، frame-time پایدار، input latency پایین، پاسخ‌گویی لمس و app switching تمرکز دارد. FPS میانگین به‌تنهایی معیار کافی نیست؛ frame pacing، 1% low، touch-to-photon و thermal residency نیز باید بررسی شوند.

## GPU و نمایشگر

- GPU دستگاه Mali-G57 MC2 است؛ مسیر devfreq گزارش‌شده: `/sys/devices/platform/13000000.mali`.
- مسیر GED گزارش‌شده: `/sys/kernel/ged/hal`.
- درایور گزارش‌شده 32.1.0 و Vulkan 1.1.177 بوده است.
- فرکانس GPU حدود 1003MHz در یک build boot شده است.
- 1050/1100MHz در تست کاربر بهبود روانی نداشته‌اند؛ 1400MHz با 1.1V boot نشده است.
- پنل 96Hz در یک build فعال شده است؛ تست واقعی پایداری، مصرف و touch sampling لازم است.
- افزایش فرکانس بدون تطبیق OPP، voltage, posdiv, DDS, thermal, GED و DTB انجام نشود.

## Touch و thread placement

- touch controller گزارش‌شده: `fts_ts`، event3، I2C 0-0038، مختصات X=0..1079 و Y=0..2399، ده slot.
- کاربر خواسته threadهای touch و input شامل `fts_ts`، InputReader، InputDispatcher و SurfaceFlinger روی big CPUs بررسی شوند.
- pin کردن thread به CPU6-7 باید ابتدا با trace و نام واقعی thread تأیید شود؛ اسم thread ممکن است بین ROMها تغییر کند.
- affinity ثابت برای همهٔ threadها می‌تواند latency یا throughput را بدتر کند؛ قبل/بعد با Perfetto و frame timeline اندازه‌گیری شود.

## CPU topology و affinity

- MT6781: 6×A55 + 2×A76، دو کلاستر.
- کاربر برای بازی ترجیح آزمایشی داده که little-core در اجرای threadهای اصلی بازی دخالت کمتری داشته باشد و سهم big/little در تست‌ها بررسی شود.
- TID pinning نباید جایگزین scheduler درست شود؛ هر اسکریپت باید PID/TID را در هر اجرا دوباره resolve کند.
- از affinityهای ثابت مانند `c0`, `3f`, `ff`, `07` فقط با دانستن CPU mask و online state استفاده شود.
- COD package گزارش‌شده: `com.activision.callofduty.shooter`.

## VM و app retention

- هدف کاربر حفظ برنامه‌ها در پس‌زمینه و کاهش reload است.
- userspace LMKD در دستگاه تشخیص داده شده بود.
- مقادیر آزمایشی LMKD شامل low/medium/critical حدود 1001 و `kill_heaviest_task=false` بوده‌اند؛ این‌ها فقط آزمایش‌اند و باید با PSI، memory pressure و رفتار واقعی برنامه‌ها سنجیده شوند.
- تغییر `thrashing_limit=300` در Android 13 موجب bootloop گزارش شده؛ تکرار بدون rollback و تست جداگانه ممنوع.
- uclamp/stune/perfmgr و LMKD userspace را با هم تحلیل کن؛ تغییر kernel vm tunables لزوماً LMKD policy را override نمی‌کند.

## Scheduler knobs گزارش‌شده

این موارد snapshotهای کاربرند، نه baseline قطعی:
- `sched_latency_ns=10000000`
- `migration_cost_ns=0`
- `sched_tunable_scaling=0`
- `nr_migrate=2147483647`
- `sched_energy_aware=1`
- `sched_cstate_aware=1`
- uclamp stune min/max و vendor perfmgr thresholds نیز بررسی شده‌اند.
- legacy CFS latency/wakeup tunables ممکن است در EEVDF patch branch وجود نداشته باشند؛ آن‌ها را بدون بررسی ABI/implementation دوباره ایجاد نکن.

## معیارهای اعتبارسنجی

- frame-time distribution، 1%/0.1% lows و touch-to-photon.
- perfetto sched_switch/wakeup/migration و CPU frequency residency.
- GPU frequency/voltage/thermal throttle و GED events.
- memory PSI، LMKD kill logs و app cold/warm launch.
- battery/thermal state ثابت در مقایسه‌ها.

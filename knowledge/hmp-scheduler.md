# HMP / EAS / Hybrid scheduler — دانش و یافته‌ها

## قابلیت ثبت‌شده در Release

Build 30 و Build 38 شامل selector حالت CPU scheduler با گزینه‌های HMP / EAS / Hybrid بوده‌اند؛ حالت پیش‌فرض HMP ثبت شده است.

Release references:
- https://github.com/mmm13921/fleur-overclock/releases/tag/meys-projectid-30
- https://github.com/mmm13921/fleur-overclock/releases/tag/meys-projectid-30-eevdf-modem-38
- Build 49: https://github.com/mmm13921/fleur-overclock/releases/tag/scheduler-hmp-eas-hybrid-49

وجود selector به معنی برتری قطعی یکی از حالت‌ها یا فعال بودن هم‌زمان تمام الگوریتم‌ها نیست. رفتار runtime باید از source/config/sysfs و اندازه‌گیری واقعی استخراج شود.

## پلتفرم

- MT6781 با 6×A55 و 2×A76؛ دو کلاستر.
- در اطلاعات ظرفیت CPU کاربر، هسته‌های بزرگ با ظرفیت پیش‌فرض حدود 427 گزارش شده‌اند؛ ظرفیت نهایی باید از device tree و scheduler topology همان build خوانده شود.
- HMP و EAS روی topology و energy model وابسته‌اند؛ صرف انتخاب نام mode کافی نیست.

## اولویت‌های کاربر برای بازی

- تمرکز روی COD Mobile، latency پایین، پاسخ‌گویی لمس و تعویض سریع برنامه‌ها.
- ترجیح تقسیم بار little/big به‌صورت آزمایشی 50/50 و پرهیز از pin کردن threadهای بازی روی little core؛ این‌ها خواسته/آزمایش کاربرند، نه الزام عمومی scheduler.
- در برخی آزمایش‌ها affinity برای process/TIDها مدنظر بوده، اما pinning بیش از حد می‌تواند migration و load balance را خراب کند.
- thread placement باید با trace/perfetto و مشاهدهٔ واقعی TIDها بررسی شود؛ صرف نام threadها ثابت نمی‌کند همیشه همان وظیفه را دارند.

## نکات پیشگیری از regression

- هر تغییر HMP/EAS/Hybrid را از تغییرات EEVDF جدا نگه دار تا علت regression مشخص باشد.
- بررسی کن scheduler mode switch در زمان runtime واقعاً state را تغییر می‌دهد و همهٔ مسیرهای init/exit و CPU hotplug درست هستند.
- در صورت EAS، energy model، capacity, uclamp, schedtune و vendor hooks را با هم بررسی کن.
- در صورت HMP، topology, capacity, migration cost, wakeup placement و vendor load-balance extensions را بررسی کن.
- legacy tunables ممکن است در EEVDF branch حذف یا تغییر کرده باشند؛ در Build 38-based EEVDF releases تصریح شده که CFS latency/wakeup tunables قدیمی وجود ندارند. آن‌ها را بدون بررسی به EEVDF اضافه نکن.

## تنظیمات آزمایشی ثبت‌شده از گفتگوها

موارد زیر snapshot تنظیمات/ترجیحات گزارش‌شده‌اند و نباید به‌صورت پیش‌فرض داخل کرنل hardcode شوند:
- `sched_latency_ns` مقدار پایهٔ 10000000 گزارش شده بود.
- `migration_cost_ns` در آزمایش کاربر مقدار 0 خوانده/نوشته شده بود.
- `sched_tunable_scaling=0`
- `nr_migrate=2147483647` آزمایش شده بود.
- `sched_energy_aware=1` و `sched_cstate_aware=1`
- uclamp stune min/max و schedtune task thresholds در مسیرهای vendor-specific بررسی شده‌اند.
- کاربر در مورد `cache_nice_tries=-1` پرسیده بود؛ مقدار باید مطابق implementation همان kernel تفسیر شود و نباید از نسخه‌های دیگر فرض گرفته شود.

## تست لازم

- مقایسهٔ HMP/EAS/Hybrid با workload یکسان، governor و thermal state یکسان.
- COD Mobile frame-time و input latency، نه فقط FPS میانگین.
- app launch/switch و background retention.
- مصرف CPU و migration، frequency residency، thermal throttling و مصرف انرژی.
- بررسی hotplug و task affinity.

## تاریخچهٔ HMP V2 و boot tuning

- کاربر HMP V2 را در تغییرات storage حساس دانسته و خواسته هنگام بررسی FUSE/Storage دست‌نخورده بماند؛ تغییر HMP را با تغییر filesystem مخلوط نکن.
- Build 30/38 دارای selector HMP/EAS/Hybrid و HMP default در release notes بوده‌اند. Build 49 نیز این حالت‌ها را حفظ کرده است.
- boot-patch set مورد درخواست شامل sched-u32 min/max، `vm.extfrag_threshold`، حذف minimum از ondemand `sampling_rate`، cpu_capacity per-CPU و حذف سقف 1024 و جدول‌های CPU/GPU/DTB بوده است. موارد sysctl-all، ged-all، cpuset-empty، swap-max و wm-max اعمال نشدند؛ حداقل فرکانس CPU به علت bootloop غیرفعال شد. این‌ها را با patchهای فعال فعلی اشتباه نگیر؛ source/commit باید بررسی شود.
- هیچ evidenceای وجود ندارد که یک mode در تمام workloadها برتر باشد. HMP default یک انتخاب baseline است، نه اثبات کارایی برتر.

## نکتهٔ سازگاری EEVDF

در شاخه‌های EEVDF، legacy CFS latency/wakeup tunables ممکن است وجود نداشته باشند یا معنای متفاوتی داشته باشند. HMP/EAS/Hybrid policy layer را از EEVDF entity selection/delayed dequeue جدا نگه دار. هر mode باید با runtime state، CPU hotplug، wakeup placement، migration و vendor hooks تست شود.

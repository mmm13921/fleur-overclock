

## تاریخچهٔ HMP V2 و boot tuning

- کاربر HMP V2 را در تغییرات storage حساس دانسته و خواسته هنگام بررسی FUSE/Storage دست‌نخورده بماند؛ تغییر HMP را با تغییر filesystem مخلوط نکن.
- Build 30/38 دارای selector HMP/EAS/Hybrid و HMP default در release notes بوده‌اند. Build 49 نیز این حالت‌ها را حفظ کرده است.
- boot-patch set مورد درخواست شامل sched-u32 min/max، `vm.extfrag_threshold`، حذف minimum از ondemand `sampling_rate`، cpu_capacity per-CPU و حذف سقف 1024 و جدول‌های CPU/GPU/DTB بوده است. موارد sysctl-all، ged-all، cpuset-empty، swap-max و wm-max اعمال نشدند؛ حداقل فرکانس CPU به علت bootloop غیرفعال شد. این‌ها را با patchهای فعال فعلی اشتباه نگیر؛ source/commit باید بررسی شود.
- هیچ evidenceای وجود ندارد که یک mode در تمام workloadها برتر باشد. HMP default یک انتخاب baseline است، نه اثبات کارایی برتر.

## نکتهٔ سازگاری EEVDF

در شاخه‌های EEVDF، legacy CFS latency/wakeup tunables ممکن است وجود نداشته باشند یا معنای متفاوتی داشته باشند. HMP/EAS/Hybrid policy layer را از EEVDF entity selection/delayed dequeue جدا نگه دار. هر mode باید با runtime state، CPU hotplug، wakeup placement، migration و vendor hooks تست شود.

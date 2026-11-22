

## سوابق EEVDF قبل از runهای 2026-11-23

- Build 14 با SHA `3db23a1ab1f880e436e8daad8a8a440426b229fb` در سوابق به‌عنوان build موفق EEVDF و AnyKernel3 package ثبت شده است؛ اجرای انتشار جدیدتر Build 14 شکست خورد و baseline نشد.
- شاخهٔ `meys-eevdf-baseline-test`، run #1 و commit `8db50399b2`: آماده‌سازی/ورود به build آغاز شد اما run لغو شد؛ compile و artifact نهایی اثبات نشد.
- در درخواست اصلی، هدف کاربر بک‌پورت کامل EEVDF Linux 6.18 با همهٔ featureها و پارامترها بود؛ EEVDF پایهٔ 4.19 به‌تنهایی معادل این هدف نیست.

### فهرست قابلیت‌هایی که باید در ممیزی کامل پوشش داده شوند

بر اساس اختلاف‌های ثبت‌شده بین EEVDF پایهٔ Fleux 4.19 و هدف Linux 6.18، موارد زیر ناقص/نیازمند audit بوده‌اند:
- `min_slice` و RB-tree augmentation مربوط
- `vprot`
- `PREEMPT_SHORT`
- `PLACE_REL_DEADLINE`
- `DELAY_DEQUEUE` و `DELAY_ZERO`
- `sched_delayed`
- `custom_slice` و `sched_runtime`
- `sched_base_slice` و کنترل‌های مربوط

این فهرست وضعیت تاریخی است؛ برای هر مورد باید وجود implementation واقعی، call sites، config/runtime knob و semantics بررسی شود. اضافه شدن اسم feature یا sysctl به‌تنهایی پیاده‌سازی کامل نیست.

## قواعد قطعی از خطاهای تکرارشونده

1. `struct lb_env` در Fleux 4.19.325 فاقد `migration_type` بوده و enum `migrate_load` از API مقصد در دسترس نبوده است؛ از کپی مستقیم guard نسخهٔ جدید استفاده نکن.
2. helper `cfs_rq_throttled()` در یکی از patchها قبل از declaration استفاده شد؛ prototype با امضای دقیق مقصد لازم است.
3. وقتی patcher guard را اصلاح می‌کند، source audit نیز باید همان guard جدید را بررسی کند؛ assertion قدیمی `env->migration_type != migrate_load` باعث audit mismatch شد.
4. در migration delayed entity، guard سادهٔ `if (p->se.sched_delayed) return 0;` فقط سازگاری اولیهٔ کد مقصد را فراهم می‌کند؛ forced migration، affinity، CPU hotplug و entity accounting هنوز باید جداگانه ثابت شوند.
5. audit pass به‌تنهایی compile pass نیست؛ compile pass هم correctness scheduler را ثابت نمی‌کند.

# EEVDF 6.18 backport — build and debugging log

**آخرین به‌روزرسانی:** 2026-11-23  
**شاخهٔ کاری:** `meys-eevdf-618-porting`  
**دستگاه هدف:** Redmi Note 11S 4G / fleur / MT6781  
**وضعیت نهایی ثبت‌شده در این گزارش:** فیکس‌های اخیر commit شده‌اند؛ اجرای CI مربوط به آخرین commit باید جداگانه بررسی شود. هیچ ادعایی دربارهٔ بیلد نهایی یا بوت دستگاه از این گزارش برداشت نشود.

## هدف و محدوده

پورت قابلیت‌های EEVDF از Linux 6.18 به شاخهٔ Fleux مبتنی بر Linux 4.19.325. این کار یک backport سازگاری است، نه انتقال مستقیم فایل‌های scheduler نسخهٔ جدید. تفاوت APIها و ساختارهای 4.19 باید در هر patch لحاظ شود.

منابع مرجع:
- Linux scheduler EEVDF documentation: https://docs.kernel.org/scheduler/sched-eevdf.html
- Linux v6.18 scheduler sources: https://github.com/torvalds/linux/tree/v6.18/kernel/sched
- Fleux source repository: https://gitlab.com/ (ورودی CI فعلی از شاخهٔ V11 دریافت می‌شود؛ URL دقیق پروژه در workflow نگهداری شود.)

## خطاهای مشاهده‌شده و ریشه‌یابی

### Build run 45074244232 — FAILED

Run: https://github.com/mmm13921/fleur-overclock/actions/runs/45074244232  
Commit: `323710e7b4f1a71103f0e9136d9f5ba7f6c6cc0f`

خطاهای کامپایل در `kernel/sched/fair.c`:

1. **`cfs_rq_throttled` بدون declaration پیش از استفاده**
   - علت: helperهای delayed-dequeue در فایل تولیدشده پیش از تعریف helper مربوط به CFS bandwidth درج می‌شوند.
   - نکتهٔ نسخه‌ای: در سورس Fleux V11/4.19 تابع `cfs_rq_throttled(struct cfs_rq *)` وجود دارد، اما تعریف آن پایین‌تر از محل helperهای delayed-dequeue قرار گرفته است.
   - اصلاح ثبت‌شده: افزودن prototype قبل از helperهای delayed-dequeue:
     `static inline int cfs_rq_throttled(struct cfs_rq *cfs_rq);`
   - commit حاوی این اصلاح: `ddbd0f93ab206782977b9672da0fa858f587afa9`.
   - وضعیت: commit شده؛ نتیجهٔ کامپایل پس از این اصلاح باید از CI خوانده شود.

2. **`struct lb_env` فاقد عضو `migration_type` و نبودن `migrate_load`**
   - علت: patch از نام‌گذاری/ساختار نسخهٔ جدید scheduler استفاده کرده که در نسخهٔ 4.19.325 این شاخه موجود نیست.
   - اصلاح ثبت‌شده: guard مهاجرت delayed entity به شرط سازگار با کد فعلی تبدیل شد:
     `if (p->se.sched_delayed) return 0;`
     این یعنی entity با وضعیت delayed از این مسیر load-balance خارج می‌شود؛ این رفتار باید در بازبینی معنایی migration و delayed dequeue دوباره ارزیابی شود و صرفاً به‌خاطر کامپایل شدن، اثبات صحت scheduler نیست.
   - تغییر اولیه در commit `e3006c26ae28de575a2df9658ae0daafc1e98d4c` انجام شد؛ اصلاح prototype در commit بعدی `ddbd0f93ab206782977b9672da0fa858f587afa9` ثبت شد.

3. **`migrate_load`**
   - علت مستقل نیست؛ همان ناسازگاری API نسخه‌ای مورد 2 است.
   - اقدام پیشگیرانه: در backportها از استفاده از enum/fieldهای جدید بدون بررسی تعریف دقیق آن‌ها در سورس مقصد خودداری شود.

## وضعیت CI مرتبط

- Audit run `45074244223` برای commit `323710e7...` موفق شد: https://github.com/mmm13921/fleur-overclock/actions/runs/45074244223
- مهم: موفقیت Audit به معنی موفقیت کامپایل نیست؛ همان commit در run `45074244232` در مرحلهٔ کامپایل شکست خورد.
- پس از اصلاحات، commit `e3006c26ae28de575a2df9658ae0daafc1e98d4c` ایجاد شد.
- آخرین commit ثبت‌شده در این گزارش: `ddbd0f93ab206782977b9672da0fa858f587afa9`.
- CIهای ایجادشده برای commit میانی `e3006c26...`:
  - Build: https://github.com/mmm13921/fleur-overclock/actions/runs/45074696502
  - Audit: https://github.com/mmm13921/fleur-overclock/actions/runs/45074696505
  این runها مربوط به commit میانی هستند و نباید نتیجهٔ آن‌ها را به commit نهایی `ddbd0f93...` نسبت داد.
- پس از commit نهایی، CI جدید با SHA دقیق `ddbd0f93...` ایجاد شد:
  - Build: https://github.com/mmm13921/fleur-overclock/actions/runs/45074713511
  - Audit: https://github.com/mmm13921/fleur-overclock/actions/runs/45074713510
  وضعیت و نتیجهٔ نهایی این دو run باید قبل از هر ادعای موفقیت بررسی شود.

## قواعد جلوگیری از تکرار

- قبل از استفاده از هر symbol، field یا enum جدید، تعریف آن را در **سورس مقصد Fleux 4.19.325** بررسی کنید؛ وجود آن در Linux 6.18 کافی نیست.
- helperهایی که قبل از تعریف واقعی خود استفاده می‌شوند باید prototype سازگار و صحیح داشته باشند.
- patcherهای Python را هم از نظر anchor و هم از نظر متن نهایی تولیدشده بررسی کنید. وجود یک رشته در comment نباید به‌عنوان وجود macro/function واقعی تشخیص داده شود؛ برای تعریف‌ها regex محدود به ابتدای خط یا parser دقیق‌تر استفاده شود.
- Static audit را طوری بنویسید که ساختار واقعی کد را بررسی کند، نه صرفاً وجود یک substring.
- بعد از هر patch: اجرای syntax check، audit، compile، packaging و در نهایت تست واقعی روی دستگاه، هرکدام جداگانه ثبت شوند.
- بعد از کامپایل موفق نیز بازبینی معنایی delayed dequeue لازم است: enqueue/dequeue دوباره‌کاری، rb-tree membership، rq locking، migration/wakeup، entity lifetime، PSI، IOWAIT، hierarchical runnable accounting، PELT، throttling، task exit، policy/class change و CPU hotplug.
- هرگز برای سبز شدن CI، خطای compiler را با حذف بی‌ضابطهٔ guard یا خاموش‌کردن warning پنهان نکنید.

## مواردی که هنوز اثبات نشده‌اند

- صحت کامل semantics پورت EEVDF 6.18 روی 4.19.
- نبود regression در delayed dequeue، migration، cgroup، PELT/PSI و accounting.
- موفقیت کامپایل و ساخت AnyKernel برای commit `ddbd0f93...` تا زمان بررسی نتیجهٔ CI.
- بوت و پایداری روی Redmi Note 11S؛ نیازمند تست واقعی دستگاه است.


## آخرین شکست و اصلاح guard — 2026-11-23

### Runهای commit `ddbd0f93...`

- Build run **45074713510**: FAILED در مرحلهٔ `Apply EEVDF layers`؛ کامپایل/AnyKernel اصلاً شروع نشد.
  https://github.com/mmm13921/fleur-overclock/actions/runs/45074713510
- Audit run **45074713511**: FAILED؛ تنها check مردود `migration_load_balance_guard` بود.
  https://github.com/mmm13921/fleur-overclock/actions/runs/45074713511

### Root cause قطعی

در `eevdf/patches/0003-delayed-dequeue-618.py`، patcher هنوز guard قدیمی را در `fair.c` درج می‌کرد:

`if (p->se.sched_delayed && env->migration_type != migrate_load) return 0;`

اما Fleux V11 / Linux 4.19.325 در `struct lb_env` عضو `migration_type` ندارد و نماد `migrate_load` نیز در این API در دسترس نیست. این با نسخهٔ جدیدتر scheduler اشتباه گرفته شده بود. علاوه بر خطر compile error، audit نیز انتظار guard سازگار را داشت.

### اصلاح ثبت‌شده

- Commit: `1efa8cfb9987168ba2a6326da84b3001f9a28841`
- فایل: `eevdf/patches/0003-delayed-dequeue-618.py`
- تغییر: حذف ارجاع به `env->migration_type` و `migrate_load`؛ patcher اکنون guard سادهٔ `if (p->se.sched_delayed) return 0;` را تولید می‌کند.
- هدف: delayed entity از مسیر عادی load-balance عبور نکند و کد با API مقصد 4.19 سازگار بماند.
- **محدودیت معنایی:** این guard به‌تنهایی صحت forced migration، affinity changes، CPU hotplug یا انتقال taskهای delayed را ثابت نمی‌کند. این مسیرها باید جداگانه بررسی شوند؛ صرف پاس شدن audit/compile کافی نیست.

### CI rerun برای commit اصلاحی

- Build run **45075293759**: https://github.com/mmm13921/fleur-overclock/actions/runs/45075293759
- Audit run **45075293762**: https://github.com/mmm13921/fleur-overclock/actions/runs/45075293762
- هنگام ثبت این یادداشت هر دو run در حال اجرا بودند؛ نتیجهٔ نهایی باید پس از تکمیل به همین گزارش اضافه شود.


### Audit mismatch پس از commit `1efa8cfb...`

- Audit run **45075293762**: FAILED در source audit، نه به‌خاطر خطای C؛ check `layer3.migration_guard` هنوز انتظار رشتهٔ قدیمی `env->migration_type != migrate_load` را داشت.
  https://github.com/mmm13921/fleur-overclock/actions/runs/45075293762
- Root cause: patcher برای API واقعی 4.19 به guard جدید تغییر کرده بود، اما ممیزی جامع `eevdf/audit_eevdf_618.py` هنوز assertion نسخهٔ قدیمی را نگه داشته بود. این یک ناسازگاری بین patcher و audit بود.
- Fix commit: `2192589ed0345eae459402d19e2b7ac7b827f7bc`
- فایل: `eevdf/audit_eevdf_618.py`
- اصلاح: assertion اکنون guard تولیدشدهٔ `if (p->se.sched_delayed) return 0;` را بررسی می‌کند.
- CI rerun:
  - Build: https://github.com/mmm13921/fleur-overclock/actions/runs/45075426116
  - Audit: https://github.com/mmm13921/fleur-overclock/actions/runs/45075426097
  - وضعیت در زمان ثبت: queued؛ نتیجه هنوز نامشخص است.

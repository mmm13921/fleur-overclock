# EEVDF commit history

Repository: [`mmm13921/fleur-overclock`](https://github.com/mmm13921/fleur-overclock)  
Baseline: [`meys-build38-boot-patches`](https://github.com/mmm13921/fleur-overclock/tree/meys-build38-boot-patches)  
Earlier implementation branch: [`meys-eevdf-618-full`](https://github.com/mmm13921/fleur-overclock/tree/meys-eevdf-618-full)  
Expanded porting branch: [`meys-eevdf-618-porting`](https://github.com/mmm13921/fleur-overclock/tree/meys-eevdf-618-porting)

## Initial EEVDF foundation on the Build 38 line

- [`4ecebe5af83d`](https://github.com/mmm13921/fleur-overclock/commit/4ecebe5af83d) — Add EEVDF layer 1 and DPMAIF PM guard to ProjectID 30 build
- [`594f54cff376`](https://github.com/mmm13921/fleur-overclock/commit/594f54cff376) — Build ProjectID 30 with EEVDF and modem PM
- [`aee40b3d6043`](https://github.com/mmm13921/fleur-overclock/commit/aee40b3d6043) — Add EEVDF Linux 6.18 layer 1 patch (min base slice 0)
- [`1c81ba096c3f`](https://github.com/mmm13921/fleur-overclock/commit/1c81ba096c3f) — Add EEVDF audit
- [`1a9135fba57e`](https://github.com/mmm13921/fleur-overclock/commit/1a9135fba57e) — Document EEVDF layer 1
- [`a87c82aefcb4`](https://github.com/mmm13921/fleur-overclock/commit/a87c82aefcb4) — Add Meys EEVDF AnyKernel installer
- [`1de8baac3d8e`](https://github.com/mmm13921/fleur-overclock/commit/1de8baac3d8e) — Name the EEVDF kernel version in build manifest
- [`9898f02f053b`](https://github.com/mmm13921/fleur-overclock/commit/9898f02f053b) — Fix EEVDF modem release package and metadata
- [`545f6b7f1009`](https://github.com/mmm13921/fleur-overclock/commit/545f6b7f1009) — Correct release asset list and multiline metadata
- [`d556d9676c53`](https://github.com/mmm13921/fleur-overclock/commit/d556d9676c53) — Cancel stale baseline builds and trigger only the complete EEVDF modem build

## Expanded porting branch history

The following is the complete commit list returned by GitHub compare for `meys-build38-boot-patches...meys-eevdf-618-porting` (135 commits ahead). It includes Layer 1/2 work, Layer 3 delayed-dequeue work, source audits, patcher corrections and CI/build integration. The earlier `meys-eevdf-618-full` snapshot is the first 15 commits of this development sequence.

- 2026-11-22 — [`5d3f0126bb80`](https://github.com/mmm13921/fleur-overclock/commit/5d3f0126bb80b43116d5cdfad7542d5dd667f3cc) — eevdf: add dequeue bool API prerequisite
- 2026-11-22 — [`49c59642e213`](https://github.com/mmm13921/fleur-overclock/commit/49c59642e21388e263ef450b26cbae745764cedf) — fix dequeue API patcher escaping
- 2026-11-22 — [`74008aa7ada9`](https://github.com/mmm13921/fleur-overclock/commit/74008aa7ada98f37233d7e63ce785f71e5dc3db3) — eevdf: wire dequeue bool prerequisite into build
- 2026-11-22 — [`15f942524b53`](https://github.com/mmm13921/fleur-overclock/commit/15f942524b533c0f24983f88d6b25dbea6c5ccba) — eevdf: audit dequeue bool prerequisite
- 2026-11-22 — [`47967ca09ec1`](https://github.com/mmm13921/fleur-overclock/commit/47967ca09ec1c317c4e5ee3dc3dfc3ec108bff96) — docs: update EEVDF backport stage
- 2026-11-22 — [`3be1fdc03fc6`](https://github.com/mmm13921/fleur-overclock/commit/3be1fdc03fc6ff9c30832bf1e74591cf52fb2385) — ci: enable EEVDF branch build and audit artifact
- 2026-11-22 — [`e009e0cd0d69`](https://github.com/mmm13921/fleur-overclock/commit/e009e0cd0d69125ada2996439968b730c8cdf1a5) — fix EEVDF dequeue bool audit matching
- 2026-11-22 — [`b3606cf0242e`](https://github.com/mmm13921/fleur-overclock/commit/b3606cf0242e7f2db7a23ed0b790aa44612ea484) — ci: include dequeue bool audit in AnyKernel package
- 2026-11-22 — [`9b9a3fdfeaed`](https://github.com/mmm13921/fleur-overclock/commit/9b9a3fdfeaedcc6f516ba469c7d3695d892b1b2d) — fix scheduler class regex in EEVDF audit
- 2026-11-22 — [`038fd48836cd`](https://github.com/mmm13921/fleur-overclock/commit/038fd48836cd1c5eceda8e530a999a73c49e9f55) — docs: track Linux 6.18 EEVDF backport layers
- 2026-11-22 — [`18dfee958e95`](https://github.com/mmm13921/fleur-overclock/commit/18dfee958e954059c300dabfb5e33e2707b573af) — ci: label EEVDF backport workflow
- 2026-11-22 — [`0d83ed7df227`](https://github.com/mmm13921/fleur-overclock/commit/0d83ed7df22781830303e618cfc68b4642b3d02f) — fix: audit dequeue bool callbacks by function body
- 2026-11-22 — [`3326f2f1662f`](https://github.com/mmm13921/fleur-overclock/commit/3326f2f1662f90d51ff075a778de886cffe6cf39) — fix: import regex module in EEVDF audit
- 2026-11-22 — [`3d30bd36cb53`](https://github.com/mmm13921/fleur-overclock/commit/3d30bd36cb53e9a6676127ea2aeb122d35b42e3c) — sched: fix EEVDF min-vruntime augmentation
- 2026-11-22 — [`6d73db2160b5`](https://github.com/mmm13921/fleur-overclock/commit/6d73db2160b572f936dff38394302a4667900e82) — sched: complete fair custom slice ABI
- 2026-11-22 — [`2f1db329362f`](https://github.com/mmm13921/fleur-overclock/commit/2f1db329362f97b6a113aadd90b446ded8fe5ff3) — sched: add Linux 6.18 delayed dequeue backport layer
- 2026-11-22 — [`3751f4fd261a`](https://github.com/mmm13921/fleur-overclock/commit/3751f4fd261a2cbb8b170bc1f6098a06cfc29001) — sched: fix delayed dequeue helper ordering and throttle accounting
- 2026-11-22 — [`e8b2d3c9813c`](https://github.com/mmm13921/fleur-overclock/commit/e8b2d3c9813c78f822480eb3ecb3cc139e2732aa) — sched: match exact fair scheduler function definitions
- 2026-11-22 — [`f74385db530d`](https://github.com/mmm13921/fleur-overclock/commit/f74385db530dc7014e04db0993b8404c0190232b) — sched: account delayed entities out of PELT runnable load
- 2026-11-22 — [`72126aa29221`](https://github.com/mmm13921/fleur-overclock/commit/72126aa292219be4a9b4e3c555c91193c9d394e8) — sched: correct patcher replacement string escaping
- 2026-11-22 — [`03683ffecf97`](https://github.com/mmm13921/fleur-overclock/commit/03683ffecf9714904306be5979fd15772a8c638a) — sched: integrate delayed entities with bandwidth, balancing and class changes
- 2026-11-22 — [`f8509acf20cd`](https://github.com/mmm13921/fleur-overclock/commit/f8509acf20cd903b5129bf3f4be3138cd6039192) — sched: target throttle and scheduler class transition anchors precisely
- 2026-11-22 — [`fd8d1046f3e7`](https://github.com/mmm13921/fleur-overclock/commit/fd8d1046f3e78f80c38f66e9bbcc9064d8ea564e) — sched: separate runnable load and synchronize group entity weights
- 2026-11-22 — [`961cb52501da`](https://github.com/mmm13921/fleur-overclock/commit/961cb52501da2241149b5998794de0cc2f2e8a2b) — sched: update group runnable weights after hierarchy counters
- 2026-11-22 — [`4ba8bbdea150`](https://github.com/mmm13921/fleur-overclock/commit/4ba8bbdea150b40173561ee992c208c6b601f8e0) — sched: drain delayed group entities during cgroup teardown
- 2026-11-22 — [`407db6c31080`](https://github.com/mmm13921/fleur-overclock/commit/407db6c310802661366047df57e4e573cee395b2) — sched: declare delayed dequeue helper before group teardown
- 2026-11-22 — [`940a6a81027c`](https://github.com/mmm13921/fleur-overclock/commit/940a6a81027c9f389df685bb0ee5a5811101600e) — sched: avoid double hierarchical dequeue accounting on throttled runqueues
- 2026-11-22 — [`35a6bef283f2`](https://github.com/mmm13921/fleur-overclock/commit/35a6bef283f28ac06f5ace4f24f2e22768abec56) — sched: initialize delayed EEVDF task and cfs runqueue state
- 2026-11-22 — [`e27d9d6afdd7`](https://github.com/mmm13921/fleur-overclock/commit/e27d9d6afdd7b15af5ca1b1275df1654ea9ecd3d) — sched: guard hierarchical runnable helper for non-group builds
- 2026-11-22 — [`33eec24876a5`](https://github.com/mmm13921/fleur-overclock/commit/33eec24876a57f5b6fe90ab2ee730ca160228d0a) — sched: refresh non-SMP group runnable weight when task count changes
- 2026-11-22 — [`576b4f0af185`](https://github.com/mmm13921/fleur-overclock/commit/576b4f0af185936d4eaec290b3184363c8c90bd2) — sched: expand delayed dequeue audit coverage
- 2026-11-22 — [`d0a50f6580d7`](https://github.com/mmm13921/fleur-overclock/commit/d0a50f6580d7e9405e7156b13898fa614f94325f) — sched: preserve delayed group runnable counts across CFS throttle cycles
- 2026-11-22 — [`d7ca7558f0bf`](https://github.com/mmm13921/fleur-overclock/commit/d7ca7558f0bf5cf11860be1b3702d04cdfb646fa) — sched: audit complete EEVDF delayed dequeue semantics
- 2026-11-22 — [`fb30c9ceddea`](https://github.com/mmm13921/fleur-overclock/commit/fb30c9ceddeafa7290fd1c9a80392159f9a7c16f) — build: require full EEVDF source audit before kernel compilation
- 2026-11-22 — [`61a4993dc2e1`](https://github.com/mmm13921/fleur-overclock/commit/61a4993dc2e11f7fd3c120df38e9013ee77247fd) — docs: track delayed dequeue port and validation gates
- 2026-11-22 — [`d7fbffc8c540`](https://github.com/mmm13921/fleur-overclock/commit/d7fbffc8c5407ec5da32d20dcabc69e4bdea05b9) — ci: add source-only EEVDF audit without kernel compilation
- 2026-11-22 — [`c33662134173`](https://github.com/mmm13921/fleur-overclock/commit/c33662134173539984e71e6ca32dbf0807e4fb91) — sched: restart fair task selection from root after delayed entity removal
- 2026-11-22 — [`61754e8acb3f`](https://github.com/mmm13921/fleur-overclock/commit/61754e8acb3fba039dd739bd1896850a544167cd) — sched: target unregister group definition not prototype
- 2026-11-22 — [`b326bda6391c`](https://github.com/mmm13921/fleur-overclock/commit/b326bda6391cc69dfb5f770206b118f06cfce921) — ci: fix source audit artifact paths
- 2026-11-22 — [`67ed2e3faa65`](https://github.com/mmm13921/fleur-overclock/commit/67ed2e3faa653644306387d9bda794ab6236d362) — ci: retain transformed EEVDF source diff for review
- 2026-11-22 — [`5a2488fa286e`](https://github.com/mmm13921/fleur-overclock/commit/5a2488fa286ed047c335c6b6bbeb8e13c7169ec3) — sched: bypass delayed dequeue for special task states
- 2026-11-22 — [`f0a2bbefd8a2`](https://github.com/mmm13921/fleur-overclock/commit/f0a2bbefd8a2e00ffa68c91b604680ae1d5b1f23) — sched: propagate hierarchical EEVDF slice requests through task groups
- 2026-11-22 — [`5fe12a0556bb`](https://github.com/mmm13921/fleur-overclock/commit/5fe12a0556bb762acbef389bdf56d1242294d605) — sched: keep per-task custom slices while propagating group slices
- 2026-11-22 — [`a30da00ad84e`](https://github.com/mmm13921/fleur-overclock/commit/a30da00ad84e5f83994eac37136ad8133ef13e80) — sched: force delayed dequeue in wait_task_inactive
- 2026-11-22 — [`f63f73fbda3f`](https://github.com/mmm13921/fleur-overclock/commit/f63f73fbda3f0178b0bc709cd687560634cd26f8) — sched: audit special states, wait-task cleanup and group slices
- 2026-11-22 — [`33689f45923b`](https://github.com/mmm13921/fleur-overclock/commit/33689f45923b7b7b192fa27cb3d2c9a3b911db69) — sched: audit full delayed EEVDF edge paths and group slices
- 2026-11-22 — [`e6cac2c22329`](https://github.com/mmm13921/fleur-overclock/commit/e6cac2c22329424755d10d8b6d4b5123c15456b3) — sched: preserve V11 root runqueue counts during hierarchical dequeue
- 2026-11-22 — [`2af5a87142fe`](https://github.com/mmm13921/fleur-overclock/commit/2af5a87142fe4055b2998cbfbc7b7eb149761ba5) — sched: retain V11 task-count sub_nr_running semantics
- 2026-11-22 — [`017543682694`](https://github.com/mmm13921/fleur-overclock/commit/01754368269429ab9df8dfb56f8b503ef1fb4a9a) — sched: preserve workqueue sleep notifications for delayed tasks
- 2026-11-22 — [`ceb81509a53e`](https://github.com/mmm13921/fleur-overclock/commit/ceb81509a53ebf7763befd203fc8fb50a54ab07b) — sched: preserve group slice on delayed and throttled dequeue paths
- 2026-11-22 — [`e53f3905b711`](https://github.com/mmm13921/fleur-overclock/commit/e53f3905b711306ff1a0202a64020ec716c6ee3e) — sched: prevent delayed entities from becoming next buddies
- 2026-11-22 — [`f868eb85e1c2`](https://github.com/mmm13921/fleur-overclock/commit/f868eb85e1c2396469217d33e45707021afba29c) — sched: skip delayed next-buddy entities during EEVDF pick
- 2026-11-22 — [`e892c89c3d28`](https://github.com/mmm13921/fleur-overclock/commit/e892c89c3d284ae1138aa342b2f521fe08316da3) — sched: audit delayed next-buddy exclusion
- 2026-11-22 — [`e47899e4fdfb`](https://github.com/mmm13921/fleur-overclock/commit/e47899e4fdfb9b6a409d934e12c98e0a29f4da8e) — sched: audit delayed next-buddy exclusion
- 2026-11-22 — [`f2274a569938`](https://github.com/mmm13921/fleur-overclock/commit/f2274a569938a57e676e5ab53f3e2e38f97da40e) — sched: decrement runqueue task count by hierarchical queued count
- 2026-11-22 — [`7f2227ac3dff`](https://github.com/mmm13921/fleur-overclock/commit/7f2227ac3dff81f29f555b68e96cfeef26ccb8dd) — sched: normalize base slice and refresh it on sysctl writes
- 2026-11-22 — [`e33f6c70c9f6`](https://github.com/mmm13921/fleur-overclock/commit/e33f6c70c9f68a9c3383fa71754d14f7b0715f95) — sched: audit normalized EEVDF base slice controls
- 2026-11-22 — [`d4ca877374eb`](https://github.com/mmm13921/fleur-overclock/commit/d4ca877374eb7c564e9677f7419cbc1e5bb99add) — sched: avoid duplicate fork-state initialization after layer one
- 2026-11-22 — [`9f28f10d248b`](https://github.com/mmm13921/fleur-overclock/commit/9f28f10d248b82ebead7f6d07ab03ea6619b5e79) — sched: prevent delayed entities from becoming next buddies
- 2026-11-22 — [`19398bac6d0d`](https://github.com/mmm13921/fleur-overclock/commit/19398bac6d0d82b412f646ffd236c4f75c540735) — sched: audit all delayed next-buddy guards
- 2026-11-22 — [`dad559d655ee`](https://github.com/mmm13921/fleur-overclock/commit/dad559d655eead3d2c84a93fbefe81ad37eac9ea) — sched: audit all delayed next-buddy guards
- 2026-11-22 — [`bace5b54bafd`](https://github.com/mmm13921/fleur-overclock/commit/bace5b54bafd2f622d7741620adaebf7c621b319) — fix: emit real line breaks in normalized base slice C patch
- 2026-11-22 — [`d152cae07bbf`](https://github.com/mmm13921/fleur-overclock/commit/d152cae07bbf7d618df79da6b67a1aeb16e9c0ac) — audit: require actual normalized base-slice code lines
- 2026-11-22 — [`2748fe329353`](https://github.com/mmm13921/fleur-overclock/commit/2748fe32935392e6367daca46335015a7ee9e9cb) — audit: require actual normalized base-slice code lines
- 2026-11-22 — [`ef34f8c9c43f`](https://github.com/mmm13921/fleur-overclock/commit/ef34f8c9c43f6d6c2a0fe6ef4428b423a31c7a44) — sched: preserve schedtune accounting across delayed dequeue and migration
- 2026-11-22 — [`dda130e2bdb8`](https://github.com/mmm13921/fleur-overclock/commit/dda130e2bdb8282973ce8c0254a265952abe9e2a) — audit: verify schedtune delayed task accounting
- 2026-11-22 — [`cafa2fed9a03`](https://github.com/mmm13921/fleur-overclock/commit/cafa2fed9a03385f9e0403fbdacdbcde6cac0824) — audit: verify schedtune delayed task accounting
- 2026-11-22 — [`eaddb534bec7`](https://github.com/mmm13921/fleur-overclock/commit/eaddb534bec7a4f9ac6233ac7ce9b94bd284226f) — fix: preserve unregister group function opening brace
- 2026-11-22 — [`22cbc9289ef5`](https://github.com/mmm13921/fleur-overclock/commit/22cbc9289ef545fa3df2f10814beec1f13c712de) — fix: place delayed migration guard after function declarations
- 2026-11-22 — [`e0fb2261fc4b`](https://github.com/mmm13921/fleur-overclock/commit/e0fb2261fc4b272bf4cb9f26aaadf65d5b03fa80) — sched: keep delayed block helper as final entity operation
- 2026-11-22 — [`667bd160983f`](https://github.com/mmm13921/fleur-overclock/commit/667bd160983facc902b81fc188ad7ef4ddace2ce) — fix: replace real fair-group teardown while preserving config stub
- 2026-11-22 — [`cd32ccd85124`](https://github.com/mmm13921/fleur-overclock/commit/cd32ccd8512413cf53e30654f27c22993af19719) — sched: avoid duplicate leaf cfs list removal on group teardown
- 2026-11-22 — [`8f9072116500`](https://github.com/mmm13921/fleur-overclock/commit/8f90721165009a851f816e83096c5ced9cfd5a2d) — sched: avoid iowait underflow when delayed tasks wake early
- 2026-11-22 — [`bf48b2b4f7aa`](https://github.com/mmm13921/fleur-overclock/commit/bf48b2b4f7aa1ecc49d51edeec194d903273f9cf) — audit: verify delayed iowait wakeup accounting
- 2026-11-22 — [`9146e8afd851`](https://github.com/mmm13921/fleur-overclock/commit/9146e8afd8513b03ebd4004089e95c643090bf6a) — audit: verify delayed iowait wakeup accounting
- 2026-11-22 — [`17665c382957`](https://github.com/mmm13921/fleur-overclock/commit/17665c3829577913474a264dc245da0ce0076d2a) — sched: enforce a safe minimum EEVDF base slice
- 2026-11-22 — [`c168430ee02e`](https://github.com/mmm13921/fleur-overclock/commit/c168430ee02e26746ed684a39d3eadcaadc6e4bb) — audit: verify safe EEVDF base slice bounds
- 2026-11-22 — [`93b7e0a48c0c`](https://github.com/mmm13921/fleur-overclock/commit/93b7e0a48c0c061a4f98ecf6db2e54519df0f2b3) — audit: verify safe EEVDF base slice bounds
- 2026-11-22 — [`5a6cdfc552f5`](https://github.com/mmm13921/fleur-overclock/commit/5a6cdfc552f5f0d63a4b28903e50be843bd9ada2) — sched: respect throttled task-group boundaries in delayed runnable counts
- 2026-11-22 — [`da2c04978f1c`](https://github.com/mmm13921/fleur-overclock/commit/da2c04978f1cc088bea54187076135dba4480d2a) — audit: verify delayed runnable counters stop at throttled groups
- 2026-11-22 — [`662503fef21e`](https://github.com/mmm13921/fleur-overclock/commit/662503fef21e657091ef1cbae0505bdf55db4ad3) — audit: verify delayed runnable counters stop at throttled groups
- 2026-11-22 — [`77999e0dbe6f`](https://github.com/mmm13921/fleur-overclock/commit/77999e0dbe6f91bab1b4010ae2c702614546f518) — sched: avoid double enqueue on delayed remote wakeup
- 2026-11-22 — [`e907a94c9d85`](https://github.com/mmm13921/fleur-overclock/commit/e907a94c9d8515201f97ab1da27cd6f11067137c) — audit: verify delayed wakeup does not double enqueue
- 2026-11-22 — [`9b5e5cfef816`](https://github.com/mmm13921/fleur-overclock/commit/9b5e5cfef8162827bb361a0e592584cd23ffbe46) — sched: restore delayed wakeup requeue path
- 2026-11-22 — [`9282a10d296b`](https://github.com/mmm13921/fleur-overclock/commit/9282a10d296baa44f11d4b0e83a2106a70d9ae5b) — audit: require delayed wakeup requeue wrapper
- 2026-11-22 — [`6055a6c46bed`](https://github.com/mmm13921/fleur-overclock/commit/6055a6c46bed6cdb5e92ab2184e90aa55565d34e) — audit: correct delayed wakeup requeue expectation
- 2026-11-22 — [`658c6cad28a7`](https://github.com/mmm13921/fleur-overclock/commit/658c6cad28a7034f20b8a7b1e54160c7d02a07e5) — eevdf: sync group runnable weights on dequeue
- 2026-11-22 — [`3c7493661075`](https://github.com/mmm13921/fleur-overclock/commit/3c749366107564b132bdb3431ef0cd73bbca35c0) — audit: verify delayed dequeue group accounting refresh
- 2026-11-22 — [`2018246c65e9`](https://github.com/mmm13921/fleur-overclock/commit/2018246c65e9d51097bb3c919721a4502b6c7828) — audit: fix dequeue accounting check regex
- 2026-11-22 — [`43405043ef74`](https://github.com/mmm13921/fleur-overclock/commit/43405043ef74f6502e6c3f22b8c54f773227d108) — eevdf: reset inherited entity state on fork
- 2026-11-22 — [`1c4f50c3b4b8`](https://github.com/mmm13921/fleur-overclock/commit/1c4f50c3b4b8d3ea5b8c99eddbd53bfad40cb180) — audit: require explicit EEVDF fork-state reset
- 2026-11-22 — [`98df8d609b6d`](https://github.com/mmm13921/fleur-overclock/commit/98df8d609b6dad33a6555d08b7eca4c7765434a8) — audit: correct fork-state tab matching
- 2026-11-22 — [`c930ba40b9df`](https://github.com/mmm13921/fleur-overclock/commit/c930ba40b9dfabc7e91f87c0a90e550fe46adc54) — eevdf: initialize fork tasks with base slice
- 2026-11-22 — [`181a5d9e619e`](https://github.com/mmm13921/fleur-overclock/commit/181a5d9e619e2a1e098c624d581a2494c4869c90) — audit: verify fork base-slice initialization
- 2026-11-22 — [`bb97d8b63c1a`](https://github.com/mmm13921/fleur-overclock/commit/bb97d8b63c1a4c063b4ce08c9f0dcb51df2274cc) — eevdf: rely on unified fork entity initialization
- 2026-11-22 — [`ea8e93119f94`](https://github.com/mmm13921/fleur-overclock/commit/ea8e93119f94db48a937024036a23a14dd28c313) — eevdf: preserve sched_attr runtime ABI
- 2026-11-22 — [`e111f7aa0de7`](https://github.com/mmm13921/fleur-overclock/commit/e111f7aa0de7b48f20b1c432448b6af8c2dd89bc) — audit: keep custom slice internal to fair groups
- 2026-11-22 — [`ce1649506359`](https://github.com/mmm13921/fleur-overclock/commit/ce164950635932afc84510bcd862fb40e96d4454) — audit: document preserved sched_attr ABI
- 2026-11-22 — [`8a75841f0d90`](https://github.com/mmm13921/fleur-overclock/commit/8a75841f0d903a9d3ad488aac3eb7f4f0242212a) — sched: preserve MTK heavy-task dequeue accounting
- 2026-11-22 — [`8fa0aad24243`](https://github.com/mmm13921/fleur-overclock/commit/8fa0aad24243cab9cc8a8b2d00960208c53d0f51) — audit: verify MTK heavy-task dequeue accounting
- 2026-11-22 — [`33ea780a897c`](https://github.com/mmm13921/fleur-overclock/commit/33ea780a897c23ab4157b232aeab5de267899a4a) — sched: assert runqueue lock before delayed migration check
- 2026-11-22 — [`f02adeac810d`](https://github.com/mmm13921/fleur-overclock/commit/f02adeac810dd0c198cd576bbab22da837185025) — sched: requeue delayed workers on local wakeup
- 2026-11-22 — [`f998172b46d8`](https://github.com/mmm13921/fleur-overclock/commit/f998172b46d868d2fe1b3952ef6a60da37468339) — audit: cover delayed local workqueue wakeups
- 2026-11-22 — [`0b603748a2dc`](https://github.com/mmm13921/fleur-overclock/commit/0b603748a2dcee00286cb81a1d7c2507f28a3b7b) — sched: account delayed tasks in MTK heavy counters
- 2026-11-22 — [`e6e7e7444b67`](https://github.com/mmm13921/fleur-overclock/commit/e6e7e7444b678d6e17652ba74df66cb4e36f893f) — audit: verify MTK delayed heavy-task accounting
- 2026-11-22 — [`fa41c9f26b21`](https://github.com/mmm13921/fleur-overclock/commit/fa41c9f26b21176133c88c79307d8ac6fe1ee52b) — fix: match Fleux local wakeup indentation
- 2026-11-22 — [`a12291b26979`](https://github.com/mmm13921/fleur-overclock/commit/a12291b269791453fbde047f6b892c58e2d7ceaa) — sched: preserve uclamp accounting for delayed tasks
- 2026-11-22 — [`5d2a73428f0d`](https://github.com/mmm13921/fleur-overclock/commit/5d2a73428f0dab38c271cfcd11145e547a913954) — audit: verify delayed uclamp accounting
- 2026-11-22 — [`2d8c0250d247`](https://github.com/mmm13921/fleur-overclock/commit/2d8c0250d247379df118fb74222a9e08493626cf) — audit: fix uclamp newline matching
- 2026-11-22 — [`570e4fe9f435`](https://github.com/mmm13921/fleur-overclock/commit/570e4fe9f435c2f3c4619d1831ed3b2fdc6a6b96) — sched: preserve PSI state across delayed dequeue
- 2026-11-22 — [`c60fdb6b09c4`](https://github.com/mmm13921/fleur-overclock/commit/c60fdb6b09c43812b35018357d7abd293dac8a17) — audit: verify PSI delayed-state handling
- 2026-11-22 — [`6a8dbd524f13`](https://github.com/mmm13921/fleur-overclock/commit/6a8dbd524f13de7810a96b28e76e29f18f93f0df) — sched: update hrtick before delayed block completion
- 2026-11-22 — [`5994cbae0e21`](https://github.com/mmm13921/fleur-overclock/commit/5994cbae0e21b805de1349e56025ea76919b8625) — audit: verify hrtick cleanup for delayed dequeue
- 2026-11-22 — [`47582b14f04b`](https://github.com/mmm13921/fleur-overclock/commit/47582b14f04b47f3e0c9bb28c0e3d67e0027d672) — fix: restore original local wakeup patch anchor
- 2026-11-22 — [`732e51218d85`](https://github.com/mmm13921/fleur-overclock/commit/732e51218d85d85af82db1a2f8bdb4afc17beec8) — psi: preserve delayed task state on cgroup migration
- 2026-11-22 — [`5849c6ec86f2`](https://github.com/mmm13921/fleur-overclock/commit/5849c6ec86f23f10a1037ad428274340c579a46c) — audit: verify PSI cgroup migration state
- 2026-11-22 — [`46f62fa68a62`](https://github.com/mmm13921/fleur-overclock/commit/46f62fa68a62b0d093fe92e542172f39b66bc44c) — psi: avoid duplicate delayed dequeue state transitions
- 2026-11-22 — [`1b2a60829185`](https://github.com/mmm13921/fleur-overclock/commit/1b2a60829185bf995b2011e83ac3f1062c0f93fa) — audit: verify delayed PSI dequeue idempotence
- 2026-11-22 — [`f201885ac251`](https://github.com/mmm13921/fleur-overclock/commit/f201885ac25108c2c04fcff42e89ecc4836b68ff) — sched: guard delayed group throttle access
- 2026-11-22 — [`4746005d4be5`](https://github.com/mmm13921/fleur-overclock/commit/4746005d4be57459453d53c8e9de86bdedfc7d1e) — sched: clear delayed state on special dequeue
- 2026-11-22 — [`80af39041f8a`](https://github.com/mmm13921/fleur-overclock/commit/80af39041f8a2d80988c8f108c67c8b73a3685d6) — audit: verify special delayed dequeue cleanup
- 2026-11-22 — [`bb9276f506c2`](https://github.com/mmm13921/fleur-overclock/commit/bb9276f506c2460727fb5d2323ade387d553d934) — sched: refresh group runnable weights on throttle transitions
- 2026-11-22 — [`d17788f6e2f0`](https://github.com/mmm13921/fleur-overclock/commit/d17788f6e2f0bdb3fe928e100551d72012a0be9c) — audit: verify group weight refresh on throttling
- 2026-11-22 — [`456f3ad83071`](https://github.com/mmm13921/fleur-overclock/commit/456f3ad83071425ff87aa2f016e1599017511c39) — audit: fix throttle group weight newline matching
- 2026-11-22 — [`13a2099845b6`](https://github.com/mmm13921/fleur-overclock/commit/13a2099845b67d5df978e1e9f0f94beaeda6f23b) — sched: refresh EEVDF group slices on unthrottle
- 2026-11-22 — [`617cc969bd75`](https://github.com/mmm13921/fleur-overclock/commit/617cc969bd75c16bca5fc7a469a649345120a3d7) — audit: verify group slice refresh on unthrottle
- 2026-11-22 — [`4836bbcfaf21`](https://github.com/mmm13921/fleur-overclock/commit/4836bbcfaf210ca6e27e73fa4361cb1ad920266c) — sched: refresh parent group slices on throttle
- 2026-11-22 — [`86af00249ccb`](https://github.com/mmm13921/fleur-overclock/commit/86af00249ccba283e1bdb469c0a2590780b66437) — audit: verify parent group slice refresh on throttle
- 2026-11-22 — [`d4856817fe29`](https://github.com/mmm13921/fleur-overclock/commit/d4856817fe29601e32dddde60834551f0aa2d7e8) — ci: build full EEVDF porting branch
- 2026-11-22 — [`81ea9675174d`](https://github.com/mmm13921/fleur-overclock/commit/81ea9675174d89a4d8c2d44b1689ae2466ac1125) — fix: define delayed enqueue flag and use 4.19 task state
- 2026-11-22 — [`323710e7b4f1`](https://github.com/mmm13921/fleur-overclock/commit/323710e7b4f1a71103f0e9136d9f5ba7f6c6cc0f) — fix: match delayed enqueue macro definition
- 2026-11-22 — [`e3006c26ae28`](https://github.com/mmm13921/fleur-overclock/commit/e3006c26ae28de575a2df9658ae0daafc1e98d4c) — fix: adapt delayed dequeue helpers to 4.19 scheduler API
- 2026-11-22 — [`ddbd0f93ab20`](https://github.com/mmm13921/fleur-overclock/commit/ddbd0f93ab206782977b9672da0fa858f587afa9) — fix: declare CFS throttle helper before delayed dequeue
- 2026-11-22 — [`1efa8cfb9987`](https://github.com/mmm13921/fleur-overclock/commit/1efa8cfb9987168ba2a6326da84b3001f9a28841) — fix: adapt delayed migration guard to 4.19
- 2026-11-22 — [`2192589ed034`](https://github.com/mmm13921/fleur-overclock/commit/2192589ed0345eae459402d19e2b7ac7b827f7bc) — fix: align EEVDF audit with 4.19 migration guard

## Branch comparison

- `meys-eevdf-618-full`: 15 commits ahead of `meys-build38-boot-patches`, 0 behind; Layer 1 + dequeue-bool/custom-slice prerequisite snapshot.
- `meys-eevdf-618-porting`: 135 commits ahead of `meys-build38-boot-patches`, 0 behind; adds the expanded delayed-dequeue implementation and related audit/build fixes.
- These are branch-relative histories, not proof that all commits are present in `main`.

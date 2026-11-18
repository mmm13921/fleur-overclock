# Full official Linux 4.19.191 filesystem experiment

Target: Redmi Note 11S 4G / POCO M4 Pro 4G (fleur, MT6781).

This is an isolated experiment based on Fleux Linux 4.19.325. It replaces the complete `fs/` directory with the official Xiaomi MT6781 Linux 4.19.191 `fs/` tree pinned to commit `6f6b84e0e2fa8d474db66798a051ec1835257729`. The matching official `include/linux/f2fs_fs.h` and `include/trace/events/f2fs.h` are also copied so the F2FS on-disk and trace definitions stay aligned with that donor.

The replacement includes VFS core files, mount/remount handling, F2FS, EXT4, FUSE, OverlayFS, FAT-family filesystems, and the other files under `fs/`. In the official 4.19.191 donor, EROFS still lives under `drivers/staging/erofs`, not under `fs/erofs`; the experiment therefore also imports that complete official EROFS source tree, its `include/trace/events/erofs.h` header, and merges only the EROFS Kconfig/Makefile registration lines into Fleux's existing staging files. Imported EROFS files are byte-verified against the pinned donor. It deliberately does not merge Fleux's newer filesystem-specific changes back into the replaced `fs/` directory. The MT6781 DPMAIF suspend/resume guard is in `drivers/` and is kept separately. Because replacing all of `fs/` also removes Fleux's SUSFS core, the experiment keeps the dedicated `fs/susfs.c` implementation and its `obj-$(CONFIG_KSU_SUSFS) += susfs.o` Makefile entry, together with the matching `include/linux/susfs.h` header from the same Fleux source ref; the build audit records its declared SUSFS v2.x version instead of pinning an older release. The donor's two EXT4 fault callbacks are also adapted in `fs/ext4/inode.c`, and their declarations in `fs/ext4/ext4.h` are updated to return `vm_fault_t`, matching the Fleux 4.19.325 MM callback API. The two EXT4 `__vmalloc()` calls in `fs/ext4/super.c` are also adapted from the old three-argument form to the two-argument Fleux API. EXT4's old `e_reusable` field accesses in `fs/ext4/xattr.c` are mapped to the newer `MBE_REUSABLE_B` flag in `mb_cache_entry.e_flags` using `set_bit()`, `test_bit()`, and `clear_bit()`. The original 4.19.191 files are byte-verified before these explicit compatibility overlays are applied.  Fleux's complete `fs/kernfs/` subtree is preserved and audited against its packed `u64` kernfs ID (`generation:ino`) and xattr APIs. The Fleux `fs/nsfs.c` namespace pseudo-filesystem is also retained because its `ns_get_path()` API returns `int`, unlike the donor's pointer-returning implementation; the imported `fs/proc/namespaces.c` caller is adapted to that Fleux contract. Fleux's four-argument `do_faccessat()`, `faccessat2` wrapper, and matching private `filename_lookup()` declaration are also restored together so the SUSFS access hook matches the 4.19.325 syscall ABI. The imported legacy VFS mount path in `fs/super.c` is also adapted to Fleux's 4.19.325 interfaces: vendor-only `mount2`/`remount_fs2` callbacks are removed in favor of the existing `mount`/`remount_fs` callbacks, and legacy LSM mount-option handling is translated to `security_sb_eat_lsm_opts()`, `security_sb_set_mnt_opts()`, `security_sb_kern_mount()`, and `security_free_mnt_opts()`. This preserves SELinux option extraction/application without adding stale vendor-only members to Fleux's `struct file_system_type` or `struct super_operations`. The imported `do_remount()` path in `fs/namespace.c` is also adapted: it parses LSM options with `security_sb_eat_lsm_opts()`, validates them with `security_sb_remount()`, and frees the parsed options, instead of passing raw mount-option text to an API that expects parsed LSM state. The FUSE inode also receives a local `VM_MAX_READAHEAD=128` KiB fallback because Fleux 4.19.325 no longer exports that legacy MM macro; this preserves the official FUSE readahead limit without changing the global MM header. It then reapplies only the four FleuxSU inline-hook sites required by its build-time checker: `ksu_handle_execveat`, `ksu_handle_faccessat`, `ksu_handle_sys_read`, and `ksu_handle_stat`. Their source locations and SUSFS guards are checked by the post-build audit; VFS/F2FS and the other filesystem implementation files remain from the pinned Xiaomi donor.

## Important compatibility impact

This creates a mixed-version kernel: Fleux 4.19.325 outside `fs/`, with the official 4.19.191 implementation inside `fs/`. The official donor predates Fleux's newer `fs_context` VFS path and filesystem-specific KernelSU/Fleux changes. The complete `fs/kernfs/` subtree is deliberately retained from Fleux 4.19.325 because the donor implementation is incompatible with the Fleux `include/linux/kernfs.h` packed-u64 node ID and newer xattr APIs; kernfs is a shared pseudo-filesystem subsystem, not the Android userdata filesystem. Fleux's `fs/nsfs.c` is also retained to match the `int ns_get_path()` declaration in `include/linux/proc_ns.h`; the donor's `fs/proc/namespaces.c` is narrowly adapted to consume that return code and return `ERR_PTR(error)` as required by the procfs link callback. The Fleux four-argument `do_faccessat()` implementation and `faccessat2` wrapper are restored, and `fs/internal.h` receives the corresponding `filename_lookup()` declaration. Its donor definition in `fs/namei.c` is changed from `static` to external linkage, matching Fleux's exported helper so the call from `fs/open.c` links correctly. Replacing the tree may therefore cause compile/link incompatibilities or remove filesystem-side hooks. The build is intentionally isolated on this branch and published only as a prerelease candidate.

The workflow must pass source-tree identity checks, compile the full kernel, verify the gzip kernel plus appended DTB, and validate the AnyKernel3 ZIP before publishing. A successful CI build still cannot establish that HyperOS can mount and decrypt real `/data`, access all existing files, preserve app data, or behave correctly across reboot and suspend/resume.

Do not overwrite the known-good kernel or remove the recovery path. Flash only after the image is built successfully and keep the previous boot image available. If the phone cannot mount userdata or reports filesystem errors, restore the known-good boot image; do not format userdata.


### VFS fdtable API compatibility

The Xiaomi 4.19.191 fs/file.c implements the older dup_fd(oldf, int *errorp) contract. Fleux 4.19.325 declares dup_fd(oldf, struct fd_range *), returns failures through ERR_PTR(), calls it from kernel/fork.c with the range argument, and includes close_range support. The experiment therefore preserves Fleux's complete fs/file.c rather than trying to adapt only the function declaration. The source audit checks the function signature, helper, error-pointer paths, header declaration, and both fork call sites; the official donor byte-identity check explicitly excludes this compatibility file.

### NLS API compatibility

The imported NLS implementation is adapted to Fleux's `load_nls(const char *)` declaration by changing both `find_nls` and `load_nls` definitions to const-correct signatures.

### Legacy VFS mount API compatibility

The Xiaomi `fs/super.c` donor uses `mount2` and `remount_fs2` callback members plus the older `alloc_secdata()` / `security_sb_copy_data()` / three-argument `security_sb_kern_mount()` LSM API. Those members and helpers are not present in Fleux 4.19.325. The compatibility layer therefore keeps the donor's legacy `mount_fs()` and `do_remount_sb2()` flow but dispatches through Fleux's regular `mount` and `remount_fs` callbacks. SELinux mount options are extracted and applied using the current `security_sb_eat_lsm_opts()` and `security_sb_set_mnt_opts()` interfaces, followed by the current `security_sb_kern_mount()` permission hook, and released with `security_free_mnt_opts()`. The imported `namespace.c` remount path separately parses LSM options with `security_sb_eat_lsm_opts()`, validates them with `security_sb_remount()`, and frees them with `security_free_mnt_opts()`; raw option text is no longer passed as an opaque options pointer. A post-build source audit checks that no obsolete vendor-only callback or LSM helper remains and that remount uses the parsed Fleux LSM API.

### procfs VMA soft-dirty API compatibility

The official 4.19.191 `fs/proc/task_mmu.c` wraps the `VM_SOFTDIRTY` VMA-flag update in `vm_write_begin()` and `vm_write_end()`, which rely on `vm_sequence` in `struct vm_area_struct`. Fleux 4.19.325 does not provide that VMA field or those helper functions. The compatibility overlay therefore ports only this `clear_refs_write()` loop to the exact Fleux implementation: clear `VM_SOFTDIRTY` and refresh `vm_page_prot` while holding the existing `mmap_write_lock`. It does not add an incomplete seqcount ABI to the Fleux MM structures.


## CI failure and compatibility ledger (2026-11-17)

This section is the running record for the isolated experiment. “Patched” means the compatibility code or audit was added to the branch; it does **not** mean the device behavior or even the current full build has been validated. Each item remains pending the current complete CI run unless explicitly marked otherwise.

### Root causes found in earlier CI runs

| Area | Failure / incompatibility | Applied correction | Verification status |
|---|---|---|---|
| Official donor source audit | Comments and string literals containing legacy callback names caused false positives | Strip C comments and literals before checking executable callback references | Patched; current audit must pass |
| `fs/super.c` remount conversion | The script modified an in-memory copy, then a later helper re-read the original file and discarded the remount edit | Persist the transformed `fs/super.c` before the next independent replacement | Patched in `73cfc40799dc985af20b1ce4f988735d7d140cf3`; current build must pass |
| VFS mount callbacks / LSM | Xiaomi-only `mount2` / `remount_fs2`, old secdata helpers, and old 3-argument `security_sb_kern_mount()` do not match Fleux 4.19.325 | Route through Fleux `mount` / `remount_fs` and translate LSM option parsing/application/freeing to current APIs | Patched; compile and runtime SELinux behavior pending |
| Namespace pseudo-filesystem | Donor `ns_get_path()` return type differs from Fleux API | Keep Fleux `fs/nsfs.c`; adapt proc namespace caller to the integer return contract and `ERR_PTR()` | Patched; compile pending |
| procattr LSM API | Donor calls 3-argument `security_getprocattr` / `security_setprocattr`, Fleux expects 4 arguments | Supply the Fleux selector argument (`NULL`) | Patched; compile pending |
| faccessat ABI / SUSFS | Donor `do_faccessat()` has 3 arguments; Fleux uses 4 and has `faccessat2`; donor `filename_lookup()` is static and undeclared to the caller | Restore Fleux 4-argument implementation and `faccessat2`, declare `filename_lookup()` in `fs/internal.h`, and use external linkage in `fs/namei.c` | Patched; compile/link pending |
| `fs/stat.c` filename lookup | `implicit declaration of function 'filename_lookup'` | Include `fs/internal.h` in `fs/stat.c`; retain the Fleux declaration and external definition | Patched in `6fbcd9bab2dfd0a80da14f6cbdb407dca0c2369a`; Run #89 compiling |
| Audit script ordering | The audit referenced `stat_source` before loading it | Load `fs/stat.c` before evaluating the declaration/include checks | Patched in `6fbcd9bab2dfd0a80da14f6cbdb407dca0c2369a`; Run #89 compiling |
| `kernfs` API | Donor kernfs does not match Fleux packed `u64` node ID and xattr interfaces | Preserve Fleux `fs/kernfs/` and audit the required ABI | Patched; audit/build pending |
| procfs VMA soft-dirty | Donor `vm_write_begin/end` relies on `vm_sequence`, absent from Fleux VMA | Port the operation to Fleux's `mmap_write_lock` implementation without importing a partial seqcount ABI | Patched; compile/runtime pending |
| EXT4 fault callbacks | Donor callback return types conflict with Fleux MM callback type | Convert the two callbacks and declarations to `vm_fault_t` | Patched; compile pending |
| EXT4 allocation API | Donor uses obsolete three-argument `__vmalloc()` | Convert the two calls to Fleux two-argument API | Patched; compile pending |
| EXT4 mbcache | Donor accesses removed `e_reusable` member | Map reusable state to `MBE_REUSABLE_B` in `e_flags` using bit operations | Patched; compile pending |
| FUSE readahead | Donor references legacy `VM_MAX_READAHEAD` absent from Fleux MM headers | Add a local fallback with the official 128 KiB limit | Patched; compile pending |
| NLS | Donor definitions are not const-correct for Fleux `load_nls(const char *)` declaration | Make `find_nls` and `load_nls` definitions const-correct | Patched; compile pending |
| `fs/exec.c` VMA initialization | Official donor calls undefined `INIT_VMA(vma)`; Fleux 4.19.325 has no such helper or speculative-page-fault VMA fields, and its `vm_area_alloc()` already calls `vma_init(vma, mm)` | Remove the donor-only redundant `INIT_VMA(vma)` call; assert Fleux `kernel/fork.c` uses `vma_init()` and the donor call is absent | Compatibility overlay added; first attempt was blocked by an over-escaped source anchor in the script, corrected after Run #93; compile pending |

### CI / release process corrections

- The workflow previously used `cancel-in-progress: true`, allowing a new push to cancel the previous validation run. Changed to `false` in commit `dbe030a47a422d1a6597e7507265f281ac3ae78a` so an active build is not killed merely because another commit is pushed. GitHub may queue the newer run in the same concurrency group.
- Every result must be checked against the current experiment branch HEAD SHA. A green run for an older SHA is not proof that the latest source passed.
- Release remains prerelease-only and isolated to this experiment. Do not promote it as stable based only on compilation.

### Current validation snapshot

- Last checked branch commit before the workflow concurrency-only change: `6fbcd9bab2dfd0a80da14f6cbdb407dca0c2369a`.
- Branch HEAD at the time of this snapshot: `0ce8daacf7ca4ad3237effcde6e37370807209b2`.
- Run #89: [GitHub Actions](https://github.com/mmm13921/fleur-overclock/actions/runs/44086083891), job `134048795343`, completed with compile failure at `fs/exec.c:317`: implicit declaration of `INIT_VMA`.
- The failure was traced to a donor-only VMA initializer absent from Fleux 4.19.325. Fleux `vm_area_alloc()` calls `vma_init(vma, mm)`, so the extra donor call is removed by an explicit compatibility overlay and guarded by the build audit.
- Run #92: [GitHub Actions](https://github.com/mmm13921/fleur-overclock/actions/runs/44087689080) failed at the original `INIT_VMA` compile error.
- Run #93: [GitHub Actions](https://github.com/mmm13921/fleur-overclock/actions/runs/44089137400) stopped before compilation because the new compatibility script used an over-escaped Python string pattern and did not match the literal tab/newline source anchor. The pattern is corrected to Python's single escaped tab/newline form; next run must confirm the overlay and continue into compilation.
- Dependency installation and checksum-verified Clang r563880c installation completed successfully in both runs.
- AnyKernel3 packaging, prerelease publication, and artifact upload have not yet been validated for the latest source.
- No successful compile, AnyKernel ZIP, release artifact, phone boot, userdata mount/read/write, radio stability, suspend/resume, or HyperOS runtime result is claimed here.

### Required acceptance gates

1. Source donor identity and all compatibility audits pass.
2. Full kernel compile exits successfully for the exact latest branch SHA.
3. Kernel image and appended DTB checks pass.
4. AnyKernel3 ZIP integrity and required installer-file checks pass.
5. Prerelease and checksums are published for that same SHA.
6. Device testing is performed separately with the known-good boot image retained. Verify boot, encrypted `/data` mount, read/write and app data integrity, modem registration/signal after long idle, reboot, and suspend/resume. Never format userdata as a troubleshooting step for this experiment.


- Follow-up commit after the ledger was added: `f6472348dbfbdb29b63ed16ba7df580d2a248ffc` (this document update). The workflow-only commit `dbe030a47a422d1a6597e7507265f281ac3ae78a` produced Run #90, which GitHub reports as cancelled before a job was created. Run #89 remains an older-SHA build and is not validation of either follow-up commit.


### Run #93 follow-up
- Run #93 stopped before compilation because the VMA overlay's source-anchor pattern was over-escaped. The Python source now uses single escape sequences for the tab and newline, so it matches the literal source line in donor `fs/exec.c`.
- Next run is the first valid test of the VMA overlay; compile, packaging, release and device boot remain unverified.


### Run #95: VFS dcache lockdep API mismatch
- The full official 4.19.191 `fs/` replacement and identity audit passed. Compilation stopped at `fs/dcache.c:1281`: donor code called `spin_release(&dentry->d_lock.dep_map, 1, _RET_IP_)`, but Fleux 4.19.325 defines `spin_release(lock, ip)` and `lock_release(lock, ip)`.
- Corrected the call by removing only the obsolete middle argument `1`, preserving `_RET_IP_` as the instruction pointer: `spin_release(&dentry->d_lock.dep_map, _RET_IP_)`.
- Added a source compatibility overlay and audit assertions against Fleux `include/linux/lockdep.h`. This fix is pending the next complete CI compile.
- Run #95: [GitHub Actions](https://github.com/mmm13921/fleur-overclock/actions/runs/44091603944), SHA `74323f788733620b531f8ce3235b016c5311da4d`, failed at this compile error; no package or release was produced.


### Run #98: VFS fdtable dup_fd API mismatch
- Run #98 reached compilation and failed at fs/file.c:272 because the official donor defines dup_fd(struct files_struct *, int *errorp), while Fleux 4.19.325 declares dup_fd(struct files_struct *, struct fd_range *). Fleux callers also expect ERR_PTR() failures and the Fleux implementation provides close_range support.
- Preserve the complete Fleux fs/file.c during the filesystem replacement. The source audit now checks the retained implementation against include/linux/fdtable.h and both kernel/fork.c call sites; official donor blob verification excludes only this explicit compatibility file in addition to prior preserved files.
- Run #98: [GitHub Actions](https://github.com/mmm13921/fleur-overclock/actions/runs/44219548713), SHA 84ec91ca7fde0cf1dd6575eb5b26168cea3e90f6, failed during compilation; no image, AnyKernel ZIP, or release was produced.

### Runs #96 and #97: SUSFS version guard
- The Fleux upstream `lineage-24.0` branch advanced its SUSFS header from `v2.3.0` to `v2.4.0` (upstream source commit `e2d900276a445fc9e31592c80df89a6f5e24175d`). Runs #96 and #97 stopped during filesystem replacement preflight because the experiment script still hard-coded `v2.3.0`; neither reached compilation.
- Updated the apply and post-build audit scripts to parse and validate a semantic `v2.x.y` value from `include/linux/susfs.h`, then record and cross-check that exact version in the reports.
- Run #96: [GitHub Actions](https://github.com/mmm13921/fleur-overclock/actions/runs/44217340788), SHA `1defb3813938f0115bc042385deb8bf6769b230e`, failed at the stale v2.3.0 guard.
- Run #97: [GitHub Actions](https://github.com/mmm13921/fleur-overclock/actions/runs/44217431650), SHA `4061a957457a0608a5123c0a7752147388c5e2ce`, failed at the same stale guard.


### Run #102: namespace read-only API return-type mismatch
- Run #102 used the corrected fdtable commit and reached full compilation. It stopped at `fs/namespace.c:249`: the official 4.19.191 donor defines `int __mnt_is_readonly(struct vfsmount *)`, while Fleux 4.19.325 `include/linux/mount.h` declares `extern bool __mnt_is_readonly(struct vfsmount *)`.
- Confirmed the original Fleux 4.19.325 implementation returns `bool` and evaluates the same mount-read-only condition. The compatibility overlay now changes only the imported definition's return type from `int` to `bool`; the official legacy mount/remount implementation remains in place.
- Added a post-replacement source audit that checks the Fleux header declaration, the final namespace definition, and its read-only condition, plus a manifest entry for this compatibility overlay.
- Run #102: [GitHub Actions](https://github.com/mmm13921/fleur-overclock/actions/runs/44221481889), SHA `4d8a4c8824b4332eb3ff90b4b575ac5d658a014c`, failed on this compile error. No image, AnyKernel ZIP, or release was produced. The next run must validate the bool API fix.

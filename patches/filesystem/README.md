# Filesystem, F2FS and Project ID compatibility

This folder archives the filesystem/mount backport and F2FS Project ID compatibility patch series, together with the related active patch applicators.

## Scope
- Official Fleur 4.19.191 filesystem/mount compatibility backport.
- F2FS inode Project ID metadata compatibility.
- FUSE passthrough/coherency compatibility helper.

Project ID metadata compatibility is not equivalent to project-quota enforcement. Do not enable on-disk quota features or reformat userdata based solely on these patches.

The older numbered patch archive remains under `patches/apply/`. Active build scripts remain under `scripts/`; keep both archive copies synchronized.

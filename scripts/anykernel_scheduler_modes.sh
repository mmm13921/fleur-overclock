#!/sbin/sh
# AnyKernel3 installer for Fleux 4.19 MT6781 CPU scheduler modes.
properties() { '
kernel.string=Fleux CPU Modes - HMP EAS Hybrid (official 4.14 mode logic)
do.devicecheck=1
do.modules=0
do.systemless=1
do.cleanup=1
do.cleanuponabort=0
device.name1=fleur
device.name2=miel
device.name3=missi
'; }
BLOCK=auto;
IS_SLOT_DEVICE=auto;
RAMDISK_COMPRESSION=auto;
PATCH_VBMETA_FLAG=auto;
. tools/ak3-core.sh;
ui_print " ";
ui_print "Fleux CPU Modes: Official Fleur 4.14 logic backport";
ui_print "Target: Redmi Note 11S 4G / POCO M4 Pro 4G / MT6781";
ui_print "Runtime selector: /proc/sys/kernel/sched_cpu_mode";
ui_print "0 = HMP; 1 = EAS (default); 2 = Hybrid";
ui_print "HMP uses a PELT/util_est adaptation, not full WALT HMP";
ui_print "Experimental: retain a known-good boot image";
ui_print " ";
dump_boot;
write_boot;

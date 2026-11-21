#!/sbin/sh
# AnyKernel3 installer for Fleux 4.19 MT6781 CPU scheduler modes.
properties() { '
kernel.string=Fleux Scheduler Modes - HMP EAS Hybrid for fleur
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
ui_print "Fleux CPU Scheduler Modes";
ui_print "Target: Redmi Note 11S 4G / POCO M4 Pro 4G / MT6781";
ui_print "Runtime selector: /proc/sys/kernel/sched_cpu_mode";
ui_print "0 = HMP-style; 1 = EAS; 2 = Hybrid (default)";
ui_print "Hybrid = EAS normally, HMP-style placement under overutilization";
ui_print "Experimental scheduler port; keep a known-good boot image";
ui_print " ";
dump_boot;
write_boot;

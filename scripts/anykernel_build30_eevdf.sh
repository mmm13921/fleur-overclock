#!/sbin/sh
# AnyKernel3 installer for Meys 4.19 MT6781 CPU scheduler modes.
properties() { '
kernel.string=Meys Build 30 EEVDF Linux 6.18 layer 1 / MT6781
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
ui_print "Meys Build 30 + EEVDF Linux 6.18 layer 1";
ui_print "Target: Redmi Note 11S 4G / POCO M4 Pro 4G / MT6781";
ui_print "Runtime selector: /proc/sys/kernel/sched_cpu_mode";
ui_print "CPU modes: 0 = HMP; 1 = EAS; 2 = Hybrid";
ui_print "EEVDF: protected slice, min-slice tree, relative deadline";
ui_print "DELAY_DEQUEUE and DELAY_ZERO are not included yet";
ui_print "Experimental: retain a known-good boot image";
ui_print " ";
dump_boot;
write_boot;

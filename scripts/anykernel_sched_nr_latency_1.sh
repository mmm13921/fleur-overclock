#!/sbin/sh
# AnyKernel3 installer for Fleux sched_nr_latency=1 / MT6781.
properties() { '
kernel.string=Fleux Scheduler NR1 - fleur
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
ui_print "Fleux Scheduler NR1";
ui_print "Target: Redmi Note 11S 4G / POCO M4 Pro 4G / MT6781";
ui_print "sched_nr_latency: fixed at 1";
ui_print "Kernel image: Image.gz";
ui_print "Boot header v2 DTB: dtb.img";
ui_print "Existing separate DTBO partition: preserved";
ui_print "CPU, GPU, CCI OPPs and voltages: unchanged";
ui_print "Thermal and watchdog protections: unchanged";
ui_print " ";
dump_boot;
write_boot;

#!/sbin/sh
# AnyKernel3 installer for Fleux SSPM thermal-throttle-off diagnostic test / MT6781.
properties() { '
kernel.string=Fleux SSPM Thermal Throttle OFF Test - fleur
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
ui_print "Fleux SSPM Thermal Throttle OFF - TEST";
ui_print "Target: Redmi Note 11S 4G / POCO M4 Pro 4G / MT6781";
ui_print "SSPM thermal throttling: disabled at thermal init (diagnostic)";
ui_print "AP thermal policy: unchanged";
ui_print "LVTS/RGU hardware thermal reset: preserved";
ui_print "Software sysrst cooler and watchdog: unchanged";
ui_print "CPU, GPU, CCI OPPs and voltages: unchanged";
ui_print "Existing separate DTBO partition: preserved";
ui_print " ";
dump_boot;
write_boot;

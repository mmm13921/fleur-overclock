#!/sbin/sh
# AnyKernel3 installer for Fleux GPU OC 1100MHz / MT6781.
properties() { '
kernel.string=Fleux GPU OC - 1100MHz for fleur
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
ui_print "Fleux GPU OC - 1100MHz";
ui_print "Target: Redmi Note 11S 4G / POCO M4 Pro 4G / MT6781";
ui_print "Mali GPU max OPP: 1100 MHz";
ui_print "CPU and CCI frequencies: stock";
ui_print "Thermal, battery, PBM and watchdog protections: retained";
ui_print " ";
dump_boot;
write_boot;

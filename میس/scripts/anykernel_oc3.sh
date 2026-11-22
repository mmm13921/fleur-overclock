#!/sbin/sh
# AnyKernel3 installer for Fleux OC3 2.2GHz / MT6781.
properties() { '
kernel.string=Fleux OC3 - 2.2GHz for fleur
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
ui_print "Fleux OC3 - 2.2GHz";
ui_print "Target: Redmi Note 11S 4G / POCO M4 Pro 4G / MT6781";
ui_print "Accepted product IDs: fleur, miel, missi";
ui_print "Big cluster CPU6 + CPU7: 2200 MHz top OPP";
ui_print "SSPM/PPM thermal throttling and IMAX protection: enabled";
ui_print " ";
dump_boot;
write_boot;

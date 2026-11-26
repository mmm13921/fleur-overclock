#!/sbin/sh
# AnyKernel3 installer for the isolated Fleux V12 stability test.
properties() { '
kernel.string=HMP-BUILD
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
ui_print "HMP-BUILD";
ui_print "Target: Redmi Note 11S 4G / POCO M4 Pro 4G / MT6781";
ui_print "Kernel: HMP-BUILD";
ui_print "Keeps CONFIGFS_FS enabled; CONFIG_SDCARD_FS disabled";
ui_print "Keeps FUSE passthrough and F2FS support";
ui_print "Experimental: preserve a known-good boot image";
ui_print " ";
dump_boot;
write_boot;

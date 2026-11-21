#!/sbin/sh
# AnyKernel3 installer for the isolated F2FS Project ID compatibility test.
properties() { '
kernel.string=Meys VX F2FS Project ID Compatibility Test
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
ui_print "Meys VX F2FS Project ID compatibility test";
ui_print "Target: Redmi Note 11S 4G / fleur / MT6781";
ui_print "Stores inode project IDs when EXTRA_ATTR exists";
ui_print "Does not enable quota enforcement without PRJQUOTA";
ui_print "Experimental: retain a known-good boot image";
ui_print " ";
dump_boot;
write_boot;

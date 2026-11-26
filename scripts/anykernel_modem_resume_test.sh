#!/sbin/sh
# AnyKernel3 installer for the experimental MT6781 modem resume guard.
properties() { '
kernel.string=Meys V12 Modem Resume Guard (experimental)
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
ui_print "Meys V12 Modem Resume Guard";
ui_print "Target: Redmi Note 11S 4G / fleur / MT6781";
ui_print "Test: CCCI modem state-aware DPMAIF syscore resume";
ui_print "Restore allowed only for modem READY or EXCEPTION";
ui_print "Experimental kernel: keep a known-good boot image";
ui_print " ";
dump_boot;
write_boot;

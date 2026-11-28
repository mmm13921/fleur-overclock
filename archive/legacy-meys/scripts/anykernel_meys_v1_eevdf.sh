#!/sbin/sh
# AnyKernel3 installer for Meys V1 EEVDF / MT6781.
properties() { '
kernel.string=Meys V1 EEVDF - Linux 6.18 scheduler backport
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
ui_print "Meys V1 EEVDF";
ui_print "Target: Redmi Note 11S 4G / POCO M4 Pro 4G / MT6781";
ui_print "Kernel: Linux 4.19.325-Meys-V1";
ui_print "EEVDF: protected slices, min-slice tree, short-slice preemption";
ui_print "Relative virtual deadline preservation and custom task slices";
ui_print "Experimental build; preserve a known-good boot image";
ui_print " ";
dump_boot;
write_boot;

#!/sbin/sh
# AnyKernel3 installer for Fleux HyperOS compatibility candidate / MT6781.
properties() { '
kernel.string=Fleux HyperOS Compatibility Candidate for fleur
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
ui_print "Fleux HyperOS Compatibility Candidate";
ui_print "Target: Redmi Note 11S 4G / POCO M4 Pro 4G / MT6781";
ui_print "NoMount and SUSFS path/mount/stat/open-redirection features disabled"; 
ui_print "KernelSU inline hook mode retained for Non-GKI 4.19";
ui_print "KernelSU remains enabled";
ui_print "MT6781 CCCI/DPMAIF suspend-resume callbacks guarded";
ui_print "SEA 4.19.325 VFS and F2FS mount/data fixes included";
ui_print "Stock CPU/GPU OPP and thermal protections retained";
ui_print "Experimental build: validate modem and filesystem behaviour on-device";
ui_print " ";
dump_boot;
write_boot;

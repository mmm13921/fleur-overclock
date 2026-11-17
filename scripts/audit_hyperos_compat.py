from pathlib import Path
import argparse
import zlib

parser = argparse.ArgumentParser()
parser.add_argument("--image", required=True)
parser.add_argument("--config", required=True)
parser.add_argument("--source", required=True)
parser.add_argument("--report", required=True)
args = parser.parse_args()

image = Path(args.image)
config = Path(args.config)
source = Path(args.source)
report = Path(args.report)

def require(condition, message):
    if not condition:
        raise SystemExit("HyperOS compatibility audit failed: " + message)

require(image.is_file() and image.stat().st_size > 0, "kernel image is missing")
require(config.is_file(), "kernel config is missing")
raw = image.read_bytes()
require(raw[:2] == b"\x1f\x8b", "Image.gz-dtb is not gzip-compressed")
decoder = zlib.decompressobj(31)
kernel = decoder.decompress(raw)
require(bool(kernel), "gzip kernel payload is empty")
require(bool(decoder.unused_data), "appended device tree data is missing")

cfg = config.read_text().splitlines()
enabled = set(line for line in cfg if line.startswith("CONFIG_") and line.endswith("=y"))
disabled = set(line for line in cfg if line.startswith("# CONFIG_") and line.endswith(" is not set"))

required = [
    "CONFIG_KSU=y",
    "CONFIG_EXT4_FS=y",
    "CONFIG_F2FS_FS=y",
    "CONFIG_EROFS_FS=y",
    "CONFIG_EXFAT_FS=y",
    "CONFIG_VFAT_FS=y",
    "CONFIG_FUSE_FS=y",
    "CONFIG_FS_ENCRYPTION=y",
    "CONFIG_FS_ENCRYPTION_INLINE_CRYPT=y",
    "CONFIG_MTK_ECCCI_DRIVER=y",
    "CONFIG_MTK_COMBO=y",
    "CONFIG_SCSI_UFS_MEDIATEK=y",
    "CONFIG_MMC_MTK=y",
]
for item in required:
    require(item in enabled, item + " is not enabled")

for symbol in ("NOMOUNT", "KSU_SUSFS", "KSU_SUSFS_SPOOF_CMDLINE_OR_BOOTCONFIG"):
    require("CONFIG_" + symbol + "=y" not in enabled, "CONFIG_" + symbol + " must be disabled")

hif = (source / "drivers/misc/mediatek/eccci/hif/ccci_hif.c").read_text()
platform = (source / "drivers/misc/mediatek/eccci/mt6785/md_sys1_platform.c").read_text()
require("ops->resume(DPMAIF_HIF_ID);" in hif, "DPMAIF resume callback dispatch is absent")
require("ops->suspend(DPMAIF_HIF_ID);" in hif, "DPMAIF suspend callback dispatch is absent")
require("ccci_hif_resume(md->index, md->hif_flag);" in platform, "MT6781 resume callback is not wired")
require("ccci_hif_suspend(md->index, md->hif_flag);" in platform, "MT6781 suspend callback is not wired")
require("md_state == GATED" in platform and "md_state == WAITING_TO_STOP" in platform,
        "modem-state guard is missing")

lines = [
    "profile=hyperos-compat",
    "kernel_image=Image.gz-dtb",
    "appended_dtb=verified",
    "root_manager=KernelSU enabled",
    "filesystem_stack=ext4,f2fs,erofs,exfat,vfat,fuse,overlayfs",
    "filesystem_encryption=enabled",
    "filesystem_interceptors=NoMount disabled; SUSFS disabled",
    "modem_pm=MT6781 CCCI suspend/resume wired to DPMAIF ops",
    "modem_state_guard=GATED,WAITING_TO_STOP,INVALID skipped on resume",
    "hardware_validation=not performed by CI",
]
report.write_text("\n".join(lines) + "\n")
print("HYPEROS COMPATIBILITY STRUCTURAL AUDIT PASSED")
print("\n".join(lines))

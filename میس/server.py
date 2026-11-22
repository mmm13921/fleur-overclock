from __future__ import annotations

import hmac
import os
import re
from typing import Any
from urllib.parse import quote

import httpx
from fastmcp import FastMCP

REPOSITORY = "mmm13921/fleur-kernel-buildb"
WORKFLOW_FILE = "build-fleux.yml"
WORKFLOW_REF = os.getenv("BUILDER_WORKFLOW_REF", "main")
SOURCE_PROJECT_ID = 87145973
SOURCE_DEFAULT_REF = "lineage-24.0"
SOURCE_BASE = "https://gitlab.com/api/v4/projects"
GITHUB_API = "https://api.github.com"

ALLOWED_SOURCE_FILES = {
    "README.md",
    "arch/arm64/configs/fleur_defconfig",
    "arch/arm64/boot/dts/mediatek/mt6781.dts",
    "drivers/misc/mediatek/base/power/cpufreq_v1/src/mach/mt6781/mtk_cpufreq_opp_table.h",
    "drivers/misc/mediatek/base/power/cpufreq_v1/src/mach/mt6781/mtk_cpufreq_opp_pv_table.h",
    "drivers/misc/mediatek/base/power/cpufreq_v1/src/mtk_cpufreq_hybrid.c",
}

REF_RE = re.compile(r"^[A-Za-z0-9._/-]{1,128}$")
mcp = FastMCP("Fleux Kernel Builder")


def _require_github_token() -> str:
    token = os.getenv("GH_TOKEN", "").strip()
    if not token:
        raise RuntimeError("GH_TOKEN is not configured on the MCP host.")
    return token


def _github_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_require_github_token()}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _validate_ref(ref: str) -> str:
    if not REF_RE.fullmatch(ref) or ".." in ref or "//" in ref or ref.startswith("-"):
        raise ValueError("Invalid Git ref.")
    return ref


async def _gitlab_raw(path: str, ref: str = SOURCE_DEFAULT_REF) -> str:
    _validate_ref(ref)
    if path not in ALLOWED_SOURCE_FILES:
        raise ValueError("This path is not in the source-file allowlist.")
    encoded_path = quote(path, safe="")
    url = f"{SOURCE_BASE}/{SOURCE_PROJECT_ID}/repository/files/{encoded_path}/raw"
    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        response = await client.get(url, params={"ref": ref})
        response.raise_for_status()
        return response.text


@mcp.tool
def project_info() -> dict[str, Any]:
    """Return the pinned Fleux source, target device and build output contract."""
    return {
        "builder_repository": REPOSITORY,
        "source_repository": "https://gitlab.com/daliboss/fleux",
        "source_ref_default": SOURCE_DEFAULT_REF,
        "device_config": "fleur_defconfig",
        "architecture": "arm64",
        "documented_toolchain": "Android LLVM clang-r563880c",
        "expected_output": "Image.gz-dtb",
        "flashable_zip": False,
        "workflow_file": WORKFLOW_FILE,
    }


@mcp.tool
async def read_kernel_source_file(path: str, ref: str = SOURCE_DEFAULT_REF) -> str:
    """Read one allowlisted file from the public Fleux GitLab source repository."""
    return await _gitlab_raw(path, ref)


@mcp.tool
async def inspect_cpu_opp_tables(ref: str = SOURCE_DEFAULT_REF) -> dict[str, Any]:
    """Inspect the source CPU OPP, voltage and SSPM evidence without modifying it."""
    opp_path = "drivers/misc/mediatek/base/power/cpufreq_v1/src/mach/mt6781/mtk_cpufreq_opp_table.h"
    pv_path = "drivers/misc/mediatek/base/power/cpufreq_v1/src/mach/mt6781/mtk_cpufreq_opp_pv_table.h"
    dts_path = "arch/arm64/boot/dts/mediatek/mt6781.dts"
    hybrid_path = "drivers/misc/mediatek/base/power/cpufreq_v1/src/mtk_cpufreq_hybrid.c"
    config_path = "arch/arm64/configs/fleur_defconfig"

    opp, pv, dts, hybrid, config = await __import__("asyncio").gather(
        _gitlab_raw(opp_path, ref),
        _gitlab_raw(pv_path, ref),
        _gitlab_raw(dts_path, ref),
        _gitlab_raw(hybrid_path, ref),
        _gitlab_raw(config_path, ref),
    )

    freq_macros = [
        line.strip() for line in opp.splitlines()
        if "CPU_DVFS_FREQ" in line and line.lstrip().startswith("#define")
    ]
    vproc2_macros = [
        line.strip() for line in opp.splitlines()
        if "CPU_DVFS_VOLT" in line and "VPROC2" in line and line.lstrip().startswith("#define")
    ]
    dt_lines = dts.splitlines()
    try:
        start = next(i for i, line in enumerate(dt_lines) if "cluster1_opp:" in line)
        end = next(i for i in range(start + 1, len(dt_lines)) if "cpus {" in dt_lines[i])
        big_cluster_dts = "\n".join(dt_lines[start:end]).strip()
    except StopIteration:
        big_cluster_dts = "Could not isolate cluster1_opp in this ref."

    sspm_config = [
        line.strip() for line in config.splitlines()
        if "SSPM" in line.upper() or "MCUPM" in line.upper()
    ]
    sspm_hybrid = [
        f"{index + 1}: {line.strip()}" for index, line in enumerate(hybrid.splitlines())
        if "SSPM" in line.upper() or "IPI_DVFS_INIT_PTBL" in line
    ]

    return {
        "source_repository": "https://gitlab.com/daliboss/fleux",
        "source_ref": ref,
        "device_tree_big_cluster_opp": big_cluster_dts,
        "cpu_frequency_macros": freq_macros,
        "vproc2_voltage_macros": vproc2_macros,
        "opp_pv_table_header": [
            line.strip() for line in pv.splitlines()
            if "OPP_6781" in line or "Freq, Vproc" in line
        ],
        "sspm_mcupm_config_lines": sspm_config,
        "sspm_hybrid_dvfs_lines": sspm_hybrid[:120],
        "safety_note": (
            "This is read-only source inspection. It does not establish that OPP "
            "changes are safe or that SSPM firmware accepts new operating points."
        ),
    }


@mcp.tool
async def start_baseline_build(source_ref: str = SOURCE_DEFAULT_REF) -> dict[str, Any]:
    """Dispatch the baseline, unmodified fleur_defconfig build on GitHub Actions."""
    source_ref = _validate_ref(source_ref)
    if source_ref != SOURCE_DEFAULT_REF:
        raise ValueError(
            f"Only the reviewed source ref {SOURCE_DEFAULT_REF!r} is enabled for now."
        )

    url = f"{GITHUB_API}/repos/{REPOSITORY}/actions/workflows/{WORKFLOW_FILE}/dispatches"
    payload = {"ref": WORKFLOW_REF, "inputs": {"source_ref": source_ref}}
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, headers=_github_headers(), json=payload)
        if response.status_code != 204:
            raise RuntimeError(
                f"GitHub workflow dispatch failed ({response.status_code}): "
                f"{response.text[:1200]}"
            )
    return {
        "dispatched": True,
        "workflow": WORKFLOW_FILE,
        "workflow_ref": WORKFLOW_REF,
        "source_ref": source_ref,
        "message": "GitHub accepted the workflow_dispatch request. Check latest_build_status for the run.",
    }


@mcp.tool
async def latest_build_status(limit: int = 5) -> dict[str, Any]:
    """Return the latest GitHub Actions build runs and their status."""
    limit = max(1, min(int(limit), 20))
    url = f"{GITHUB_API}/repos/{REPOSITORY}/actions/runs"
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            url, headers=_github_headers(), params={"per_page": limit}
        )
        response.raise_for_status()
        data = response.json()
    runs = [
        {
            "id": run.get("id"),
            "name": run.get("name"),
            "display_title": run.get("display_title"),
            "status": run.get("status"),
            "conclusion": run.get("conclusion"),
            "branch": run.get("head_branch"),
            "commit": run.get("head_sha"),
            "html_url": run.get("html_url"),
            "created_at": run.get("created_at"),
            "updated_at": run.get("updated_at"),
        }
        for run in data.get("workflow_runs", [])
    ]
    return {"total_count": data.get("total_count", 0), "runs": runs}


@mcp.tool
async def list_build_artifacts(run_id: int) -> dict[str, Any]:
    """List downloadable artifacts associated with a GitHub Actions run."""
    if run_id <= 0:
        raise ValueError("run_id must be a positive integer.")
    url = f"{GITHUB_API}/repos/{REPOSITORY}/actions/runs/{run_id}/artifacts"
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url, headers=_github_headers())
        response.raise_for_status()
        data = response.json()
    artifacts = [
        {
            "id": item.get("id"),
            "name": item.get("name"),
            "size_in_bytes": item.get("size_in_bytes"),
            "expired": item.get("expired"),
            "expires_at": item.get("expires_at"),
            "archive_download_url": item.get("archive_download_url"),
        }
        for item in data.get("artifacts", [])
    ]
    return {"total_count": data.get("total_count", 0), "artifacts": artifacts}


class BearerTokenGuard:
    """Small ASGI guard; protect MCP requests while allowing a public health probe."""

    def __init__(self, app: Any, token: str) -> None:
        self.app = app
        self.token = token

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        if path == "/health":
            body = b'{"status":"ok"}'
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())],
            })
            await send({"type": "http.response.body", "body": body})
            return

        auth = b""
        for key, value in scope.get("headers", []):
            if key.lower() == b"authorization":
                auth = value
                break
        expected = f"Bearer {self.token}".encode()
        if not self.token or not hmac.compare_digest(auth, expected):
            body = b'{"error":"unauthorized"}'
            await send({
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                    (b"www-authenticate", b"Bearer"),
                ],
            })
            await send({"type": "http.response.body", "body": body})
            return
        await self.app(scope, receive, send)


_mcp_app = mcp.http_app(path="/mcp")
app = BearerTokenGuard(_mcp_app, os.getenv("MCP_AUTH_TOKEN", "").strip())

from __future__ import annotations

"""
sync_engine.py
TurboSync helper layer for EMBORGANIZER v4.8.

This module keeps library/cache resync work outside streamlit_app.py so the UI
stays clean as IMGS grows. The native C++ helper is optional; when a compiler is
not available, every function safely falls back to Python.
"""

import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

SYNC_ENGINE_VERSION = "TurboSync v1 • C++ dedupe helper + Python fallback"
BASE_DIR = Path(__file__).resolve().parent
CPP_SOURCE = BASE_DIR / "sync_native.cpp"
CPP_BINARY_NAME = "sync_native.exe" if os.name == "nt" else "sync_native"
CACHE_DIR = BASE_DIR / ".turboemb"
CACHE_BINARY = CACHE_DIR / CPP_BINARY_NAME
SYNC_CPP_ENABLED = os.environ.get("TURBO_SYNC_CPP", "1").lower() not in {"0", "false", "no", "off"}
_compile_status: Dict[str, Any] = {"checked": False, "available": False, "binary": "", "message": "not checked"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _run_status(binary: Path) -> bool:
    try:
        if not binary.exists():
            return False
        if os.name != "nt":
            binary.chmod(binary.stat().st_mode | 0o111)
        proc = subprocess.run([str(binary), "--version"], capture_output=True, text=True, timeout=4)
        return proc.returncode == 0 and "TurboSync" in (proc.stdout + proc.stderr)
    except Exception:
        return False


def ensure_sync_native(force: bool = False) -> Tuple[bool, Dict[str, Any]]:
    """Compile/check the optional native C++ helper.

    The helper currently accelerates large duplicate-index passes. It is optional
    by design, because local/Cloud environments may not have a C++ compiler.
    """
    global _compile_status
    if _compile_status.get("checked") and not force:
        return bool(_compile_status.get("available")), dict(_compile_status)

    status: Dict[str, Any] = {"checked": True, "available": False, "binary": "", "message": "C++ TurboSync disabled"}
    if not SYNC_CPP_ENABLED:
        _compile_status = status
        return False, dict(status)

    if _run_status(CACHE_BINARY):
        status.update({"available": True, "binary": str(CACHE_BINARY), "message": "C++ TurboSync helper ready"})
        _compile_status = status
        return True, dict(status)

    if not CPP_SOURCE.exists():
        status["message"] = "C++ TurboSync source missing; Python sync active"
        _compile_status = status
        return False, dict(status)

    compiler = shutil.which(os.environ.get("CXX", "")) if os.environ.get("CXX") else None
    if compiler is None:
        compiler = shutil.which("g++") or shutil.which("clang++")
    if not compiler:
        status["message"] = "No C++ compiler found; Python sync active"
        _compile_status = status
        return False, dict(status)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cmd = [compiler, "-O3", "-std=c++17", str(CPP_SOURCE), "-o", str(CACHE_BINARY)]
    started = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
        if proc.returncode == 0 and _run_status(CACHE_BINARY):
            status.update({
                "available": True,
                "binary": str(CACHE_BINARY),
                "message": f"C++ TurboSync helper compiled with {Path(compiler).name} in {time.time() - started:.1f}s",
            })
        else:
            err = (proc.stderr or proc.stdout or "compiler returned an error").strip().splitlines()[-1:]
            status["message"] = "C++ TurboSync compile failed; Python sync active" + (f": {err[0][:160]}" if err else "")
    except Exception as exc:
        status["message"] = f"C++ TurboSync compile unavailable; Python sync active: {exc}"

    _compile_status = status
    return bool(status.get("available")), dict(status)


def _python_first_indices(keys: List[str]) -> List[int]:
    seen = set()
    out: List[int] = []
    for idx, key in enumerate(keys):
        if key in seen:
            continue
        seen.add(key)
        out.append(idx)
    return out


def first_unique_indices(keys: Iterable[str]) -> Tuple[List[int], Dict[str, Any]]:
    rows = [str(k) for k in keys]
    available, status = ensure_sync_native()
    engine = "TurboSync_v1_Python"
    indices: List[int]
    if available and status.get("binary"):
        try:
            proc = subprocess.run(
                [str(status["binary"]), "--dedupe"],
                input="\n".join(rows) + "\n",
                capture_output=True,
                text=True,
                timeout=20,
            )
            if proc.returncode == 0:
                indices = [int(line.strip()) for line in proc.stdout.splitlines() if line.strip().isdigit()]
                engine = "TurboSync_v1_CPP_Dedupe"
            else:
                indices = _python_first_indices(rows)
        except Exception as exc:
            indices = _python_first_indices(rows)
            status = dict(status)
            status["message"] = f"C++ sync failed; Python active: {exc}"
    else:
        indices = _python_first_indices(rows)
    return indices, {"engine": engine, "native_available": bool(available), "native_status": status, "input": len(rows), "unique": len(indices)}


def build_type_folder_manifest(app_root: Path, items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build a virtual folder/type manifest without moving original files."""
    root = Path(app_root) / "imgs_training" / "indexes"
    by_type: Dict[str, List[Dict[str, Any]]] = {}
    for item in items:
        train = item.get("imgs_training") or {}
        label = str(train.get("predicted_type") or "unknown_review")
        by_type.setdefault(label, []).append({
            "id": item.get("id"),
            "name": item.get("name"),
            "relative_path": item.get("relative_path"),
            "preview_path": item.get("preview_path"),
            "source_path": item.get("path"),
            "confidence": train.get("confidence", 0),
            "tags": train.get("tags", []),
        })
    manifest = {
        "version": SYNC_ENGINE_VERSION,
        "updated_at": utc_now(),
        "folder_mode": "virtual_type_folders",
        "note": "Original design files are not moved. This manifest maps each file to its IMGS type folder for fast search and future export.",
        "counts": {k: len(v) for k, v in sorted(by_type.items())},
        "by_type": dict(sorted(by_type.items())),
    }
    _write_json(root / "type_folders.json", manifest)
    return manifest


def build_fast_search_manifest(app_root: Path, items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build a compact search manifest used by IMGS to avoid scanning the full library."""
    root = Path(app_root) / "imgs_training" / "indexes"
    keys = [str(item.get("sha256") or item.get("id") or item.get("path") or i) for i, item in enumerate(items)]
    unique_indices, dedupe_info = first_unique_indices(keys)
    unique_ids = {items[i].get("id") for i in unique_indices if i < len(items)}
    by_type: Dict[str, List[str]] = {}
    compact_items: Dict[str, Dict[str, Any]] = {}
    for item in items:
        item_id = str(item.get("id") or "")
        if not item_id:
            continue
        train = item.get("imgs_training") or {}
        label = str(train.get("predicted_type") or "unknown_review")
        by_type.setdefault(label, []).append(item_id)
        compact_items[item_id] = {
            "id": item_id,
            "name": item.get("name"),
            "preview_path": item.get("preview_path"),
            "source_path": item.get("path"),
            "predicted_type": label,
            "confidence": train.get("confidence", 0),
            "fingerprint_path": train.get("fingerprint_path"),
            "is_first_unique": item_id in unique_ids,
        }
    manifest = {
        "version": SYNC_ENGINE_VERSION,
        "updated_at": utc_now(),
        "dedupe": dedupe_info,
        "counts": {k: len(v) for k, v in sorted(by_type.items())},
        "by_type": dict(sorted(by_type.items())),
        "items": compact_items,
    }
    _write_json(root / "fast_search_manifest.json", manifest)
    return manifest


def sync_library_cache(app_root: Path, items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Create all lightweight sync manifests after import/training/resync."""
    type_manifest = build_type_folder_manifest(app_root, items)
    fast_manifest = build_fast_search_manifest(app_root, items)
    return {
        "version": SYNC_ENGINE_VERSION,
        "updated_at": utc_now(),
        "type_folders": type_manifest.get("counts", {}),
        "fast_search": fast_manifest.get("counts", {}),
        "dedupe": fast_manifest.get("dedupe", {}),
    }

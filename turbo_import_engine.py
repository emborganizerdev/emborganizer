from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

TURBO_IMPORT_ENGINE_VERSION = "TurboImport v1 • C++ native scan + Python fallback"
TURBO_IMPORT_ANIMATION_VERSION = "Animation S"
BASE_DIR = Path(__file__).resolve().parent
CPP_SOURCE = BASE_DIR / "turbo_import_native.cpp"
CPP_BINARY_NAME = "turbo_import_native.exe" if os.name == "nt" else "turbo_import_native"
CACHE_DIR = BASE_DIR / ".turboemb"
CACHE_BINARY = CACHE_DIR / CPP_BINARY_NAME
TURBO_IMPORT_CPP_ENABLED = os.environ.get("TURBO_IMPORT_CPP", "1").lower() not in {"0", "false", "no", "off"}

_compile_status: Dict[str, Any] = {"checked": False, "available": False, "binary": "", "message": "not checked"}


def _run_status(binary: Path) -> bool:
    try:
        if not binary.exists():
            return False
        if os.name != "nt":
            binary.chmod(binary.stat().st_mode | 0o111)
        proc = subprocess.run([str(binary), "--version"], capture_output=True, text=True, timeout=4)
        return proc.returncode == 0 and "TurboImport" in (proc.stdout + proc.stderr)
    except Exception:
        return False


def ensure_turbo_import_native(force: bool = False) -> Tuple[bool, Dict[str, Any]]:
    """Compile/check the optional native C++ Drive manifest scanner.

    v4.6 keeps this optional. Streamlit Cloud or other hosts without a compiler
    simply use the Python fallback and the app continues working.
    """
    global _compile_status
    if _compile_status.get("checked") and not force:
        return bool(_compile_status.get("available")), dict(_compile_status)

    status: Dict[str, Any] = {"checked": True, "available": False, "binary": "", "message": "C++ turbo import disabled"}
    if not TURBO_IMPORT_CPP_ENABLED:
        _compile_status = status
        return False, dict(status)

    if _run_status(CACHE_BINARY):
        status.update({"available": True, "binary": str(CACHE_BINARY), "message": "C++ Turbo Import scanner ready"})
        _compile_status = status
        return True, dict(status)

    if not CPP_SOURCE.exists():
        status["message"] = "C++ Turbo Import source file is missing; Python scanner active"
        _compile_status = status
        return False, dict(status)

    compiler = shutil.which(os.environ.get("CXX", "")) if os.environ.get("CXX") else None
    if compiler is None:
        compiler = shutil.which("g++") or shutil.which("clang++")
    if not compiler:
        status["message"] = "No C++ compiler found; Python scanner active"
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
                "message": f"C++ Turbo Import scanner compiled with {Path(compiler).name} in {time.time() - started:.1f}s",
            })
        else:
            err = (proc.stderr or proc.stdout or "compiler returned an error").strip().splitlines()[-1:]
            status["message"] = "C++ Turbo Import compile failed; Python scanner active" + (f": {err[0][:160]}" if err else "")
    except Exception as exc:
        status["message"] = f"C++ Turbo Import compile unavailable; Python scanner active: {exc}"

    _compile_status = status
    return bool(status.get("available")), dict(status)


def _suffix_for_file(row: Dict[str, Any]) -> str:
    return Path(str(row.get("name") or "")).suffix.lower()


def _python_filter(files: List[Dict[str, Any]], supported_extensions: Iterable[str]) -> List[int]:
    supported = {str(ext).lower() if str(ext).startswith(".") else "." + str(ext).lower() for ext in supported_extensions}
    return [idx for idx, row in enumerate(files) if _suffix_for_file(row) in supported]


def filter_supported_drive_files(files: List[Dict[str, Any]], supported_extensions: Iterable[str]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Filter Drive manifest rows with an optional native C++ suffix scanner."""
    rows = list(files or [])
    supported = sorted({str(ext).lower() if str(ext).startswith(".") else "." + str(ext).lower() for ext in supported_extensions})
    available, status = ensure_turbo_import_native()
    indices: List[int] = []
    engine = "TurboImport_v1_Python_Filter"

    if available and status.get("binary"):
        try:
            suffix_text = "\n".join(_suffix_for_file(row) for row in rows) + "\n"
            proc = subprocess.run(
                [str(status["binary"]), "--filter", ",".join(supported)],
                input=suffix_text,
                capture_output=True,
                text=True,
                timeout=12,
            )
            if proc.returncode == 0:
                indices = [int(line.strip()) for line in proc.stdout.splitlines() if line.strip().isdigit()]
                engine = "TurboImport_v1_CPP_ExtensionScanner"
            else:
                indices = _python_filter(rows, supported)
        except Exception as exc:
            indices = _python_filter(rows, supported)
            status = dict(status)
            status["message"] = f"C++ scan failed; Python scanner active: {exc}"
    else:
        indices = _python_filter(rows, supported)

    seen_ids: set[str] = set()
    filtered: List[Dict[str, Any]] = []
    for idx in indices:
        if idx < 0 or idx >= len(rows):
            continue
        row = rows[idx]
        file_id = str(row.get("id") or "")
        key = file_id or f"{row.get('name')}::{row.get('size')}::{row.get('modifiedTime')}"
        if key in seen_ids:
            continue
        seen_ids.add(key)
        filtered.append(row)

    info = {
        "engine": engine,
        "engine_label": TURBO_IMPORT_ENGINE_VERSION,
        "animation": TURBO_IMPORT_ANIMATION_VERSION,
        "native_available": bool(available),
        "native_status": status,
        "input_files": len(rows),
        "supported_files": len(filtered),
    }
    return filtered, info

"""Small Google Drive sync/cache helpers for EMBORGANIZER v0.8.5.

Kept separate from app.py so Drive background sync and local cache pruning are
simple to debug. This module does not call Google APIs; app.py owns auth/API.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


def bool_env(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return bool(default)
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def int_env(name: str, default: int, low: int = 0, high: int = 10**9) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except Exception:
        value = default
    return max(low, min(high, value))


def iter_files(paths: Iterable[Path]) -> Iterable[Path]:
    for root in paths:
        try:
            root = Path(root)
            if root.is_file():
                yield root
            elif root.is_dir():
                for p in root.rglob("*"):
                    if p.is_file():
                        yield p
        except Exception:
            continue


def cache_status(paths: Iterable[Path]) -> Dict:
    files: List[Tuple[float, int, str]] = []
    total = 0
    for p in iter_files(paths):
        try:
            st = p.stat()
            total += int(st.st_size)
            files.append((float(st.st_mtime), int(st.st_size), str(p)))
        except Exception:
            pass
    return {
        "bytes": total,
        "mb": round(total / 1048576, 2),
        "file_count": len(files),
        "oldest_files": [x[2] for x in sorted(files)[:10]],
    }


def enforce_cache_limit(paths: Iterable[Path], max_bytes: int, protected_suffixes: Iterable[str] = ()) -> Dict:
    """Delete oldest cache files until total size is under max_bytes.

    Intended for temporary uploads, conversion cache, exports, and preview cache.
    Never pass critical source-code folders here.
    """
    protected = {str(s).lower() for s in (protected_suffixes or [])}
    files: List[Tuple[float, int, Path]] = []
    total = 0
    for p in iter_files(paths):
        try:
            st = p.stat()
            size = int(st.st_size)
            total += size
            if p.suffix.lower() not in protected:
                files.append((float(st.st_mtime), size, p))
        except Exception:
            pass

    deleted = []
    errors = []
    before = total
    if max_bytes <= 0:
        return {"ok": True, "before_bytes": before, "after_bytes": total, "deleted_count": 0, "deleted_bytes": 0, "errors": []}

    for _mtime, size, path in sorted(files):
        if total <= max_bytes:
            break
        try:
            path.unlink(missing_ok=True)
            total -= size
            deleted.append({"path": str(path), "bytes": size})
        except Exception as exc:
            errors.append({"path": str(path), "error": str(exc)})

    return {
        "ok": True,
        "before_bytes": before,
        "before_mb": round(before / 1048576, 2),
        "after_bytes": total,
        "after_mb": round(total / 1048576, 2),
        "max_bytes": max_bytes,
        "max_mb": round(max_bytes / 1048576, 2),
        "deleted_count": len(deleted),
        "deleted_bytes": sum(d["bytes"] for d in deleted),
        "deleted_mb": round(sum(d["bytes"] for d in deleted) / 1048576, 2),
        "deleted_files": deleted[:50],
        "errors": errors[:20],
    }


def gentle_delay(seconds: float) -> None:
    try:
        seconds = float(seconds or 0)
    except Exception:
        seconds = 0.0
    if seconds > 0:
        time.sleep(seconds)

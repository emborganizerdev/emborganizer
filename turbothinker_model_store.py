"""
turbothinker_model_store.py
EMBORGANIZER TurboThinker model storage helper.

Purpose
-------
GitHub blocks normal Git files above 100 MB and large generated model JSON can
make the repo painful. This helper stores big local models as GitHub-safe brain
part files and writes a tiny redirect JSON at the original model path.

It is local-only. It does not upload anything and it does not use any API.
"""
from __future__ import annotations

import hashlib
import json
import math
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

FORMAT = "emborganizer-json-shards-v1"
DEFAULT_SHARD_SIZE = 24_000_000  # target ~24 MB, safely below the user-requested 25 MB per brain part


def _json_dumps_compact(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def shard_dir_for(model_path: Path, shard_root: Optional[Path] = None) -> Path:
    model_path = Path(model_path)
    root = Path(shard_root) if shard_root else model_path.parent / "shards"
    return root / model_path.stem


def save_json_model(
    model_path: Path,
    data: Any,
    *,
    shard_size: int = DEFAULT_SHARD_SIZE,
    force_shards: bool = True,
    shard_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Save JSON directly or as many small chunks.

    Returns a storage report suitable for GUI/debug display.
    """
    model_path = Path(model_path)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    text = _json_dumps_compact(data)
    raw_bytes = len(text.encode("utf-8"))
    if not force_shards and raw_bytes <= shard_size:
        model_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return {
            "storage": "single_json",
            "model_path": str(model_path),
            "bytes": raw_bytes,
            "shard_count": 0,
            "max_shard_bytes": raw_bytes,
        }

    shard_size = max(32_000, int(shard_size or DEFAULT_SHARD_SIZE))
    sdir = shard_dir_for(model_path, shard_root)
    if sdir.exists():
        shutil.rmtree(sdir)
    sdir.mkdir(parents=True, exist_ok=True)

    chunks: List[str] = [text[i : i + shard_size] for i in range(0, len(text), shard_size)] or [""]
    parts: List[Dict[str, Any]] = []
    for idx, chunk in enumerate(chunks):
        name = f"brain_part_{idx:04d}.brainpart"
        p = sdir / name
        p.write_text(chunk, encoding="utf-8")
        parts.append({
            "index": idx,
            "file": name,
            "bytes": len(chunk.encode("utf-8")),
            "sha256": _sha256_text(chunk),
        })

    manifest = {
        "format": FORMAT,
        "source_model_filename": model_path.name,
        "encoding": "utf-8-json-brainparts",
        "total_bytes": raw_bytes,
        "total_sha256": _sha256_text(text),
        "shard_size_target": shard_size,
        "shard_count": len(parts),
        "parts": parts,
    }
    (sdir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    rel_manifest = (sdir / "manifest.json").relative_to(model_path.parent).as_posix()
    stub = {
        "sharded_model": True,
        "format": FORMAT,
        "manifest": rel_manifest,
        "source_model_filename": model_path.name,
        "total_bytes": raw_bytes,
        "shard_count": len(parts),
        "note": "Model is split into local brain-part files under 25 MB each. Use turbothinker_model_store.load_json_model().",
    }
    model_path.write_text(json.dumps(stub, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "storage": "json_brainparts",
        "model_path": str(model_path),
        "manifest_path": str(sdir / "manifest.json"),
        "bytes": raw_bytes,
        "shard_count": len(parts),
        "max_shard_bytes": max((p["bytes"] for p in parts), default=0),
    }


def _load_manifest(stub_path: Path, stub: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    manifest_rel = stub.get("manifest")
    if not manifest_rel:
        return None
    manifest_path = Path(stub_path).parent / str(manifest_rel)
    if not manifest_path.exists():
        return None
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_json_model(model_path: Path, default: Any = None) -> Any:
    """Load a normal JSON model or a GitHub-safe sharded model."""
    model_path = Path(model_path)
    if not model_path.exists():
        return {} if default is None else default
    try:
        first = json.loads(model_path.read_text(encoding="utf-8"))
    except Exception:
        return {} if default is None else default

    if not isinstance(first, dict) or not first.get("sharded_model"):
        return first

    manifest = _load_manifest(model_path, first)
    if not manifest or manifest.get("format") != FORMAT:
        return {} if default is None else default

    base_dir = model_path.parent / Path(str(first.get("manifest"))).parent
    chunks: List[str] = []
    for part in sorted(manifest.get("parts") or [], key=lambda p: int(p.get("index") or 0)):
        p = base_dir / str(part.get("file"))
        if not p.exists():
            return {} if default is None else default
        chunk = p.read_text(encoding="utf-8")
        if part.get("sha256") and _sha256_text(chunk) != part.get("sha256"):
            return {} if default is None else default
        chunks.append(chunk)
    text = "".join(chunks)
    if manifest.get("total_sha256") and _sha256_text(text) != manifest.get("total_sha256"):
        return {} if default is None else default
    try:
        return json.loads(text)
    except Exception:
        return {} if default is None else default


def storage_summary(model_path: Path) -> Dict[str, Any]:
    model_path = Path(model_path)
    if not model_path.exists():
        return {"exists": False, "storage": "missing", "model_path": str(model_path)}
    try:
        stub = json.loads(model_path.read_text(encoding="utf-8"))
    except Exception:
        return {"exists": True, "storage": "unknown", "model_path": str(model_path), "bytes": model_path.stat().st_size}
    if not isinstance(stub, dict) or not stub.get("sharded_model"):
        return {"exists": True, "storage": "single_json", "model_path": str(model_path), "bytes": model_path.stat().st_size}
    manifest = _load_manifest(model_path, stub)
    return {
        "exists": True,
        "storage": "json_brainparts",
        "model_path": str(model_path),
        "manifest": stub.get("manifest"),
        "total_bytes": stub.get("total_bytes"),
        "shard_count": stub.get("shard_count"),
        "max_shard_bytes": max((int(p.get("bytes") or 0) for p in (manifest or {}).get("parts", [])), default=0),
    }


__all__ = [
    "FORMAT",
    "DEFAULT_SHARD_SIZE",
    "save_json_model",
    "load_json_model",
    "storage_summary",
    "shard_dir_for",
]

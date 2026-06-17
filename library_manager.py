"""Maximum Library Manager helpers for EMBORGANIZER v5.4.3.

All functions are local-only and operate on cache/imgs_index.json plus the local
library/import folders. No external API is used here.
"""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

LIBRARY_MANAGER_VERSION = "Maximum Library Manager v5.4.3"


def json_read(path: Path, default: Any) -> Any:
    try:
        p = Path(path)
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def json_write(path: Path, data: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def index_path(app_root: Path) -> Path:
    return Path(app_root) / "cache" / "imgs_index.json"


def load_index(app_root: Path) -> Dict[str, Any]:
    data = json_read(index_path(app_root), {"version": "unknown", "items": []})
    if not isinstance(data, dict):
        data = {"version": "unknown", "items": []}
    data.setdefault("items", [])
    return data


def write_index(app_root: Path, data: Dict[str, Any]) -> None:
    data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    json_write(index_path(app_root), data)


def as_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def item_text(item: Dict[str, Any]) -> str:
    parts = [
        item.get("design_no"), item.get("source_name"), item.get("primary_label"),
        item.get("work_type"), item.get("neck_type"), item.get("dress_type"),
        " ".join(str(x) for x in as_list(item.get("tags"))),
    ]
    return " ".join(str(x or "") for x in parts).lower()


def fingerprint_key(item: Dict[str, Any]) -> str:
    fp = item.get("fingerprint") or {}
    for key in ("sha1", "image_sha1", "ahash", "dhash", "edge_hash", "mask_bits"):
        val = fp.get(key)
        if val:
            return f"{key}:{val}"
    path = Path(str(item.get("image_path") or item.get("path") or ""))
    if path.exists():
        try:
            h = hashlib.sha1()
            with path.open("rb") as fh:
                for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                    h.update(chunk)
            return "file:" + h.hexdigest()
        except Exception:
            pass
    return ""


def library_summary(app_root: Path) -> Dict[str, Any]:
    index = load_index(app_root)
    items = as_list(index.get("items"))
    by_work: Dict[str, int] = {}
    by_neck: Dict[str, int] = {}
    by_label: Dict[str, int] = {}
    by_source: Dict[str, int] = {}
    missing = 0
    duplicates: Dict[str, List[str]] = {}
    for item in items:
        by_work[str(item.get("work_type") or "unknown")] = by_work.get(str(item.get("work_type") or "unknown"), 0) + 1
        by_neck[str(item.get("neck_type") or "unknown")] = by_neck.get(str(item.get("neck_type") or "unknown"), 0) + 1
        by_label[str(item.get("primary_label") or "unknown")] = by_label.get(str(item.get("primary_label") or "unknown"), 0) + 1
        by_source[str(item.get("source") or "unknown")] = by_source.get(str(item.get("source") or "unknown"), 0) + 1
        p = Path(str(item.get("image_path") or item.get("path") or ""))
        if not p.exists():
            missing += 1
        fk = fingerprint_key(item)
        if fk:
            duplicates.setdefault(fk, []).append(str(item.get("id") or item.get("image_path") or ""))
    duplicate_sets = [v for v in duplicates.values() if len(v) > 1]
    return {
        "version": index.get("version"),
        "updated_at": index.get("updated_at"),
        "total": len(items),
        "missing_files": missing,
        "duplicate_sets": len(duplicate_sets),
        "duplicate_records": sum(len(v) for v in duplicate_sets),
        "by_work_type": dict(sorted(by_work.items(), key=lambda kv: kv[1], reverse=True)),
        "by_neck_type": dict(sorted(by_neck.items(), key=lambda kv: kv[1], reverse=True)),
        "by_label": dict(sorted(by_label.items(), key=lambda kv: kv[1], reverse=True)),
        "by_source": dict(sorted(by_source.items(), key=lambda kv: kv[1], reverse=True)),
    }


def filter_items(items: Iterable[Dict[str, Any]], query: str = "", work_type: str = "any", neck_type: str = "any", dress_type: str = "any", source: str = "any", missing_only: bool = False, limit: int = 500) -> List[Dict[str, Any]]:
    q = str(query or "").strip().lower()
    result: List[Dict[str, Any]] = []
    for item in items:
        if q and q not in item_text(item):
            continue
        if work_type != "any" and str(item.get("work_type") or "") != work_type:
            continue
        if neck_type != "any" and str(item.get("neck_type") or "") != neck_type:
            continue
        if dress_type != "any" and str(item.get("dress_type") or "") != dress_type:
            continue
        if source != "any" and str(item.get("source") or "") != source:
            continue
        if missing_only:
            p = Path(str(item.get("image_path") or item.get("path") or ""))
            if p.exists():
                continue
        result.append(item)
        if len(result) >= int(limit):
            break
    return result


def list_options(items: Iterable[Dict[str, Any]], field: str) -> List[str]:
    vals = sorted({str(item.get(field) or "unknown") for item in items if str(item.get(field) or "").strip()})
    return ["any"] + vals


def export_csv(app_root: Path, items: Optional[List[Dict[str, Any]]] = None, filename: str = "library_export.csv") -> Path:
    index = load_index(app_root)
    rows = items if items is not None else as_list(index.get("items"))
    out = Path(app_root) / "exports" / filename
    out.parent.mkdir(parents=True, exist_ok=True)
    fields = ["id", "design_no", "source_name", "primary_label", "work_type", "neck_type", "dress_type", "confidence", "image_mode", "tags", "image_path", "source", "created_at"]
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for item in rows:
            row = {k: item.get(k, "") for k in fields}
            row["tags"] = ", ".join(str(x) for x in as_list(item.get("tags")))
            writer.writerow(row)
    return out


def export_json(app_root: Path, items: Optional[List[Dict[str, Any]]] = None, filename: str = "library_export.json") -> Path:
    index = load_index(app_root)
    rows = items if items is not None else as_list(index.get("items"))
    out = Path(app_root) / "exports" / filename
    json_write(out, {"exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "items": rows})
    return out


def backup_library(app_root: Path, include_images: bool = False) -> Path:
    app_root = Path(app_root)
    out = app_root / "exports" / f"emborganizer_library_backup_{int(time.time())}.zip"
    out.parent.mkdir(parents=True, exist_ok=True)
    include_roots = [app_root / "cache", app_root / "imgs_training" / "design_json", app_root / "imgs_training" / "corrections.json"]
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for root in include_roots:
            if root.is_file():
                zf.write(root, arcname=str(root.relative_to(app_root)))
            elif root.is_dir():
                for p in root.rglob("*"):
                    if p.is_file():
                        zf.write(p, arcname=str(p.relative_to(app_root)))
        if include_images:
            lib = app_root / "library"
            if lib.exists():
                for p in lib.rglob("*"):
                    if p.is_file():
                        zf.write(p, arcname=str(p.relative_to(app_root)))
    return out


def remove_missing_records(app_root: Path) -> Dict[str, Any]:
    index = load_index(app_root)
    items = as_list(index.get("items"))
    kept = []
    removed = []
    for item in items:
        p = Path(str(item.get("image_path") or item.get("path") or ""))
        if p.exists():
            kept.append(item)
        else:
            removed.append(item)
    index["items"] = kept
    write_index(app_root, index)
    return {"removed": len(removed), "kept": len(kept)}


def dedupe_records(app_root: Path, dry_run: bool = True) -> Dict[str, Any]:
    index = load_index(app_root)
    items = as_list(index.get("items"))
    seen: Dict[str, Dict[str, Any]] = {}
    kept: List[Dict[str, Any]] = []
    removed: List[Dict[str, Any]] = []
    for item in items:
        key = fingerprint_key(item) or str(item.get("image_path") or item.get("id") or "")
        if key and key in seen:
            removed.append(item)
        else:
            kept.append(item)
            if key:
                seen[key] = item
    if not dry_run:
        index["items"] = kept
        write_index(app_root, index)
    return {"duplicate_records": len(removed), "kept": len(kept), "dry_run": bool(dry_run), "sample_removed": removed[:20]}


def apply_bulk_labels(app_root: Path, ids: List[str], work_type: Optional[str] = None, neck_type: Optional[str] = None, dress_type: Optional[str] = None, add_tags: Optional[List[str]] = None) -> Dict[str, Any]:
    index = load_index(app_root)
    items = as_list(index.get("items"))
    idset = set(str(x) for x in ids)
    changed = 0
    for item in items:
        if str(item.get("id") or item.get("image_path") or "") not in idset:
            continue
        if work_type:
            item["work_type"] = work_type
            item["primary_label"] = work_type
        if neck_type:
            item["neck_type"] = neck_type
        if dress_type:
            item["dress_type"] = dress_type
        if add_tags:
            tags = [str(x) for x in as_list(item.get("tags"))]
            for tag in add_tags:
                if tag and tag not in tags:
                    tags.append(tag)
            item["tags"] = tags
        changed += 1
    write_index(app_root, index)
    return {"changed": changed}

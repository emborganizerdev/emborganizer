"""
EMBORGANIZER v5.4.4 DST-first Full Site Alive + Converters + Google Bridge

Clean local UI for the v5.4 24MB brain-part build with an interactive teacher-rule searcher.
Removed old/clutter pages from the visible app: Google Drive, external sign-in,
legacy converters, and extra marketing panels. This file focuses only on the
workflow Shiva needs now:

1. Check SuperBrain status.
2. Test one image visually.
3. Save teacher corrections.
4. Train/retrain local brain from ZIP + corrections.
5. Search teacher memory, corrections, local images, and GitHub-safe 24MB brain parts.

Local-only. No API. File names are never used as labels.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import time
import zipfile
from datetime import datetime, timezone
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import streamlit as st
from PIL import Image, ImageOps

try:
    from imgs_training import (
        IMGS_LABELS,
        IMGS_TRAINING_WARNING,
        IMGS_TRAINING_VERSION,
        TURBOTHINKER_ENGINE_VERSION,
        analyze_image_for_training,
        analyze_selector_area,
        apply_seed_training_memory,
        apply_student_model_memory,
        apply_ultrabrain_memory,
        apply_superbrain_memory,
        apply_teacher_rule_pipeline,
        build_seed_training_corpus_from_zip_bytes,
        build_ultrabrain_region_corpus_from_zip_bytes,
        ensure_training_dirs,
        load_corrections,
        load_seed_training_bank,
        load_turbothinker_student_summary,
        load_turbothinker_ultrabrain_summary,
        load_turbothinker_superbrain_summary,
        record_training_correction,
        record_selector_area_training,
        save_uploaded_training_image,
        train_turbothinker_student_model,
        train_turbothinker_ultrabrain_model,
        train_turbothinker_superbrain_model,
    )
except Exception as exc:  # pragma: no cover - Streamlit will display the issue.
    IMGS_LABELS = ["unknown_review"]
    IMGS_TRAINING_WARNING = "TurboThinker modules could not be imported."
    IMGS_TRAINING_VERSION = f"Unavailable: {exc}"
    TURBOTHINKER_ENGINE_VERSION = "Unavailable"
    analyze_image_for_training = None
    analyze_selector_area = None
    apply_seed_training_memory = None
    apply_student_model_memory = None
    apply_ultrabrain_memory = None
    apply_superbrain_memory = None
    apply_teacher_rule_pipeline = None
    build_seed_training_corpus_from_zip_bytes = None
    build_ultrabrain_region_corpus_from_zip_bytes = None
    ensure_training_dirs = None
    load_corrections = None
    load_seed_training_bank = None
    load_turbothinker_student_summary = None
    load_turbothinker_ultrabrain_summary = None
    load_turbothinker_superbrain_summary = None
    record_training_correction = None
    record_selector_area_training = None
    save_uploaded_training_image = None
    train_turbothinker_student_model = None
    train_turbothinker_ultrabrain_model = None
    train_turbothinker_superbrain_model = None

try:
    from turbothinker_superbrain import SUPERBRAIN_VERSION
except Exception:
    SUPERBRAIN_VERSION = "TurboThinker SuperBrain unavailable"

try:
    from turbothinker_model_store import storage_summary
except Exception:
    storage_summary = None


try:
    from imagesearch import (
        IMAGE_SEARCH_VERSION,
        compare_fingerprints,
        create_fingerprint_from_image,
        create_fingerprint_from_path,
    )
except Exception as exc:  # pragma: no cover
    IMAGE_SEARCH_VERSION = f"Image Searcher unavailable: {exc}"
    compare_fingerprints = None
    create_fingerprint_from_image = None
    create_fingerprint_from_path = None

try:
    from sync_engine import sync_library_cache, build_fast_search_manifest, build_type_folder_manifest
except Exception:  # pragma: no cover
    sync_library_cache = None
    build_fast_search_manifest = None
    build_type_folder_manifest = None

try:
    from turbothinker_interactive_searcher import (
        SEARCHER_VERSION,
        DRESS_TYPE_OPTIONS,
        FEATURE_OPTIONS,
        NECK_TYPE_OPTIONS,
        WORK_TYPE_OPTIONS,
        build_search_records,
        infer_query_facets,
        rule_cards,
        search_records,
        student_answer_for,
        summarize_records,
    )
except Exception as exc:  # pragma: no cover
    SEARCHER_VERSION = f"Interactive Searcher unavailable: {exc}"
    DRESS_TYPE_OPTIONS = ["any"]
    FEATURE_OPTIONS = ["any"]
    NECK_TYPE_OPTIONS = ["any"]
    WORK_TYPE_OPTIONS = ["any"]
    build_search_records = None
    infer_query_facets = None
    rule_cards = None
    search_records = None
    student_answer_for = None
    summarize_records = None


try:
    from dst_converter import (
        DST_CONVERTER_VERSION,
        SUPPORTED_EMB_EXTENSIONS,
        convert_uploaded_bytes,
        convert_zip_bytes,
        cpp_status,
        read_design_file,
        render_embroidery_file,
    )
except Exception as exc:  # pragma: no cover
    DST_CONVERTER_VERSION = f"DST Converter unavailable: {exc}"
    SUPPORTED_EMB_EXTENSIONS = {".dst"}
    convert_uploaded_bytes = None
    convert_zip_bytes = None
    cpp_status = None
    read_design_file = None
    render_embroidery_file = None

try:
    from library_manager import (
        LIBRARY_MANAGER_VERSION,
        apply_bulk_labels as lm_apply_bulk_labels,
        backup_library as lm_backup_library,
        dedupe_records as lm_dedupe_records,
        export_csv as lm_export_csv,
        export_json as lm_export_json,
        filter_items as lm_filter_items,
        library_summary as lm_library_summary,
        list_options as lm_list_options,
        load_index as lm_load_index,
        remove_missing_records as lm_remove_missing_records,
    )
except Exception as exc:  # pragma: no cover
    LIBRARY_MANAGER_VERSION = f"Library Manager unavailable: {exc}"
    lm_apply_bulk_labels = None
    lm_backup_library = None
    lm_dedupe_records = None
    lm_export_csv = None
    lm_export_json = None
    lm_filter_items = None
    lm_library_summary = None
    lm_list_options = None
    lm_load_index = None
    lm_remove_missing_records = None

try:
    from drive_gmail_bridge import (
        GOOGLE_BRIDGE_VERSION,
        build_oauth_url,
        drive_download_file,
        drive_list_files,
        exchange_oauth_code,
        gmail_profile,
        gmail_recent_messages,
        google_status,
        load_google_config,
        parse_drive_id,
        save_google_config,
    )
except Exception as exc:  # pragma: no cover
    GOOGLE_BRIDGE_VERSION = f"Google bridge unavailable: {exc}"
    build_oauth_url = None
    drive_download_file = None
    drive_list_files = None
    exchange_oauth_code = None
    gmail_profile = None
    gmail_recent_messages = None
    google_status = None
    load_google_config = None
    parse_drive_id = None
    save_google_config = None

APP_NAME = "EMBORGANIZER"
APP_VERSION = "v5.4.4"
APP_RELEASE = "DST-first Full Site Alive + folder/ZIP import + meaningful reader + teacher-rule TurboThinker"
APP_ROOT = Path(__file__).resolve().parent
SUPPORTED_IMAGE_TYPES = ["png", "jpg", "jpeg", "webp", "bmp"]
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
EMBROIDERY_EXTENSIONS = set(SUPPORTED_EMB_EXTENSIONS or {".dst"})


# -----------------------------
# Loading animation helpers
# -----------------------------

def _loader_html(message: str, detail: str = "", small: bool = False) -> str:
    """Small CSS-only embroidery loading animation for Streamlit placeholders."""
    size_class = " emb-loader-small" if small else ""
    safe_message = str(message).replace("<", "&lt;").replace(">", "&gt;")
    safe_detail = str(detail).replace("<", "&lt;").replace(">", "&gt;")
    detail_html = f'<div class="emb-loader-detail">{safe_detail}</div>' if safe_detail else ""
    return f"""
    <div class="emb-loader-wrap{size_class}" role="status" aria-live="polite">
      <div class="emb-loader-stage">
        <span class="emb-stitch s1"></span>
        <span class="emb-stitch s2"></span>
        <span class="emb-stitch s3"></span>
        <span class="emb-stitch s4"></span>
        <span class="emb-needle"></span>
        <span class="emb-thread"></span>
        <span class="emb-dot d1"></span>
        <span class="emb-dot d2"></span>
        <span class="emb-dot d3"></span>
      </div>
      <div class="emb-loader-copy">
        <strong>{safe_message}</strong>
        {detail_html}
      </div>
    </div>
    """


@contextmanager
def animated_loader(message: str, detail: str = "", small: bool = False):
    """Show a custom loading animation while a local operation runs."""
    slot = st.empty()
    slot.markdown(_loader_html(message, detail, small=small), unsafe_allow_html=True)
    try:
        yield slot
    finally:
        slot.empty()


# -----------------------------
# Small safe helpers
# -----------------------------

def _json_read(path: Path, default: Any) -> Any:
    try:
        if Path(path).exists():
            return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def _json_write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _safe_percent(value: Any) -> int:
    try:
        return max(0, min(100, int(round(float(value)))))
    except Exception:
        return 0


def _as_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _short_path(path: Path) -> str:
    try:
        return str(path.relative_to(APP_ROOT))
    except Exception:
        return str(path)


def _image_from_upload(uploaded: Any) -> Image.Image:
    raw = uploaded.getvalue()
    with Image.open(io.BytesIO(raw)) as img:
        return ImageOps.exif_transpose(img).convert("RGB")


def _sample_id_for_image(img: Image.Image, source_name: str) -> str:
    small = img.copy()
    small.thumbnail((128, 128))
    buf = io.BytesIO()
    small.save(buf, format="PNG")
    return hashlib.sha256(buf.getvalue() + source_name.encode("utf-8", "ignore")).hexdigest()[:16]


def _run_full_analysis(img: Image.Image, source_name: str) -> Dict[str, Any]:
    if analyze_image_for_training is None:
        raise RuntimeError("TurboThinker image analysis is unavailable.")
    analysis = analyze_image_for_training(img, source_name)
    # Blend brains from old to strongest. Each function safely returns unchanged if missing.
    for fn in (apply_seed_training_memory, apply_student_model_memory, apply_ultrabrain_memory, apply_superbrain_memory):
        if fn is not None:
            analysis = fn(APP_ROOT, analysis)
    if apply_teacher_rule_pipeline is not None:
        analysis = apply_teacher_rule_pipeline(analysis)
    return analysis


def _score_table(scores: Dict[str, Any], limit: int = 12) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for label, score in sorted((scores or {}).items(), key=lambda kv: float(kv[1] or 0), reverse=True)[:limit]:
        try:
            pct = round(float(score) * 100, 1)
        except Exception:
            pct = 0.0
        rows.append({"label": label, "score": pct})
    return rows


def _brain_manifest_path() -> Path:
    return APP_ROOT / "imgs_training" / "models" / "shards" / "turbothinker_superbrain_v5_3_model" / "manifest.json"


def brain_part_status() -> Dict[str, Any]:
    manifest_path = _brain_manifest_path()
    manifest = _json_read(manifest_path, {})
    parts = []
    total = 0
    ok = True
    for row in _as_list(manifest.get("parts")):
        name = str(row.get("file") or "")
        part_path = manifest_path.parent / name
        size = part_path.stat().st_size if part_path.exists() else 0
        total += size
        part_ok = part_path.exists() and size < 25_000_000
        ok = ok and part_ok
        parts.append({
            "file": name,
            "size_mb": round(size / (1024 * 1024), 2),
            "under_25mb": part_ok,
        })
    return {
        "manifest_exists": manifest_path.exists(),
        "model": manifest.get("model_name") or "turbothinker_superbrain_v5_3_model",
        "parts": parts,
        "parts_count": len(parts),
        "total_mb": round(total / (1024 * 1024), 2),
        "ok": bool(parts and ok),
        "manifest_path": _short_path(manifest_path),
    }


def load_all_summaries() -> Dict[str, Any]:
    summaries: Dict[str, Any] = {}
    for name, fn in [
        ("seed", load_seed_training_bank),
        ("student", load_turbothinker_student_summary),
        ("ultrabrain", load_turbothinker_ultrabrain_summary),
        ("superbrain", load_turbothinker_superbrain_summary),
    ]:
        try:
            summaries[name] = fn(APP_ROOT) if fn is not None else {"exists": False}
        except Exception as exc:
            summaries[name] = {"exists": False, "error": str(exc)}
    try:
        corrections = load_corrections(APP_ROOT) if load_corrections is not None else {}
        summaries["corrections"] = {"count": len(_as_list(corrections.get("samples")))}
    except Exception as exc:
        summaries["corrections"] = {"count": 0, "error": str(exc)}
    summaries["brain_parts"] = brain_part_status()
    return summaries


def _show_prediction_card(analysis: Dict[str, Any]) -> None:
    pred = analysis.get("prediction") or {}
    thinker = analysis.get("turbothinker") or {}
    label = str(pred.get("predicted_type") or "unknown_review")
    confidence = _safe_percent(pred.get("confidence"))
    tags = _as_list(pred.get("tags"))
    secondary = _as_list(pred.get("secondary_types"))
    reasons = _as_list(pred.get("reason"))
    failure_notes = _as_list(pred.get("superbrain_failure_notes"))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Primary type", label)
    c2.metric("Confidence", f"{confidence}%")
    c3.metric("Image mode", str(pred.get("image_mode") or thinker.get("image_mode") or "single_design"))
    c4.metric("Estimated parts", str(thinker.get("estimated_region_count") or thinker.get("unique_design_file_count", {}).get("min") or "1"))

    if tags:
        st.markdown("**Tags**")
        st.write(" · ".join(f"`{tag}`" for tag in tags[:24]))
    if secondary:
        st.markdown("**Secondary candidates**")
        st.write(" · ".join(f"`{tag}`" for tag in secondary[:12]))
    if failure_notes:
        st.warning(" | ".join(str(x) for x in failure_notes[:4]))
    if reasons:
        with st.expander("Why TurboThinker guessed this"):
            for reason in reasons[:10]:
                st.write("• " + str(reason))
    scores = _score_table(pred.get("scores") or {}, limit=16)
    if scores:
        with st.expander("Score table"):
            st.dataframe(scores, use_container_width=True, hide_index=True)
    if pred.get("superbrain_neighbors"):
        with st.expander("Nearest visual memory"):
            rows = []
            for n in _as_list(pred.get("superbrain_neighbors"))[:12]:
                rows.append({
                    "label": n.get("label") or n.get("primary") or "",
                    "score": round(float(n.get("score") or n.get("similarity") or 0) * 100, 1),
                    "tags": ", ".join(_as_list(n.get("tags"))[:6]),
                })
            if rows:
                st.dataframe(rows, use_container_width=True, hide_index=True)


def _show_identification_breakdown(analysis: Dict[str, Any]) -> None:
    """Show the redesigned TurboThinker explanation in meaningful teacher language."""
    pipe = analysis.get("teacher_rule_pipeline") or (analysis.get("prediction") or {}).get("teacher_rule_pipeline") or {}
    if not pipe:
        return
    st.markdown("#### How TurboThinker identified it")
    c1, c2, c3 = st.columns(3)
    c1.metric("Shape / neck guess", str(pipe.get("neck_guess") or "unknown"))
    c2.metric("Work guess", str(pipe.get("work_guess") or "normal_work"))
    c3.metric("Mode", str(pipe.get("image_mode") or "single_design"))
    st.caption(str(pipe.get("student_sentence") or "Shape first, work type second, motif/hand/drop details third."))
    rows = []
    for r in _as_list(pipe.get("rules")):
        rows.append({
            "rule": r.get("rule"),
            "used": "YES" if r.get("fired") else "no",
            "strength": r.get("strength"),
            "why": r.get("detail"),
        })
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)


# -----------------------------
# Full-site import/cache/search helpers
# -----------------------------

def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _cache_dir() -> Path:
    path = APP_ROOT / "cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _library_dir() -> Path:
    path = APP_ROOT / "library"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _search_index_path() -> Path:
    return _cache_dir() / "imgs_index.json"


def _import_log_path() -> Path:
    return _cache_dir() / "import_log.json"


def _design_json_dir() -> Path:
    path = APP_ROOT / "imgs_training" / "design_json"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _load_search_index() -> Dict[str, Any]:
    data = _json_read(_search_index_path(), {"version": APP_VERSION, "items": []})
    if not isinstance(data, dict):
        return {"version": APP_VERSION, "items": []}
    data.setdefault("items", [])
    return data


def _write_search_index(data: Dict[str, Any]) -> None:
    data["version"] = APP_VERSION
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    _json_write(_search_index_path(), data)


def _append_import_log(row: Dict[str, Any]) -> None:
    log = _json_read(_import_log_path(), {"imports": []})
    if not isinstance(log, dict):
        log = {"imports": []}
    imports = _as_list(log.get("imports"))
    imports.append(row)
    log["imports"] = imports[-100:]
    _json_write(_import_log_path(), log)


def _normalize_design_no(source_name: str) -> str:
    stem = Path(str(source_name)).stem.strip()
    clean = "".join(ch if ch.isalnum() else " " for ch in stem).split()
    if not clean:
        return stem or "design"
    # Keep common HB/BH codes together when possible.
    joined = "".join(clean)
    return joined.upper() if joined[:2].lower() in {"hb", "bh"} else "_".join(clean)


def _tags_from_analysis(analysis: Dict[str, Any]) -> List[str]:
    pred = analysis.get("prediction") or {}
    tags: List[str] = []
    primary = pred.get("predicted_type")
    if primary:
        tags.append(str(primary))
    for key in ("tags", "secondary_types"):
        for tag in _as_list(pred.get(key)):
            if tag and str(tag) not in tags:
                tags.append(str(tag))
    thinker = analysis.get("turbothinker") or {}
    for tag in _as_list(thinker.get("tags")):
        if tag and str(tag) not in tags:
            tags.append(str(tag))
    return tags[:40]


def _class_fields_from_analysis(analysis: Dict[str, Any]) -> Dict[str, Any]:
    pred = analysis.get("prediction") or {}
    tags = _tags_from_analysis(analysis)
    label = str(pred.get("predicted_type") or "unknown_review")
    lower = " ".join(tags + [label]).lower()
    work_type = label
    if "rangoli" in lower:
        work_type = "rangoli_work"
    elif "cut" in lower:
        work_type = "cut_work"
    elif "net" in lower:
        work_type = "net_work"
    elif "heavy" in lower:
        work_type = "heavy_work"
    elif any(x in lower for x in ["flower", "floral", "normal"]):
        work_type = "normal_work"

    neck_type = "unknown"
    for needle, value in [
        ("drop", "drop_neck"), ("back_drop", "drop_neck"), ("boat", "boat_neck"),
        ("pot", "pot_neck"), ("u_shaped", "u_shaped_neck"), ("u-shaped", "u_shaped_neck"),
        ("u_neck", "u_shaped_neck"), ("v_neck", "v_neck"), ("v-neck", "v_neck"),
        ("kurta", "kurta_neck"),
    ]:
        if needle in lower:
            neck_type = value
            break

    dress_type = "blouse"
    if "kurta" in lower or "kurt" in lower:
        dress_type = "kurta"
    elif "saree" in lower:
        dress_type = "saree"

    return {"label": label, "tags": tags, "work_type": work_type, "neck_type": neck_type, "dress_type": dress_type}


def _make_design_record(
    *,
    image_path: Path,
    source_name: str,
    analysis: Optional[Dict[str, Any]] = None,
    fingerprint: Optional[Dict[str, Any]] = None,
    import_id: str = "manual",
) -> Dict[str, Any]:
    analysis = analysis or {}
    fields = _class_fields_from_analysis(analysis) if analysis else {
        "label": "unknown_review", "tags": [], "work_type": "unknown", "neck_type": "unknown", "dress_type": "unknown"
    }
    rel = _short_path(image_path)
    fid = hashlib.sha256((str(image_path) + source_name).encode("utf-8", "ignore")).hexdigest()[:16]
    pred = analysis.get("prediction") or {}
    return {
        "id": fid,
        "design_no": _normalize_design_no(source_name),
        "source_name": source_name,
        "image_path": str(image_path),
        "relative_path": rel,
        "primary_label": fields.get("label") or "unknown_review",
        "work_type": fields.get("work_type") or "unknown",
        "neck_type": fields.get("neck_type") or "unknown",
        "dress_type": fields.get("dress_type") or "unknown",
        "tags": fields.get("tags") or [],
        "confidence": pred.get("confidence"),
        "image_mode": pred.get("image_mode") or (analysis.get("turbothinker") or {}).get("image_mode") or "single_design",
        "estimated_parts": (analysis.get("turbothinker") or {}).get("estimated_region_count"),
        "analysis": analysis,
        "fingerprint": fingerprint or {},
        "import_id": import_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "imported_library",
        "name": source_name,
        "path": str(image_path),
        "preview_path": str(image_path),
        "imgs_training": {
            "predicted_type": fields.get("label") or "unknown_review",
            "confidence": pred.get("confidence") or 0,
            "tags": fields.get("tags") or [],
            "image_mode": pred.get("image_mode") or (analysis.get("turbothinker") or {}).get("image_mode") or "single_design",
        },
    }


def _upsert_index_items(new_items: List[Dict[str, Any]]) -> Dict[str, Any]:
    index = _load_search_index()
    existing = _as_list(index.get("items"))
    by_key: Dict[str, Dict[str, Any]] = {}
    for item in existing:
        key = str(item.get("id") or item.get("image_path") or item.get("source_name") or "")
        if key:
            by_key[key] = item
    for item in new_items:
        key = str(item.get("id") or item.get("image_path") or item.get("source_name") or "")
        if key:
            by_key[key] = item
    index["items"] = list(by_key.values())
    _write_search_index(index)
    return index


def _open_image_bytes(data: bytes) -> Image.Image:
    with Image.open(io.BytesIO(data)) as img:
        return ImageOps.exif_transpose(img).convert("RGB")


def _iter_zip_images(payload: bytes, limit: int = 5000) -> Iterable[Tuple[str, bytes]]:
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        names = [n for n in zf.namelist() if not n.endswith("/") and Path(n).suffix.lower() in IMAGE_EXTENSIONS]
        for name in names[:int(limit)]:
            try:
                yield name, zf.read(name)
            except Exception:
                continue


def _save_imported_image(img: Image.Image, source_name: str, import_id: str) -> Path:
    safe_name = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in Path(source_name).name)
    if not safe_name.lower().endswith(tuple(IMAGE_EXTENSIONS)):
        safe_name = Path(safe_name).stem + ".png"
    out_dir = _library_dir() / "imports" / import_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / safe_name
    stem = out_path.stem
    suffix = out_path.suffix or ".png"
    counter = 1
    while out_path.exists():
        out_path = out_dir / f"{stem}_{counter}{suffix}"
        counter += 1
    img.save(out_path)
    return out_path


def import_images_to_library(
    files: List[Any],
    *,
    import_name: str = "manual_import",
    analyze: bool = True,
    build_fingerprints: bool = True,
    limit: int = 500,
) -> Dict[str, Any]:
    import_id = f"{_utc_stamp()}_{hashlib.sha1(import_name.encode('utf-8','ignore')).hexdigest()[:8]}"
    items: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []
    count = 0
    for uploaded in files:
        if count >= int(limit):
            break
        try:
            img = _image_from_upload(uploaded)
            out = _save_imported_image(img, uploaded.name, import_id)
            analysis = _run_full_analysis(img, uploaded.name) if analyze else {}
            fp = create_fingerprint_from_image(img) if build_fingerprints and create_fingerprint_from_image is not None else {}
            rec = _make_design_record(image_path=out, source_name=uploaded.name, analysis=analysis, fingerprint=fp, import_id=import_id)
            _json_write(_design_json_dir() / f"{rec['id']}.json", rec)
            items.append(rec)
            count += 1
        except Exception as exc:
            errors.append({"file": getattr(uploaded, "name", "uploaded"), "error": str(exc)})
    index = _upsert_index_items(items)
    _append_import_log({"import_id": import_id, "name": import_name, "items": len(items), "errors": errors, "created_at": datetime.now(timezone.utc).isoformat()})
    if sync_library_cache is not None and items:
        try:
            sync_library_cache(APP_ROOT, index.get("items", []))
        except Exception:
            pass
    return {"import_id": import_id, "items": items, "errors": errors, "index_count": len(index.get("items", []))}


def import_zip_to_library(
    payload: bytes,
    *,
    zip_name: str,
    analyze: bool = True,
    build_fingerprints: bool = True,
    limit: int = 500,
) -> Dict[str, Any]:
    import_id = f"{_utc_stamp()}_{hashlib.sha1(zip_name.encode('utf-8','ignore')).hexdigest()[:8]}"
    items: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []
    for i, (name, raw) in enumerate(_iter_zip_images(payload, int(limit)), start=1):
        try:
            img = _open_image_bytes(raw)
            out = _save_imported_image(img, name, import_id)
            analysis = _run_full_analysis(img, name) if analyze else {}
            fp = create_fingerprint_from_image(img) if build_fingerprints and create_fingerprint_from_image is not None else {}
            rec = _make_design_record(image_path=out, source_name=name, analysis=analysis, fingerprint=fp, import_id=import_id)
            _json_write(_design_json_dir() / f"{rec['id']}.json", rec)
            items.append(rec)
        except Exception as exc:
            errors.append({"file": name, "error": str(exc)})
    index = _upsert_index_items(items)
    _append_import_log({"import_id": import_id, "name": zip_name, "items": len(items), "errors": errors, "created_at": datetime.now(timezone.utc).isoformat()})
    if sync_library_cache is not None and items:
        try:
            sync_library_cache(APP_ROOT, index.get("items", []))
        except Exception:
            pass
    return {"import_id": import_id, "items": items, "errors": errors, "index_count": len(index.get("items", []))}



def _iter_zip_embroidery(payload: bytes, limit: int = 5000) -> Iterable[Tuple[str, bytes]]:
    """Yield embroidery design files from a ZIP. DST is the main import source."""
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        names = [n for n in zf.namelist() if not n.endswith("/") and Path(n).suffix.lower() in EMBROIDERY_EXTENSIONS]
        for name in names[:int(limit)]:
            try:
                yield name, zf.read(name)
            except Exception:
                continue


def _design_meaningful_summary(meta: Dict[str, Any], analysis: Dict[str, Any], source_kind: str = "dst") -> Dict[str, Any]:
    """Small, human-readable summary so the app does not only show raw JSON bounds."""
    pred = analysis.get("prediction") or {}
    pipe = analysis.get("teacher_rule_pipeline") or pred.get("teacher_rule_pipeline") or {}
    bounds = meta.get("bounds") or {}
    reader = meta.get("reader") or {}
    work = pipe.get("work_guess") or pred.get("predicted_type") or "unknown"
    neck = pipe.get("neck_guess") or "unknown"
    tags = _as_list(pred.get("tags"))[:10]
    parts = []
    if int(meta.get("stitches") or 0) > 0:
        parts.append(f"{int(meta.get('stitches') or 0):,} stitches")
    if meta.get("estimated_thread_colors") is not None:
        parts.append(f"{meta.get('estimated_thread_colors')} thread colors")
    if bounds.get("width") and bounds.get("height"):
        parts.append(f"size {bounds.get('width')} × {bounds.get('height')} stitch units")
    if meta.get("density_score") is not None:
        parts.append(f"density {meta.get('density_score')}")
    explanation = " · ".join(parts) if parts else "Rendered and analyzed locally."
    return {
        "source_type": source_kind,
        "student_name": f"{neck} {work}".replace("unknown ", "").strip() or "unknown design",
        "work_guess": work,
        "neck_guess": neck,
        "primary_label": pred.get("predicted_type") or "unknown_review",
        "confidence": pred.get("confidence"),
        "tags": tags,
        "stitch_summary": explanation,
        "reader": reader.get("reader") if isinstance(reader, dict) else reader,
        "engine": meta.get("engine"),
        "output_size": meta.get("output_size"),
    }


def _make_embroidery_record_from_meta(meta: Dict[str, Any], analysis: Dict[str, Any], fingerprint: Dict[str, Any], import_id: str, source_name: str, source: str) -> Dict[str, Any]:
    preview = Path(str(meta.get("output_path") or ""))
    rec = _make_design_record(image_path=preview, source_name=source_name, analysis=analysis, fingerprint=fingerprint, import_id=import_id)
    rec.update({
        "source": source,
        "source_type": "embroidery_file",
        "embroidery_path": str(meta.get("input_path") or ""),
        "original_source_path": str(meta.get("input_path") or ""),
        "preview_path": str(preview),
        "image_path": str(preview),
        "file_extension": Path(source_name).suffix.lower(),
        "stitches": int(meta.get("stitches") or 0),
        "estimated_thread_colors": meta.get("estimated_thread_colors"),
        "density_score": meta.get("density_score"),
        "bounds": meta.get("bounds") or {},
        "reader": meta.get("reader") or {},
        "converter_meta": meta,
        "meaningful_summary": _design_meaningful_summary(meta, analysis, "dst/embroidery"),
    })
    return rec


def import_embroidery_files_to_library(
    files: List[Any],
    *,
    import_name: str = "dst_upload",
    analyze: bool = True,
    build_fingerprints: bool = True,
    limit: int = 500,
    render_size: int = 2048,
    prefer_cpp: bool = True,
) -> Dict[str, Any]:
    """Main v5.4.4 import path: DST/PES/JEF/etc → render PNG → analyze → fingerprint → cache."""
    import_id = f"dst_{_utc_stamp()}_{hashlib.sha1(import_name.encode('utf-8','ignore')).hexdigest()[:8]}"
    out_dir = _library_dir() / "imports" / import_id
    out_dir.mkdir(parents=True, exist_ok=True)
    items: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []
    for uploaded in files[:int(limit)]:
        try:
            name = getattr(uploaded, "name", "design.dst")
            raw = uploaded.getvalue()
            meta = convert_uploaded_bytes(raw, name, out_dir, size=int(render_size), output_format="PNG", prefer_cpp=prefer_cpp)
            preview_path = Path(str(meta.get("output_path") or ""))
            with Image.open(preview_path) as im:
                img = ImageOps.exif_transpose(im).convert("RGB")
            analysis = _run_full_analysis(img, name) if analyze else {}
            fp = create_fingerprint_from_path(preview_path) if build_fingerprints and create_fingerprint_from_path is not None else {}
            rec = _make_embroidery_record_from_meta(meta, analysis, fp, import_id, name, "dst_imported_library")
            _json_write(_design_json_dir() / f"{rec['id']}.json", rec)
            items.append(rec)
        except Exception as exc:
            errors.append({"file": getattr(uploaded, "name", "uploaded"), "error": str(exc)[:240]})
    index = _upsert_index_items(items)
    _append_import_log({"import_id": import_id, "name": import_name, "source_type": "embroidery_files", "items": len(items), "errors": errors, "created_at": datetime.now(timezone.utc).isoformat()})
    if sync_library_cache is not None and items:
        try:
            sync_library_cache(APP_ROOT, index.get("items", []))
        except Exception:
            pass
    return {"import_id": import_id, "items": items, "errors": errors, "index_count": len(index.get("items", []))}


def import_embroidery_zip_to_library(
    payload: bytes,
    *,
    zip_name: str,
    analyze: bool = True,
    build_fingerprints: bool = True,
    limit: int = 500,
    render_size: int = 2048,
    prefer_cpp: bool = True,
) -> Dict[str, Any]:
    import_id = f"dstzip_{_utc_stamp()}_{hashlib.sha1(zip_name.encode('utf-8','ignore')).hexdigest()[:8]}"
    out_dir = _library_dir() / "imports" / import_id
    out_dir.mkdir(parents=True, exist_ok=True)
    items: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []
    for name, raw in _iter_zip_embroidery(payload, int(limit)):
        try:
            meta = convert_uploaded_bytes(raw, Path(name).name, out_dir, size=int(render_size), output_format="PNG", prefer_cpp=prefer_cpp)
            meta["source_zip"] = zip_name
            meta["zip_member"] = name
            preview_path = Path(str(meta.get("output_path") or ""))
            with Image.open(preview_path) as im:
                img = ImageOps.exif_transpose(im).convert("RGB")
            analysis = _run_full_analysis(img, Path(name).name) if analyze else {}
            fp = create_fingerprint_from_path(preview_path) if build_fingerprints and create_fingerprint_from_path is not None else {}
            rec = _make_embroidery_record_from_meta(meta, analysis, fp, import_id, Path(name).name, "dst_zip_imported_library")
            rec["zip_member"] = name
            rec["source_zip"] = zip_name
            _json_write(_design_json_dir() / f"{rec['id']}.json", rec)
            items.append(rec)
        except Exception as exc:
            errors.append({"file": name, "error": str(exc)[:240]})
    index = _upsert_index_items(items)
    _append_import_log({"import_id": import_id, "name": zip_name, "source_type": "embroidery_zip", "items": len(items), "errors": errors, "created_at": datetime.now(timezone.utc).isoformat()})
    if sync_library_cache is not None and items:
        try:
            sync_library_cache(APP_ROOT, index.get("items", []))
        except Exception:
            pass
    return {"import_id": import_id, "items": items, "errors": errors, "index_count": len(index.get("items", []))}


def scan_embroidery_folder_to_index(folder: str, *, analyze: bool = True, build_fingerprints: bool = True, limit: int = 2000, render_size: int = 2048, prefer_cpp: bool = True) -> Dict[str, Any]:
    root = Path(folder).expanduser()
    if not root.exists() or not root.is_dir():
        return {"items": [], "errors": [{"folder": str(root), "error": "folder not found"}], "index_count": len(_load_search_index().get("items", []))}
    import_id = f"dstfolder_{_utc_stamp()}"
    out_dir = _library_dir() / "imports" / import_id
    out_dir.mkdir(parents=True, exist_ok=True)
    items: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []
    paths = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in EMBROIDERY_EXTENSIONS]
    for path in paths[:int(limit)]:
        try:
            meta = render_embroidery_file(path, out_dir / f"{path.stem}_{int(time.time()*1000)}_{int(render_size)}px.png", size=int(render_size), output_format="PNG", prefer_cpp=prefer_cpp)
            meta.update({"input_path": str(path), "input_name": path.name, "input_sha1": hashlib.sha1(path.read_bytes()).hexdigest()})
            preview_path = Path(str(meta.get("output_path") or ""))
            with Image.open(preview_path) as im:
                img = ImageOps.exif_transpose(im).convert("RGB")
            analysis = _run_full_analysis(img, path.name) if analyze else {}
            fp = create_fingerprint_from_path(preview_path) if build_fingerprints and create_fingerprint_from_path is not None else {}
            rec = _make_embroidery_record_from_meta(meta, analysis, fp, import_id, path.name, "dst_scanned_folder")
            rec["folder_source"] = str(root)
            _json_write(_design_json_dir() / f"{rec['id']}.json", rec)
            items.append(rec)
        except Exception as exc:
            errors.append({"file": str(path), "error": str(exc)[:240]})
    index = _upsert_index_items(items)
    if sync_library_cache is not None and items:
        try:
            sync_library_cache(APP_ROOT, index.get("items", []))
        except Exception:
            pass
    _append_import_log({"import_id": import_id, "name": str(root), "source_type": "embroidery_folder", "items": len(items), "errors": errors[:25], "created_at": datetime.now(timezone.utc).isoformat()})
    return {"items": items, "errors": errors[:50], "index_count": len(index.get("items", []))}


def scan_folder_to_index(folder: str, *, analyze: bool = False, build_fingerprints: bool = True, limit: int = 2000) -> Dict[str, Any]:
    root = Path(folder).expanduser()
    if not root.exists() or not root.is_dir():
        return {"items": [], "errors": [{"folder": str(root), "error": "folder not found"}], "index_count": len(_load_search_index().get("items", []))}
    import_id = f"scan_{_utc_stamp()}"
    items: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []
    for path in list(root.rglob("*"))[: max(1, int(limit) * 3)]:
        if len(items) >= int(limit):
            break
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        try:
            with Image.open(path) as im:
                img = ImageOps.exif_transpose(im).convert("RGB")
            analysis = _run_full_analysis(img, path.name) if analyze else {}
            fp = create_fingerprint_from_path(path) if build_fingerprints and create_fingerprint_from_path is not None else {}
            rec = _make_design_record(image_path=path, source_name=path.name, analysis=analysis, fingerprint=fp, import_id=import_id)
            rec["source"] = "scanned_folder"
            items.append(rec)
        except Exception as exc:
            errors.append({"file": str(path), "error": str(exc)})
    index = _upsert_index_items(items)
    if sync_library_cache is not None and items:
        try:
            sync_library_cache(APP_ROOT, index.get("items", []))
        except Exception:
            pass
    return {"items": items, "errors": errors[:25], "index_count": len(index.get("items", []))}


def _entry_matches_query_class(entry: Dict[str, Any], query_analysis: Dict[str, Any], strict: bool) -> bool:
    if not strict:
        return True
    q_fields = _class_fields_from_analysis(query_analysis)
    q_tokens = set(str(x).lower() for x in q_fields.get("tags", []))
    q_tokens.add(str(q_fields.get("label") or "").lower())
    q_tokens.add(str(q_fields.get("work_type") or "").lower())
    q_tokens.add(str(q_fields.get("neck_type") or "").lower())
    e_tokens = set(str(x).lower() for x in _as_list(entry.get("tags")))
    for key in ("primary_label", "work_type", "neck_type", "dress_type"):
        e_tokens.add(str(entry.get(key) or "").lower())
    e_tokens.discard("")
    q_tokens.discard("")
    return bool(q_tokens & e_tokens) or str(entry.get("primary_label")) == "unknown_review"


def search_index_by_image(img: Image.Image, source_name: str, *, limit: int = 20, strict_type: bool = True) -> Dict[str, Any]:
    if create_fingerprint_from_image is None or compare_fingerprints is None:
        raise RuntimeError("Image Searcher engine is unavailable.")
    query_analysis = _run_full_analysis(img, source_name)
    qfp = create_fingerprint_from_image(img)
    index = _load_search_index()
    candidates = []
    for entry in _as_list(index.get("items")):
        if not _entry_matches_query_class(entry, query_analysis, strict_type):
            continue
        fp = entry.get("fingerprint") or {}
        path = Path(str(entry.get("image_path") or ""))
        if not fp and path.exists() and create_fingerprint_from_path is not None:
            try:
                fp = create_fingerprint_from_path(path)
                entry["fingerprint"] = fp
            except Exception:
                fp = {}
        if not fp:
            continue
        try:
            score = compare_fingerprints(qfp, fp)
        except Exception:
            continue
        row = dict(entry)
        row["match"] = score
        row["match_score"] = float(score.get("score") or 0)
        row["match_label"] = score.get("label")
        candidates.append(row)
    candidates.sort(key=lambda x: float(x.get("match_score") or 0), reverse=True)
    return {"query_analysis": query_analysis, "query_fingerprint": qfp, "results": candidates[:int(limit)], "searched": len(candidates), "index_total": len(_as_list(index.get("items")))}


def animated_stepper(title: str, steps: List[str], active: int = 0) -> None:
    pieces = []
    for i, step in enumerate(steps):
        state = "done" if i < active else "active" if i == active else "todo"
        pieces.append(f'<div class="emb-step {state}"><span>{i+1}</span><b>{step}</b></div>')
    st.markdown(f'<div class="emb-stepper"><h4>{title}</h4><div class="emb-step-row">' + "".join(pieces) + "</div></div>", unsafe_allow_html=True)


def _preview_import_rows(items: List[Dict[str, Any]], limit: int = 30) -> List[Dict[str, Any]]:
    rows = []
    for item in items[:limit]:
        ms = item.get("meaningful_summary") or {}
        rows.append({
            "design": item.get("design_no"),
            "source": item.get("source_type") or item.get("source"),
            "student_name": ms.get("student_name") or item.get("primary_label"),
            "label": item.get("primary_label"),
            "work": ms.get("work_guess") or item.get("work_type"),
            "neck": ms.get("neck_guess") or item.get("neck_type"),
            "stitches": item.get("stitches"),
            "colors": item.get("estimated_thread_colors"),
            "summary": ms.get("stitch_summary"),
            "mode": item.get("image_mode"),
            "tags": ", ".join(_as_list(item.get("tags"))[:8]),
        })
    return rows

# -----------------------------
# Page setup + styling
# -----------------------------

def init_page() -> None:
    st.set_page_config(
        page_title=f"{APP_NAME} {APP_VERSION}",
        page_icon="🧵",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(
        """
        <style>
        [data-testid="stSidebarNav"], section[data-testid="stSidebar"] nav {display:none !important;}
        .block-container {padding-top: 1.35rem; max-width: 1320px;}
        [data-testid="stSidebar"] {background: linear-gradient(180deg,#0f172a,#111827);}
        [data-testid="stSidebar"] * {color:#e5edf8;}
        [data-testid="stSidebar"] label[data-baseweb="radio"] {
          border:1px solid rgba(255,255,255,.10); border-radius:14px; padding:.5rem .65rem; margin:.12rem 0;
          background:rgba(255,255,255,.04);
        }
        [data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked) {
          background:linear-gradient(135deg,#f59e0b,#f97316); color:#111827 !important; font-weight:900;
        }
        .emb-hero {border:1px solid #e2e8f0; border-radius:24px; padding:1.25rem 1.35rem; background:linear-gradient(135deg,#fff7ed,#eef2ff 55%,#ecfeff); box-shadow:0 20px 50px rgba(15,23,42,.08);}
        .emb-hero h1 {margin:0; font-size:2.1rem; letter-spacing:-.05em; color:#0f172a;}
        .emb-muted {color:#64748b;}
        .emb-card {border:1px solid #e2e8f0; border-radius:20px; padding:1rem; background:#fff; box-shadow:0 12px 30px rgba(15,23,42,.05);}
        .emb-pill {display:inline-block; padding:.25rem .6rem; border-radius:999px; background:#0f172a; color:white; font-size:.78rem; font-weight:800; margin:.15rem .2rem .15rem 0;}
        .emb-good {background:#dcfce7; color:#166534;}
        .emb-warn {background:#fef3c7; color:#92400e;}
        .emb-bad {background:#fee2e2; color:#991b1b;}
        .stButton>button {border-radius:999px; font-weight:800;}

        .emb-loader-wrap {
          display:flex; align-items:center; gap:1rem; margin:.65rem 0 1rem 0; padding:.85rem 1rem;
          border:1px solid rgba(14,165,233,.22); border-radius:20px;
          background:linear-gradient(135deg,rgba(236,254,255,.95),rgba(255,247,237,.95));
          box-shadow:0 14px 36px rgba(15,23,42,.08); overflow:hidden; position:relative;
        }
        .emb-loader-wrap:before {
          content:""; position:absolute; inset:0; pointer-events:none;
          background:linear-gradient(90deg,transparent,rgba(255,255,255,.55),transparent);
          transform:translateX(-100%); animation:embShimmer 1.9s infinite;
        }
        .emb-loader-stage {width:92px; height:42px; position:relative; flex:0 0 92px;}
        .emb-thread {
          position:absolute; left:6px; top:23px; width:78px; height:3px; border-radius:999px;
          background:linear-gradient(90deg,#06b6d4,#22c55e,#f59e0b,#ec4899);
          animation:embThread 1.25s infinite ease-in-out;
          box-shadow:0 0 12px rgba(6,182,212,.42);
        }
        .emb-needle {
          position:absolute; top:7px; left:10px; width:38px; height:4px; border-radius:999px;
          background:#334155; transform-origin:right center; animation:embNeedle 1.25s infinite ease-in-out;
        }
        .emb-needle:after {
          content:""; position:absolute; right:-8px; top:-3px; border-left:11px solid #334155;
          border-top:5px solid transparent; border-bottom:5px solid transparent;
        }
        .emb-stitch {
          position:absolute; bottom:6px; width:10px; height:20px; border-left:3px solid #0ea5e9;
          border-radius:50%; opacity:.28; animation:embStitch 1.25s infinite ease-in-out;
        }
        .emb-stitch.s1 {left:15px; animation-delay:0s;}
        .emb-stitch.s2 {left:32px; animation-delay:.15s; border-left-color:#22c55e;}
        .emb-stitch.s3 {left:49px; animation-delay:.3s; border-left-color:#f59e0b;}
        .emb-stitch.s4 {left:66px; animation-delay:.45s; border-left-color:#ec4899;}
        .emb-dot {position:absolute; width:8px; height:8px; border-radius:50%; background:#0ea5e9; animation:embDot 1.25s infinite ease-in-out;}
        .emb-dot.d1 {left:20px; top:5px; background:#22c55e; animation-delay:.05s;}
        .emb-dot.d2 {left:48px; top:2px; background:#f59e0b; animation-delay:.23s;}
        .emb-dot.d3 {left:73px; top:8px; background:#ec4899; animation-delay:.41s;}
        .emb-loader-copy strong {display:block; color:#0f172a; font-size:1rem; letter-spacing:-.01em;}
        .emb-loader-detail {color:#475569; font-size:.86rem; margin-top:.12rem;}
        .emb-loader-small {padding:.55rem .7rem; gap:.65rem; border-radius:16px;}
        .emb-loader-small .emb-loader-stage {transform:scale(.78); transform-origin:left center; width:74px; height:34px;}
        .emb-loader-small .emb-loader-copy strong {font-size:.9rem;}
        @keyframes embShimmer {0%{transform:translateX(-100%);} 100%{transform:translateX(100%);}}
        @keyframes embNeedle {0%{transform:translateX(0) rotate(-10deg);} 45%{transform:translateX(38px) rotate(11deg);} 100%{transform:translateX(0) rotate(-10deg);}}
        @keyframes embThread {0%,100%{transform:scaleX(.82); opacity:.75;} 50%{transform:scaleX(1.05); opacity:1;}}
        @keyframes embStitch {0%,100%{opacity:.25; transform:translateY(3px) scaleY(.72);} 50%{opacity:1; transform:translateY(-2px) scaleY(1.1);}}
        @keyframes embDot {0%,100%{transform:translateY(0) scale(.75); opacity:.45;} 50%{transform:translateY(20px) scale(1); opacity:1;}}

        .emb-stepper {border:1px solid #e2e8f0; border-radius:20px; padding:1rem; background:#fff; margin:.7rem 0 1rem 0;}
        .emb-stepper h4 {margin:.05rem 0 .8rem 0; color:#0f172a;}
        .emb-step-row {display:flex; flex-wrap:wrap; gap:.55rem;}
        .emb-step {display:flex; align-items:center; gap:.45rem; padding:.45rem .65rem; border-radius:999px; border:1px solid #e2e8f0; color:#475569; background:#f8fafc;}
        .emb-step span {width:1.35rem; height:1.35rem; border-radius:50%; display:inline-flex; align-items:center; justify-content:center; background:#e2e8f0; font-size:.78rem; font-weight:900;}
        .emb-step.done {background:#dcfce7; border-color:#86efac; color:#166534;}
        .emb-step.done span {background:#22c55e; color:white;}
        .emb-step.active {background:#fff7ed; border-color:#fdba74; color:#9a3412; box-shadow:0 0 0 4px rgba(249,115,22,.10); animation:embPulse 1.35s infinite;}
        .emb-step.active span {background:#f97316; color:white;}
        @keyframes embPulse {0%,100%{transform:translateY(0);} 50%{transform:translateY(-2px);}}
        .emb-mini-grid {display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:.75rem; margin:.75rem 0;}
        .emb-mini-card {border:1px solid #e2e8f0; border-radius:18px; padding:.85rem; background:linear-gradient(135deg,#ffffff,#f8fafc);}
        .emb-mini-card b {display:block; color:#0f172a; margin-bottom:.2rem;}
        .emb-mini-card span {color:#64748b; font-size:.86rem;}

        </style>
        """,
        unsafe_allow_html=True,
    )


def sidebar_nav() -> str:
    with st.sidebar:
        logo = APP_ROOT / "static" / "logo.png"
        if logo.exists():
            st.image(str(logo), use_container_width=True)
        st.markdown(f"### {APP_NAME}")
        st.caption(f"{APP_VERSION} · Full Site Alive")
        nav = st.radio(
            "Navigation",
            [
                "Dashboard",
                "DST to PNG Converter",
                "4K Design Reader",
                "Import Library",
                "Image Searcher",
                "TurboThinker GUI",
                "Interactive Searcher",
                "IMGS Training BETA",
                "Teach / Train",
                "Maximum Library Manager",
                "Library Cache",
                "Google Drive",
                "Gmail Sign In",
                "Brain Parts",
                "Settings",
            ],
            label_visibility="collapsed",
        )
        st.divider()
        st.caption("Local-only · no API · no filename-label learning")
    return nav


def hero(title: str, text: str = "") -> None:
    st.markdown(
        f"""
        <div class="emb-hero">
          <h1>{title}</h1>
          <p class="emb-muted">{text}</p>
          <span class="emb-pill">{APP_VERSION}</span>
          <span class="emb-pill">24MB brain parts</span>
          <span class="emb-pill">TurboThinker SuperBrain</span>
          <span class="emb-pill">Interactive Searcher</span>
          <span class="emb-pill">Import + Image Searcher</span>
          <span class="emb-pill">Full site alive</span>
          <span class="emb-pill">DST→PNG</span>
          <span class="emb-pill">Google Drive/Gmail</span>
          <span class="emb-pill">4K C++ Reader</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write("")


# -----------------------------
# Pages
# -----------------------------

def dashboard_page() -> None:
    hero("EMBORGANIZER Full Site", "v5.4.4 restores the full site with DST as the main import source: DST/PES/JEF folder import, ZIP import, 4K C++ reader, meaningful design summaries, Image Searcher, TurboThinker teacher-rule identification, Google Drive/Gmail, Library Manager, cache tools, and loading animations.")
    st.info(IMGS_TRAINING_WARNING)
    with animated_loader("Loading TurboThinker brain status…", "Checking seed bank, corrections, SuperBrain memory, and 24MB brain parts", small=True):
        s = load_all_summaries()
    seed_summary = (s.get("seed") or {}).get("summary") or {}
    student = s.get("student") or {}
    ultra = s.get("ultrabrain") or {}
    super_s = s.get("superbrain") or {}
    parts = s.get("brain_parts") or {}

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Seed images", f"{int(seed_summary.get('images_indexed') or 0):,}")
    c2.metric("Corrections", f"{int((s.get('corrections') or {}).get('count') or 0):,}")
    c3.metric("SuperBrain memory", f"{int(super_s.get('memory_rows') or super_s.get('knn_memory_rows') or 0):,}")
    c4.metric("Brain parts", f"{int(parts.get('parts_count') or 0)}")

    left, right = st.columns([1.15, .85])
    with left:
        st.markdown("#### Current engine")
        st.markdown(f"**IMGS:** `{IMGS_TRAINING_VERSION}`")
        st.markdown(f"**TurboThinker:** `{TURBOTHINKER_ENGINE_VERSION}`")
        st.markdown(f"**SuperBrain:** `{SUPERBRAIN_VERSION}`")
        if parts.get("ok"):
            st.success(f"Brain-part model is GitHub-safe. Largest/part checked under 25 MB. Total: {parts.get('total_mb')} MB")
        else:
            st.warning("Brain-part manifest is missing or a part failed the under-25MB check.")
    with right:
        st.markdown("#### Model summaries")
        st.json({
            "student": {k: student.get(k) for k in ("exists", "labels", "rows", "epochs") if k in student},
            "ultrabrain": {k: ultra.get(k) for k in ("exists", "labels_with_weights", "knn_memory_rows", "rows") if k in ultra},
            "superbrain": {k: super_s.get(k) for k in ("exists", "labels", "memory_rows", "cortex_features", "training_rows") if k in super_s},
            "brain_parts": parts,
        })

    st.markdown("#### Clean UI kept")
    st.write("Dashboard · DST Import Library · DST/Image Searcher · TurboThinker GUI · Interactive Searcher · IMGS Training BETA · Teach/Train · Library Cache · Brain Parts · Settings")
    st.markdown("#### Removed from visible UI")
    st.write("Only external API/sign-in pages remain hidden. Local import, local image search, local training, selector reader, and cache pages are restored inside the clean main GUI.")


def turbothinker_gui_page() -> None:
    hero("TurboThinker GUI", "Upload one embroidery preview/image, see the local prediction, then save a correction if needed.")
    uploaded = st.file_uploader("Upload image for visual recognition", type=SUPPORTED_IMAGE_TYPES)
    if not uploaded:
        st.caption("Use this page to test one image after every training round.")
        return

    img = _image_from_upload(uploaded)
    c_img, c_result = st.columns([.85, 1.15])
    with c_img:
        st.image(img, caption=uploaded.name, use_container_width=True)
    with c_result:
        with animated_loader("TurboThinker is reading the design…", "Scanning neck shape, work type, motifs, borders, and teacher memory"):
            analysis = _run_full_analysis(img, uploaded.name)
        st.session_state["last_analysis"] = analysis
        st.session_state["last_image"] = img
        st.session_state["last_source_name"] = uploaded.name
        _show_prediction_card(analysis)
        _show_identification_breakdown(analysis)

    st.divider()
    st.markdown("### Teacher correction")
    pred = (analysis.get("prediction") or {})
    default_label = str(pred.get("predicted_type") or "unknown_review")
    if default_label not in IMGS_LABELS:
        default_label = "unknown_review"
    col1, col2 = st.columns([.8, 1.2])
    with col1:
        final_label = st.selectbox("Correct primary label", IMGS_LABELS, index=IMGS_LABELS.index(default_label))
        auto_remove = st.checkbox("Auto-remove weak leftover tags", value=True)
        min_score = st.slider("Weak tag cutoff", 0.05, 0.75, 0.24, 0.01)
    with col2:
        manual_tags_raw = st.text_input("Extra correct tags", placeholder="flower_border, back_neck, net_work")
        notes = st.text_area("Teacher notes", placeholder="Why this label is correct…", height=80)
    if st.button("Save teacher correction", type="primary"):
        sample_id, sample_path = save_uploaded_training_image(APP_ROOT, img, uploaded.name)
        manual_tags = [x.strip() for x in manual_tags_raw.split(",") if x.strip()]
        saved = record_training_correction(
            APP_ROOT,
            sample_id=sample_id,
            source_name=uploaded.name,
            analysis=analysis,
            final_label=final_label,
            notes=notes,
            sample_image_path=str(sample_path),
            manual_tags=manual_tags,
            auto_remove_low_tags=auto_remove,
            tag_min_score=float(min_score),
        )
        st.success(f"Saved correction: {saved.get('final_label')} · sample {saved.get('sample_id')}")

    with st.expander("Fixed crop / selector reader"):
        st.caption("Enter crop coordinates to test only one area of the image. This is useful for sleeves, borders, neck curves, butti, flowers, or net-work.")
        w, h = img.size
        c1, c2, c3, c4 = st.columns(4)
        x0 = c1.number_input("x0", min_value=0, max_value=max(0, w - 1), value=0)
        y0 = c2.number_input("y0", min_value=0, max_value=max(0, h - 1), value=0)
        x1 = c3.number_input("x1", min_value=1, max_value=w, value=w)
        y1 = c4.number_input("y1", min_value=1, max_value=h, value=h)
        if st.button("Analyze selected area"):
            box = (int(x0), int(y0), int(x1), int(y1))
            result = analyze_selector_area(img, source_name=f"{uploaded.name}::selector", box=box)
            st.image(img.crop(box), caption=f"Selected area {box}", use_container_width=True)
            st.write("Tags: " + " · ".join(f"`{x}`" for x in _as_list(result.get("selector_tags"))))
            for r in _as_list(result.get("selector_reasons")):
                st.write("• " + str(r))
            st.session_state["last_selector_result"] = result
        if st.button("Save selected area training"):
            result = st.session_state.get("last_selector_result")
            if not result:
                st.warning("Analyze a selected area first.")
            else:
                parent_id = _sample_id_for_image(img, uploaded.name)
                saved = record_selector_area_training(APP_ROOT, parent_id, uploaded.name, result)
                st.success(f"Saved selector training area: {saved.get('area_id')}")


def interactive_searcher_page() -> None:
    hero(
        "Interactive Searcher",
        "Search design numbers, neck names, work types, teacher rules, saved corrections, and local image folders.",
    )
    st.caption(str(SEARCHER_VERSION))
    if build_search_records is None or search_records is None:
        st.error("Interactive Searcher module is unavailable.")
        return

    with st.expander("Teacher rules used by v5.4", expanded=False):
        cards = rule_cards(APP_ROOT) if rule_cards is not None else []
        if cards:
            for row in cards:
                st.markdown(f"**{row.get('name')}** — {row.get('rule')}")
        else:
            st.info("No teacher-rule memory file found yet.")

    st.markdown("### Search controls")
    c0, c1, c2 = st.columns([1.25, 0.85, 0.85])
    with c0:
        query = st.text_input(
            "Search words or design number",
            placeholder="HB2257 cut work, pot neck net work, rangoli, kurta, drop neck...",
        )
    with c1:
        work_type = st.selectbox("Work type", WORK_TYPE_OPTIONS, index=0)
    with c2:
        neck_type = st.selectbox("Neck type", NECK_TYPE_OPTIONS, index=0)

    c3, c4, c5 = st.columns([0.85, 0.85, 1.3])
    with c3:
        dress_type = st.selectbox("Dress type", DRESS_TYPE_OPTIONS, index=0)
    with c4:
        feature = st.selectbox("Feature", FEATURE_OPTIONS, index=0)
    with c5:
        extra_dir = st.text_input("Optional folder to scan", placeholder="C:/designs or /home/me/designs")

    c6, c7, c8, c9 = st.columns(4)
    include_memory = c6.checkbox("Teacher memory", value=True)
    include_corrections = c7.checkbox("Corrections", value=True)
    include_index = c8.checkbox("Training index", value=True)
    include_images = c9.checkbox("Scan image files", value=False)

    c10, c11 = st.columns([0.85, 0.85])
    confirmed_only = c10.checkbox("Teacher-confirmed only", value=False)
    limit = c11.slider("Result limit", 5, 100, 30, 5)

    extra_dirs = [extra_dir] if extra_dir.strip() else []
    loader_detail = "Reading teacher memory, corrections, training index"
    if include_images or extra_dirs:
        loader_detail += ", and local image folders"
    with animated_loader("Searching/loading design database…", loader_detail, small=True):
        records = build_search_records(
            APP_ROOT,
            include_teacher_memory=include_memory,
            include_corrections=include_corrections,
            include_training_index=include_index,
            include_local_images=include_images,
            extra_dirs=extra_dirs,
        )
        summary = summarize_records(records) if summarize_records is not None else {"records": len(records)}

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Search records", f"{int(summary.get('records') or 0):,}")
    m2.metric("Teacher-confirmed", f"{int(summary.get('teacher_confirmed') or 0):,}")
    m3.metric("Work groups", f"{len(summary.get('by_work_type') or {})}")
    m4.metric("Neck groups", f"{len(summary.get('by_neck_type') or {})}")

    if infer_query_facets is not None and query.strip():
        facets = infer_query_facets(query)
        with st.expander("What the searcher understood from your query"):
            st.json(facets)

    with animated_loader("Matching your search…", "Applying design number, work type, neck type, and feature filters", small=True):
        results = search_records(
            records,
            query=query,
            work_type=work_type,
            neck_type=neck_type,
            dress_type=dress_type,
            feature=feature,
            confirmed_only=confirmed_only,
            limit=int(limit),
        )

    st.markdown(f"### Results ({len(results)})")
    if not results:
        st.warning("No matching design found. Try fewer filters or scan a local folder.")
        return

    compact_rows = []
    for row in results:
        compact_rows.append({
            "design": row.get("design_no") or "",
            "answer": student_answer_for(row) if student_answer_for is not None else row.get("student_answer"),
            "neck": row.get("neck_type") or "",
            "work": row.get("work_type") or "",
            "dress": row.get("dress_type") or "",
            "confirmed": bool(row.get("teacher_confirmed")),
            "source": row.get("source") or "",
            "score": row.get("search_score") or 0,
        })
    st.dataframe(compact_rows, use_container_width=True, hide_index=True)

    st.markdown("### Result cards")
    for i, row in enumerate(results[:20], start=1):
        title = student_answer_for(row) if student_answer_for is not None else str(row.get("student_answer") or "Design")
        with st.container(border=True):
            c_img, c_text = st.columns([0.32, 1.0])
            with c_img:
                image_path = row.get("image_path")
                if image_path and Path(str(image_path)).exists():
                    st.image(str(image_path), use_container_width=True)
                else:
                    st.markdown("🧵")
                    st.caption("No local preview")
            with c_text:
                confirmed = "✅ teacher confirmed" if row.get("teacher_confirmed") else "🟡 draft / local record"
                st.markdown(f"#### {i}. {row.get('design_no') or 'Design'} — {title}")
                st.caption(f"{confirmed} · {row.get('source')}")
                cc1, cc2, cc3 = st.columns(3)
                cc1.markdown(f"**Neck:** `{row.get('neck_type')}`")
                cc2.markdown(f"**Work:** `{row.get('work_type')}`")
                cc3.markdown(f"**Dress:** `{row.get('dress_type')}`")
                features = row.get("features") or row.get("tags") or []
                if features:
                    st.write("Features: " + " · ".join(f"`{x}`" for x in list(features)[:16]))
                if row.get("notes"):
                    st.caption(str(row.get("notes")))
                reasons = row.get("match_reasons") or []
                if reasons:
                    st.caption("Match: " + " | ".join(str(x) for x in reasons[:5]))

    with st.expander("Search database summary"):
        st.json(summary)


def import_library_page() -> None:
    hero("DST Import Library", "DST/PES/JEF/etc. are now the main source. The app renders stitch files to PNG, reads stitch stats, runs TurboThinker, builds fingerprints, and stores meaningful searchable records.")
    animated_stepper("DST import pipeline", ["Upload/Folder", "Render DST", "Read design", "Fingerprint", "Index"], active=0)
    st.info("Local-only import. File name is saved only as a record name; the design label comes from rendered visual analysis + teacher rules/corrections.")

    emb_types = sorted([x.lstrip(".") for x in EMBROIDERY_EXTENSIONS])
    mode = st.radio(
        "Import source",
        ["DST / embroidery files", "ZIP of DST / embroidery", "Scan local DST folder", "Image files (legacy)", "Image ZIP (legacy)", "Scan image folder (legacy)"],
        horizontal=False,
    )
    c1, c2, c3, c4, c5 = st.columns(5)
    analyze = c1.checkbox("Auto visual analysis", value=True)
    build_fp = c2.checkbox("Build fingerprints", value=True)
    limit = c3.number_input("Import limit", min_value=1, max_value=100000, value=300, step=50)
    render_size = int(c4.selectbox("DST render size", ["1024", "2048", "4096"], index=1))
    prefer_cpp = c5.checkbox("C++ Turbo", value=True)
    show_preview = st.checkbox("Show imported table", value=True)

    if mode == "DST / embroidery files":
        files = st.file_uploader("Upload DST/PES/JEF/etc. files", type=emb_types, accept_multiple_files=True, key="import_dst_files")
        if files and st.button("Import DST files to searchable library", type="primary"):
            bar = st.progress(0, text="Preparing DST import…")
            animated_stepper("DST import pipeline", ["Upload", "Render", "Read", "Fingerprint", "Search ready"], active=1)
            with animated_loader("Importing DST files…", "Rendering stitch files, reading density/colors/bounds, and building local search cache"):
                bar.progress(15, text="Uploaded DST files")
                result = import_embroidery_files_to_library(files, import_name="dst_upload", analyze=analyze, build_fingerprints=build_fp, limit=int(limit), render_size=render_size, prefer_cpp=prefer_cpp)
                bar.progress(100, text="DST import complete")
            st.success(f"Imported {len(result.get('items', [])):,} stitch designs. Search index now has {result.get('index_count', 0):,} records.")
            if result.get("errors"):
                st.warning(f"Some DST files could not import: {len(result['errors'])}")
                st.dataframe(result["errors"], use_container_width=True, hide_index=True)
            if show_preview and result.get("items"):
                st.dataframe(_preview_import_rows(result["items"]), use_container_width=True, hide_index=True)
                for item in result["items"][:6]:
                    with st.container(border=True):
                        cc1, cc2 = st.columns([0.38, 1.0])
                        with cc1:
                            pth = Path(str(item.get("preview_path") or item.get("image_path") or ""))
                            if pth.exists():
                                st.image(str(pth), use_container_width=True)
                        with cc2:
                            st.markdown(f"#### {item.get('source_name')}")
                            st.write((item.get("meaningful_summary") or {}).get("stitch_summary") or "Rendered DST preview.")
                            st.write("Tags: " + " · ".join(f"`{x}`" for x in _as_list(item.get("tags"))[:10]))

    elif mode == "ZIP of DST / embroidery":
        zip_file = st.file_uploader("Upload ZIP containing DST/PES/JEF/etc.", type=["zip"], key="import_dst_zip")
        if zip_file and st.button("Import DST ZIP to searchable library", type="primary"):
            bar = st.progress(0, text="Opening DST ZIP…")
            animated_stepper("DST ZIP pipeline", ["Upload", "Extract DST", "Render", "Fingerprint", "Index"], active=1)
            with animated_loader("Importing DST ZIP…", "Extracting stitch files, rendering previews, analyzing, and indexing"):
                bar.progress(12, text="ZIP uploaded")
                result = import_embroidery_zip_to_library(zip_file.getvalue(), zip_name=zip_file.name, analyze=analyze, build_fingerprints=build_fp, limit=int(limit), render_size=render_size, prefer_cpp=prefer_cpp)
                bar.progress(100, text="DST ZIP import complete")
            st.success(f"Imported {len(result.get('items', [])):,} stitch designs from ZIP. Search index now has {result.get('index_count', 0):,} records.")
            if result.get("errors"):
                with st.expander("Import errors"):
                    st.dataframe(result["errors"], use_container_width=True, hide_index=True)
            if show_preview and result.get("items"):
                st.dataframe(_preview_import_rows(result["items"]), use_container_width=True, hide_index=True)

    elif mode == "Scan local DST folder":
        folder = st.text_input("Local folder path containing DST/PES/JEF/etc.", placeholder="C:/designs/dst or /home/me/designs")
        st.caption("Folder path works when you run EMBORGANIZER on your own computer/server. Browser folder upload is handled by the file uploader/ZIP import.")
        if st.button("Scan DST folder into search cache", type="primary"):
            if not folder.strip():
                st.warning("Enter a local folder path first.")
            else:
                with animated_loader("Scanning DST folder…", "Rendering every stitch file, reading stats, and updating cache"):
                    result = scan_embroidery_folder_to_index(folder, analyze=analyze, build_fingerprints=build_fp, limit=int(limit), render_size=render_size, prefer_cpp=prefer_cpp)
                st.success(f"Added {len(result.get('items', [])):,} stitch records. Search index now has {result.get('index_count', 0):,} records.")
                if result.get("errors"):
                    with st.expander("Scan errors"):
                        st.dataframe(result["errors"], use_container_width=True, hide_index=True)
                if show_preview and result.get("items"):
                    st.dataframe(_preview_import_rows(result["items"]), use_container_width=True, hide_index=True)

    elif mode == "Image files (legacy)":
        files = st.file_uploader("Upload one or more embroidery images", type=SUPPORTED_IMAGE_TYPES, accept_multiple_files=True, key="import_images")
        if files and st.button("Import images to searchable library", type="primary"):
            bar = st.progress(0, text="Preparing image import…")
            with animated_loader("Importing images…", "Saving images, reading visually, and creating local fingerprints"):
                result = import_images_to_library(files, import_name="image_upload", analyze=analyze, build_fingerprints=build_fp, limit=int(limit))
                bar.progress(100, text="Import complete")
            st.success(f"Imported {len(result.get('items', [])):,} images. Search index now has {result.get('index_count', 0):,} records.")
            if result.get("errors"):
                st.dataframe(result["errors"], use_container_width=True, hide_index=True)
            if show_preview and result.get("items"):
                st.dataframe(_preview_import_rows(result["items"]), use_container_width=True, hide_index=True)

    elif mode == "Image ZIP (legacy)":
        zip_file = st.file_uploader("Upload ZIP of embroidery images", type=["zip"], key="import_zip")
        if zip_file and st.button("Import image ZIP to searchable library", type="primary"):
            with animated_loader("Importing image ZIP…", "Extracting images, analyzing design type, and building fingerprints"):
                result = import_zip_to_library(zip_file.getvalue(), zip_name=zip_file.name, analyze=analyze, build_fingerprints=build_fp, limit=int(limit))
            st.success(f"Imported {len(result.get('items', [])):,} images from ZIP. Search index now has {result.get('index_count', 0):,} records.")
            if result.get("errors"):
                with st.expander("Import errors"):
                    st.dataframe(result["errors"], use_container_width=True, hide_index=True)
            if show_preview and result.get("items"):
                st.dataframe(_preview_import_rows(result["items"]), use_container_width=True, hide_index=True)

    else:
        folder = st.text_input("Local image folder path to scan", placeholder="C:/designs/previews or /home/me/designs")
        if st.button("Scan image folder into search cache", type="primary"):
            if not folder.strip():
                st.warning("Enter a local folder path first.")
            else:
                with animated_loader("Scanning image folder…", "Reading images and adding them to the fast search cache"):
                    result = scan_folder_to_index(folder, analyze=analyze, build_fingerprints=build_fp, limit=int(limit))
                st.success(f"Added {len(result.get('items', [])):,} records. Search index now has {result.get('index_count', 0):,} records.")
                if result.get("errors"):
                    with st.expander("Scan errors"):
                        st.dataframe(result["errors"], use_container_width=True, hide_index=True)
                if show_preview and result.get("items"):
                    st.dataframe(_preview_import_rows(result["items"]), use_container_width=True, hide_index=True)

    st.divider()
    index = _load_search_index()
    items = _as_list(index.get("items"))
    dst_count = sum(1 for x in items if str(x.get("source_type") or "").startswith("embroidery") or str(x.get("file_extension") or "").lower() in EMBROIDERY_EXTENSIONS)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Cached designs", f"{len(items):,}")
    c2.metric("DST/stitch records", f"{dst_count:,}")
    c3.metric("Design JSON", f"{len(list(_design_json_dir().glob('*.json'))):,}")
    c4.metric("Image search", "ready" if compare_fingerprints is not None else "missing")

    with st.expander("Recent imports"):
        st.json(_json_read(_import_log_path(), {"imports": []}))


def image_searcher_page() -> None:
    hero("DST / Image Searcher", "Search the local library with a DST/PES/JEF file or an image. DST queries are rendered first, then classified and matched against cached previews.")
    st.caption(str(IMAGE_SEARCH_VERSION))
    index = _load_search_index()
    total = len(_as_list(index.get("items")))
    if total == 0:
        st.warning("Your search cache is empty. Use Import Library first, then come back here.")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Search cache", f"{total:,}")
    strict_type = c2.checkbox("Divide-and-rule type filter", value=True, help="First classify the query, then search matching type/tag records first.")
    limit = c3.slider("Top matches", 5, 80, 20, 5)
    render_size = int(c4.selectbox("DST query render", ["1024", "2048", "4096"], index=1))

    query_kind = st.radio("Search by", ["DST / embroidery file", "Image file"], horizontal=True)
    img: Optional[Image.Image] = None
    source_name = "query"
    query_meta: Dict[str, Any] = {}

    if query_kind == "DST / embroidery file":
        emb_types = sorted([x.lstrip(".") for x in EMBROIDERY_EXTENSIONS])
        uploaded = st.file_uploader("Upload query DST/PES/JEF/etc.", type=emb_types, key="query_dst_searcher")
        if not uploaded:
            st.caption("Upload a DST file → render → TurboThinker identifies → IMGS searches imported cache.")
            return
        out_dir = _exports_dir("query_dst")
        with animated_loader("Rendering query DST…", "Converting stitch file to clean PNG before search", small=True):
            query_meta = convert_uploaded_bytes(uploaded.getvalue(), uploaded.name, out_dir, size=render_size, output_format="PNG", prefer_cpp=True)
        source_name = uploaded.name
        with Image.open(str(query_meta.get("output_path"))) as im:
            img = ImageOps.exif_transpose(im).convert("RGB")
    else:
        uploaded = st.file_uploader("Upload query image to search", type=SUPPORTED_IMAGE_TYPES, key="query_image_searcher")
        if not uploaded:
            st.caption("Upload query image → visual read → fingerprint → match cache.")
            return
        img = _image_from_upload(uploaded)
        source_name = uploaded.name

    left, right = st.columns([0.8, 1.2])
    with left:
        st.image(img, caption=source_name, use_container_width=True)
        if query_meta:
            st.caption(_design_meaningful_summary(query_meta, {}, "query_dst").get("stitch_summary"))
    with right:
        animated_stepper("Searcher pipeline", ["Render/read", "Classify", "Fingerprint", "Filter cache", "Rank matches"], active=1)
        with animated_loader("Searching visually…", "TurboThinker is identifying first, then IMGS compares fingerprints"):
            result = search_index_by_image(img, source_name, limit=int(limit), strict_type=strict_type)
        if query_meta:
            result["query_meta"] = query_meta
        _show_prediction_card(result.get("query_analysis") or {})
        _show_identification_breakdown(result.get("query_analysis") or {})
        st.success(f"Searched {result.get('searched', 0):,} filtered candidates from {result.get('index_total', 0):,} cached records.")

    results = result.get("results") or []
    st.markdown(f"### Top matches ({len(results)})")
    if not results:
        st.info("No visual match found yet. Import more DST designs or turn off divide-and-rule type filter.")
        return
    table = []
    for row in results:
        ms = row.get("meaningful_summary") or {}
        table.append({
            "design": row.get("design_no"),
            "score": row.get("match_score"),
            "match": row.get("match_label"),
            "source": row.get("source_type") or row.get("source"),
            "student_name": ms.get("student_name") or row.get("primary_label"),
            "label": row.get("primary_label"),
            "work": ms.get("work_guess") or row.get("work_type"),
            "neck": ms.get("neck_guess") or row.get("neck_type"),
            "stitches": row.get("stitches"),
            "path": row.get("relative_path") or row.get("image_path"),
        })
    st.dataframe(table, use_container_width=True, hide_index=True)

    for i, row in enumerate(results[:12], start=1):
        with st.container(border=True):
            c_img, c_text = st.columns([0.35, 1.0])
            with c_img:
                path = Path(str(row.get("image_path") or row.get("preview_path") or ""))
                if path.exists():
                    st.image(str(path), use_container_width=True)
                else:
                    st.caption("Preview missing")
            with c_text:
                st.markdown(f"#### {i}. {row.get('design_no')} — {row.get('match_score')}%")
                ms = row.get("meaningful_summary") or {}
                st.caption(f"{row.get('match_label')} · {ms.get('student_name') or row.get('primary_label')} · {row.get('source')}")
                if ms.get("stitch_summary"):
                    st.write(ms.get("stitch_summary"))
                st.write("Tags: " + " · ".join(f"`{x}`" for x in _as_list(row.get("tags"))[:14]))
                match = row.get("match") or {}
                with st.expander("Verification details"):
                    st.json({
                        "algorithm": match.get("algorithm"),
                        "parts": match.get("parts"),
                        "verification": match.get("verification"),
                        "meaningful_summary": ms,
                    })


def imgs_training_beta_page() -> None:
    hero("IMGS Training BETA", "The full local trainer: auto tags, multi-design preview behavior, fixed selector crop reader, weak tag cleanup, custom tags, and JSON corrections.")
    st.warning(IMGS_TRAINING_WARNING)
    animated_stepper("Training loop", ["Upload", "Auto guess", "Correct", "Save", "Resync"], active=0)

    uploaded = st.file_uploader("Upload image for IMGS training", type=SUPPORTED_IMAGE_TYPES, key="imgs_beta_upload")
    if uploaded:
        img = _image_from_upload(uploaded)
        c_img, c_guess = st.columns([0.85, 1.15])
        with c_img:
            st.image(img, caption=uploaded.name, use_container_width=True)
        with c_guess:
            with animated_loader("IMGS Beta is reading the full image…", "Checking multi-design preview, neck curve, work type, borders, motifs, and stitched reference areas"):
                analysis = _run_full_analysis(img, uploaded.name)
            st.session_state["imgs_beta_analysis"] = analysis
            st.session_state["imgs_beta_image"] = img
            st.session_state["imgs_beta_name"] = uploaded.name
            _show_prediction_card(analysis)
            _show_identification_breakdown(analysis)

        pred = analysis.get("prediction") or {}
        thinker = analysis.get("turbothinker") or {}
        image_mode = pred.get("image_mode") or thinker.get("image_mode") or "single_design"
        tags = _as_list(pred.get("tags"))
        if image_mode == "multi_design_preview" and (not tags or tags[0] != "multi_design_preview"):
            st.warning("Teacher rule: multi-design preview should keep `multi_design_preview` as first tag. Save a correction to lock it.")

        st.markdown("### Correct the answer")
        default_label = str(pred.get("predicted_type") or "unknown_review")
        if default_label not in IMGS_LABELS:
            default_label = "unknown_review"
        c1, c2, c3 = st.columns(3)
        final_label = c1.selectbox("Correct primary label", IMGS_LABELS, index=IMGS_LABELS.index(default_label), key="imgs_beta_final")
        auto_remove = c2.checkbox("Auto-remove weak leftover tags", value=True, key="imgs_beta_weak")
        min_score = c3.slider("Weak tag cutoff", 0.05, 0.75, 0.24, 0.01, key="imgs_beta_cutoff")
        c4, c5 = st.columns([1.1, 1.0])
        with c4:
            known_tags = sorted(set([str(x) for x in IMGS_LABELS] + ["normal_work", "u_shaped_neck", "drop_neck", "rangoli_work", "kurta", "full_hand", "cut_work", "net_work", "back_drop", "flower_border", "peacock", "pot_neck", "boat_neck"]))
            selected_tags = st.multiselect("Anne/style category tags", known_tags, default=[])
            manual_tags_raw = st.text_input("Manual custom tags", placeholder="u_shaped_neck, cut_work, full_hand")
        with c5:
            notes = st.text_area("Teacher reason", placeholder="Example: U-shaped neck + irregular inside border means cut work", height=110)
        if st.button("Save IMGS training correction", type="primary"):
            sample_id, sample_path = save_uploaded_training_image(APP_ROOT, img, uploaded.name)
            manual_tags = selected_tags + [x.strip() for x in manual_tags_raw.split(",") if x.strip()]
            with animated_loader("Saving teacher correction…", "Writing local JSON and keeping manually added tags"):
                saved = record_training_correction(
                    APP_ROOT,
                    sample_id=sample_id,
                    source_name=uploaded.name,
                    analysis=analysis,
                    final_label=final_label,
                    notes=notes,
                    sample_image_path=str(sample_path),
                    manual_tags=manual_tags,
                    auto_remove_low_tags=auto_remove,
                    tag_min_score=float(min_score),
                )
            st.success(f"Saved correction: {saved.get('final_label')} · {saved.get('sample_id')}")

        st.markdown("### Fixed-size selector / crop reader")
        st.caption("Move the box by coordinates. The engine analyzes only that area for flower, border, butti, net work, cut work, neck curve, heavy outline, hand/full hand, or back neck hints.")
        w, h = img.size
        size_cols = st.columns(6)
        box_w = size_cols[0].number_input("box width", min_value=20, max_value=w, value=min(360, w), step=10, key="sel_bw")
        box_h = size_cols[1].number_input("box height", min_value=20, max_value=h, value=min(260, h), step=10, key="sel_bh")
        x0 = size_cols[2].number_input("x", min_value=0, max_value=max(0, w - int(box_w)), value=0, step=10, key="sel_x")
        y0 = size_cols[3].number_input("y", min_value=0, max_value=max(0, h - int(box_h)), value=0, step=10, key="sel_y")
        save_area_label = size_cols[4].text_input("area label", placeholder="border / flower", key="sel_label")
        do_area = size_cols[5].button("Read crop")
        box = (int(x0), int(y0), min(w, int(x0 + box_w)), min(h, int(y0 + box_h)))
        if do_area:
            with animated_loader("Reading selected crop…", "Detecting local stitches and area features", small=True):
                result = analyze_selector_area(img, source_name=f"{uploaded.name}::selector", box=box)
            st.image(img.crop(box), caption=f"Selected crop {box}", use_container_width=True)
            st.write("Tags: " + " · ".join(f"`{x}`" for x in _as_list(result.get("selector_tags"))))
            for r in _as_list(result.get("selector_reasons")):
                st.write("• " + str(r))
            st.session_state["imgs_beta_selector"] = result
        if st.button("Save selector area training"):
            result = st.session_state.get("imgs_beta_selector")
            if not result:
                st.warning("Read a crop first.")
            else:
                if save_area_label:
                    result = dict(result)
                    result["teacher_area_label"] = save_area_label
                parent_id = _sample_id_for_image(img, uploaded.name)
                saved = record_selector_area_training(APP_ROOT, parent_id, uploaded.name, result)
                st.success(f"Saved selector area training: {saved.get('area_id')}")

    st.divider()
    st.markdown("### Training ZIP + resync")
    zip_file = st.file_uploader("Optional ZIP to build training bank", type=["zip"], key="imgs_beta_zip")
    z1, z2, z3 = st.columns(3)
    zlimit = z1.number_input("ZIP image limit", min_value=1, max_value=100000, value=500, step=100, key="imgs_beta_zlimit")
    crops = z2.slider("Crops/image", 1, 12, 6, key="imgs_beta_crops")
    tag_min = z3.slider("Auto tag cutoff", 0.05, 0.75, 0.24, 0.01, key="imgs_beta_tagmin")
    if zip_file and st.button("Build IMGS training bank from ZIP", type="primary"):
        payload = zip_file.getvalue()
        if build_seed_training_corpus_from_zip_bytes is not None:
            with animated_loader("Building full-image training bank…", "Full-image rows keep multi_design_preview first when detected"):
                seed = build_seed_training_corpus_from_zip_bytes(APP_ROOT, payload, corpus_name=zip_file.name, limit=int(zlimit), tag_min_score=float(tag_min))
            st.success(f"Seed rows: {seed.get('summary', {}).get('images_indexed', 0):,}")
        if build_ultrabrain_region_corpus_from_zip_bytes is not None:
            with animated_loader("Building selector crop training bank…", "Region rows for neck curves, sleeves, buttas, borders, and work style"):
                regions = build_ultrabrain_region_corpus_from_zip_bytes(APP_ROOT, payload, corpus_name=f"{zip_file.name}_regions", limit=int(zlimit), crops_per_image=int(crops), tag_min_score=float(tag_min))
            st.success(f"Region rows: {regions.get('summary', {}).get('region_rows_indexed', 0):,}")
    if st.button("Resync training cache now"):
        with animated_loader("Resyncing local cache…", "Refreshing type-folder and fast-search manifests"):
            idx = _load_search_index()
            status = sync_library_cache(APP_ROOT, _as_list(idx.get("items"))) if sync_library_cache is not None else {"ok": False, "error": "sync engine unavailable"}
        st.json(status)

    with st.expander("Local data viewer"):
        s = load_all_summaries()
        st.json({"summaries": s, "search_index": {"path": _short_path(_search_index_path()), "items": len(_load_search_index().get("items", []))}})


def library_cache_page() -> None:
    hero("Library Cache", "View and resync the local type index, fast search manifest, fingerprints, and imported design JSON.")
    index = _load_search_index()
    items = _as_list(index.get("items"))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Index records", f"{len(items):,}")
    c2.metric("Design JSON", f"{len(list(_design_json_dir().glob('*.json'))):,}")
    c3.metric("Library folder", "found" if _library_dir().exists() else "missing")
    c4.metric("Cache updated", index.get("updated_at", "never"))

    st.markdown("### Cache actions")
    a1, a2, a3 = st.columns(3)
    if a1.button("Resync cache/type folders", type="primary"):
        with animated_loader("Resyncing cache…", "Building type-folder manifest and fast search manifest"):
            status = sync_library_cache(APP_ROOT, items) if sync_library_cache is not None else {"ok": False, "error": "sync engine unavailable"}
        st.json(status)
    if a2.button("Rebuild fingerprints for missing records"):
        changed = 0
        with animated_loader("Rebuilding missing fingerprints…", "Reading local image files only where fingerprint is missing"):
            for item in items:
                if item.get("fingerprint"):
                    continue
                path = Path(str(item.get("image_path") or ""))
                if path.exists() and create_fingerprint_from_path is not None:
                    try:
                        item["fingerprint"] = create_fingerprint_from_path(path)
                        changed += 1
                    except Exception:
                        pass
            index["items"] = items
            _write_search_index(index)
        st.success(f"Rebuilt {changed:,} fingerprints.")
    if a3.button("Clear empty/missing image records"):
        kept = [x for x in items if Path(str(x.get("image_path") or "")).exists()]
        index["items"] = kept
        _write_search_index(index)
        st.success(f"Removed {len(items)-len(kept):,} missing records.")

    st.markdown("### Type groups")
    groups: Dict[str, int] = {}
    for item in items:
        for key in ("primary_label", "work_type", "neck_type"):
            val = str(item.get(key) or "unknown")
            groups[val] = groups.get(val, 0) + 1
    st.dataframe([{"group": k, "count": v} for k, v in sorted(groups.items(), key=lambda kv: kv[1], reverse=True)], use_container_width=True, hide_index=True)

    with st.expander("Index records preview"):
        st.dataframe([{
            "design": x.get("design_no"), "label": x.get("primary_label"), "work": x.get("work_type"),
            "neck": x.get("neck_type"), "tags": ", ".join(_as_list(x.get("tags"))[:8]), "path": x.get("relative_path") or x.get("image_path")
        } for x in items[:300]], use_container_width=True, hide_index=True)
    with st.expander("Raw import log"):
        st.json(_json_read(_import_log_path(), {"imports": []}))

def teach_train_page() -> None:
    hero("Teach / Train", "Build visual seed data from ZIPs and retrain the local brain. Corrections are stronger than auto guesses.")
    st.warning("For GitHub, do not commit raw ZIPs. Train locally, keep only under-25MB brain parts in the repo.")

    st.markdown("### 1) Build visual training rows from ZIP")
    zip_file = st.file_uploader("Upload image ZIP for local training", type=["zip"])
    c1, c2, c3 = st.columns(3)
    limit = c1.number_input("Image limit", min_value=1, max_value=100000, value=500, step=100)
    crops_per_image = c2.slider("Region crops per image", 1, 12, 8)
    tag_min = c3.slider("Weak tag cutoff", 0.05, 0.75, 0.24, 0.01)

    if zip_file and st.button("Build seed + region training bank", type="primary"):
        if build_seed_training_corpus_from_zip_bytes is None:
            st.error("Seed-bank builder is unavailable.")
        else:
            payload = zip_file.getvalue()
            with animated_loader("Building full-image seed bank…", "Indexing uploaded ZIP images for local training"):
                seed = build_seed_training_corpus_from_zip_bytes(APP_ROOT, payload, corpus_name=zip_file.name, limit=int(limit), tag_min_score=float(tag_min))
            st.success(f"Seed bank indexed {seed.get('summary', {}).get('images_indexed', 0):,} images")
            if build_ultrabrain_region_corpus_from_zip_bytes is not None:
                with animated_loader("Building crop/region training bank…", "Creating selector-style crops for sleeves, borders, neck curves, buttas, and motifs"):
                    regions = build_ultrabrain_region_corpus_from_zip_bytes(APP_ROOT, payload, corpus_name=f"{zip_file.name}_regions", limit=int(limit), crops_per_image=int(crops_per_image), tag_min_score=float(tag_min))
                st.success(f"Region bank indexed {regions.get('summary', {}).get('region_rows_indexed', 0):,} crop rows")

    st.markdown("### 2) Train local brain weights")
    c1, c2, c3 = st.columns(3)
    train_student = c1.checkbox("Train v4.9 Student", value=True)
    train_ultra = c2.checkbox("Train v5.0 UltraBrain", value=True)
    train_super = c3.checkbox("Train v5.3 SuperBrain", value=True)
    if st.button("Train / refresh selected models", type="primary"):
        if train_student and train_turbothinker_student_model is not None:
            with animated_loader("Training Student weights…", "Refreshing corrected label weights"):
                report = train_turbothinker_student_model(APP_ROOT)
            st.success(f"Student trained: {report.get('training_rows', report.get('rows', 'done'))}")
        if train_ultra and train_turbothinker_ultrabrain_model is not None:
            with animated_loader("Training UltraBrain…", "Learning region and feature memory"):
                report = train_turbothinker_ultrabrain_model(APP_ROOT)
            st.success(f"UltraBrain trained: {report.get('training_rows', report.get('rows', 'done'))}")
        if train_super and train_turbothinker_superbrain_model is not None:
            with animated_loader("Training SuperBrain 24MB brain-part model…", "Writing GitHub-safe brain parts under 25 MB"):
                report = train_turbothinker_superbrain_model(APP_ROOT)
            st.success(f"SuperBrain trained: {report.get('training_rows', report.get('raw_training_rows', 'done'))}")
            st.info("Run Brain Parts page check before pushing to GitHub.")

    st.markdown("### 3) Local teacher corrections")
    corrections = load_corrections(APP_ROOT) if load_corrections is not None else {"samples": []}
    rows = _as_list(corrections.get("samples"))
    st.metric("Saved corrections", len(rows))
    if rows:
        compact = [{
            "sample_id": r.get("sample_id"),
            "final_label": r.get("final_label"),
            "predicted_type": r.get("predicted_type"),
            "tags": ", ".join(_as_list(r.get("tags"))[:8]),
            "created_at": r.get("created_at"),
        } for r in rows[-100:]]
        st.dataframe(compact, use_container_width=True, hide_index=True)



def _exports_dir(name: str) -> Path:
    path = APP_ROOT / "exports" / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def _download_file_button(path: Path, label: str, mime: str = "application/octet-stream") -> None:
    p = Path(path)
    if p.exists():
        st.download_button(label, data=p.read_bytes(), file_name=p.name, mime=mime)


def dst_to_png_converter_page() -> None:
    hero("DST to PNG Converter", "The main legacy converter is back: DST/PES/JEF/etc. to PNG/JPG/WEBP using local TurboEmb, optional C++ renderer, 4K output, and loading animations.")
    st.caption(str(DST_CONVERTER_VERSION))
    status = cpp_status() if cpp_status is not None else {"available": False, "message": "C++ status unavailable"}
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("C++ Turbo", "ready" if status.get("available") else "fallback")
    c2.metric("Renderer", status.get("message", "unknown")[:36])
    c3.metric("Max output", "4K")
    c4.metric("Mode", "local only")

    animated_stepper("Converter pipeline", ["Upload", "Read stitches", "C++/Python render", "Save PNG", "Preview/download"], active=0)
    mode = st.radio("Converter source", ["Single / multiple files", "ZIP batch"], horizontal=True)
    c1, c2, c3 = st.columns(3)
    output_format = c1.selectbox("Output format", ["PNG", "WEBP", "JPG"], index=0)
    size_label = c2.selectbox("Render size", ["1024", "2048", "3000", "4096"], index=1)
    prefer_cpp = c3.checkbox("Use C++ Turbo when available", value=True)
    size = int(size_label)
    out_dir = _exports_dir("converter")
    emb_types = sorted([x.lstrip(".") for x in SUPPORTED_EMB_EXTENSIONS])

    if convert_uploaded_bytes is None:
        st.error("Converter module is unavailable. Check dst_converter.py.")
        return

    if mode == "Single / multiple files":
        files = st.file_uploader("Upload embroidery design files", type=emb_types, accept_multiple_files=True, key="dst_converter_files")
        if files and st.button("Convert to image", type="primary"):
            results = []
            errors = []
            progress = st.progress(0, text="Starting converter…")
            with animated_loader("Converting embroidery files…", "Reading stitch data, rendering with TurboEmb/C++, and saving preview images"):
                for i, f in enumerate(files, start=1):
                    try:
                        progress.progress(int((i - 1) / max(1, len(files)) * 100), text=f"Converting {f.name}")
                        meta = convert_uploaded_bytes(f.getvalue(), f.name, out_dir, size=size, output_format=output_format, prefer_cpp=prefer_cpp)
                        results.append(meta)
                    except Exception as exc:
                        errors.append({"file": f.name, "error": str(exc)[:240]})
                progress.progress(100, text="Conversion complete")
            st.success(f"Converted {len(results)} file(s).")
            if errors:
                st.warning(f"{len(errors)} file(s) could not convert.")
                st.dataframe(errors, use_container_width=True, hide_index=True)
            if results:
                rows = []
                for meta in results:
                    rows.append({
                        "file": meta.get("input_name"),
                        "engine": meta.get("engine"),
                        "stitches": meta.get("stitches"),
                        "colors": meta.get("estimated_thread_colors"),
                        "size": meta.get("output_size"),
                        "output": Path(str(meta.get("output_path"))).name,
                    })
                st.dataframe(rows, use_container_width=True, hide_index=True)
                for meta in results[:12]:
                    out = Path(str(meta.get("output_path") or ""))
                    with st.container(border=True):
                        cc1, cc2 = st.columns([0.45, 1.0])
                        with cc1:
                            if out.exists():
                                st.image(str(out), use_container_width=True)
                        with cc2:
                            st.markdown(f"#### {meta.get('input_name')}")
                            st.caption(f"{meta.get('engine')} · {meta.get('stitches')} stitches · {meta.get('estimated_thread_colors')} colors")
                            st.json({k: meta.get(k) for k in ["bounds", "density_score", "reader", "converter_version"]})
                            mime = "image/png" if out.suffix.lower() == ".png" else "image/jpeg" if out.suffix.lower() in {".jpg", ".jpeg"} else "image/webp"
                            _download_file_button(out, "Download converted image", mime)
                if len(results) > 1:
                    zip_path = out_dir / f"converted_images_{int(time.time())}.zip"
                    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                        for meta in results:
                            for key in ("output_path", "metadata_path"):
                                p = Path(str(meta.get(key) or ""))
                                if p.exists():
                                    zf.write(p, arcname=p.name)
                    _download_file_button(zip_path, "Download all converted outputs as ZIP", "application/zip")
    else:
        zip_file = st.file_uploader("Upload ZIP of DST/PES/JEF/etc.", type=["zip"], key="dst_converter_zip")
        limit = st.number_input("Batch limit", min_value=1, max_value=100000, value=500, step=100)
        if zip_file and st.button("Batch convert ZIP", type="primary"):
            if convert_zip_bytes is None:
                st.error("ZIP converter is unavailable.")
            else:
                with animated_loader("Batch converting ZIP…", "Extracting embroidery files and rendering previews"):
                    result = convert_zip_bytes(zip_file.getvalue(), zip_file.name, out_dir, size=size, output_format=output_format, limit=int(limit), prefer_cpp=prefer_cpp)
                st.success(f"Converted {result.get('count', 0)} embroidery files.")
                if result.get("errors"):
                    with st.expander("Conversion errors"):
                        st.dataframe(result["errors"], use_container_width=True, hide_index=True)
                bundle = Path(str(result.get("bundle_path") or ""))
                _download_file_button(bundle, "Download converted ZIP", "application/zip")
                if result.get("converted"):
                    st.dataframe([{ "file": x.get("input_name"), "stitches": x.get("stitches"), "engine": x.get("engine"), "output": Path(str(x.get("output_path"))).name } for x in result["converted"][:200]], use_container_width=True, hide_index=True)


def design_reader_4k_page() -> None:
    hero("4K Design Reader", "Render stitch files up to 4K, read stitch counts/density/colors, then send the rendered design into TurboThinker for visual classification.")
    st.caption(str(DST_CONVERTER_VERSION))
    status = cpp_status() if cpp_status is not None else {"available": False, "message": "C++ status unavailable"}
    st.info(f"C++ Turbo status: {status.get('message')}")
    kind = st.radio("Read from", ["Embroidery file", "Image file"], horizontal=True)
    c1, c2 = st.columns(2)
    render_size = int(c1.selectbox("Reader render size", ["1024", "2048", "4096"], index=1))
    use_cpp = c2.checkbox("Use C++ render engine", value=True)

    if kind == "Embroidery file":
        emb_types = sorted([x.lstrip(".") for x in SUPPORTED_EMB_EXTENSIONS])
        f = st.file_uploader("Upload DST/PES/JEF/etc. to read", type=emb_types, key="reader_emb")
        if not f:
            st.caption("Upload a DST to see stitch stats, 4K preview, and TurboThinker visual tags.")
            return
        out_dir = _exports_dir("reader")
        with animated_loader("Reading stitch file…", "Parsing commands, rendering 4K preview, calculating density, and classifying visual design"):
            meta = convert_uploaded_bytes(f.getvalue(), f.name, out_dir, size=render_size, output_format="PNG", prefer_cpp=use_cpp)
        out = Path(str(meta.get("output_path") or ""))
        c_img, c_stats = st.columns([0.55, 1.0])
        with c_img:
            if out.exists():
                st.image(str(out), caption=out.name, use_container_width=True)
                _download_file_button(out, "Download rendered PNG", "image/png")
        with c_stats:
            st.markdown("### Stitch reader result")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Stitches", f"{int(meta.get('stitches') or 0):,}")
            m2.metric("Colors", meta.get("estimated_thread_colors", 0))
            m3.metric("Density", meta.get("density_score", 0))
            m4.metric("Engine", str(meta.get("engine", "reader"))[:18])
            st.json({k: meta.get(k) for k in ["bounds", "reader", "palette_preview", "estimated_length_units", "max_jump_units"]})
        if out.exists():
            with Image.open(out) as rendered:
                analysis_img = rendered.convert("RGB")
            with animated_loader("TurboThinker reading rendered design…", "Detecting work type, neck style, motifs, and training tags", small=True):
                analysis = _run_full_analysis(analysis_img, out.name)
            _show_prediction_card(analysis)
            _show_identification_breakdown(analysis)
    else:
        f = st.file_uploader("Upload image for 4K visual read", type=SUPPORTED_IMAGE_TYPES, key="reader_img")
        if not f:
            return
        img = _image_from_upload(f)
        c1, c2 = st.columns([0.5, 1.0])
        with c1:
            st.image(img, caption=f.name, use_container_width=True)
        with c2:
            with animated_loader("TurboThinker reading image…", "Detecting design class and features", small=True):
                analysis = _run_full_analysis(img, f.name)
            _show_prediction_card(analysis)
            _show_identification_breakdown(analysis)


def maximum_library_manager_page() -> None:
    hero("Maximum Library Manager", "Manage the full local library: filter, preview, relabel, dedupe, remove missing records, export, backup, and resync.")
    st.caption(str(LIBRARY_MANAGER_VERSION))
    if lm_load_index is None:
        st.error("Library Manager module is unavailable.")
        return
    with animated_loader("Loading maximum library manager…", "Reading search index, design JSON, cache groups, missing files, and duplicates", small=True):
        index = lm_load_index(APP_ROOT)
        items = _as_list(index.get("items"))
        summary = lm_library_summary(APP_ROOT) if lm_library_summary is not None else {"total": len(items)}
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Library records", f"{int(summary.get('total') or 0):,}")
    c2.metric("Missing files", f"{int(summary.get('missing_files') or 0):,}")
    c3.metric("Duplicate sets", f"{int(summary.get('duplicate_sets') or 0):,}")
    c4.metric("Updated", str(summary.get("updated_at") or "never")[:22])

    st.markdown("### Filters")
    c1, c2, c3, c4, c5 = st.columns(5)
    query = c1.text_input("Search", placeholder="HB2479 cut work u neck")
    work = c2.selectbox("Work", lm_list_options(items, "work_type") if lm_list_options else ["any"])
    neck = c3.selectbox("Neck", lm_list_options(items, "neck_type") if lm_list_options else ["any"])
    dress = c4.selectbox("Dress", lm_list_options(items, "dress_type") if lm_list_options else ["any"])
    source = c5.selectbox("Source", lm_list_options(items, "source") if lm_list_options else ["any"])
    c6, c7 = st.columns([0.35, 0.65])
    missing_only = c6.checkbox("Missing only", value=False)
    limit = c7.slider("Rows to show", 25, 1000, 200, 25)

    visible = lm_filter_items(items, query=query, work_type=work, neck_type=neck, dress_type=dress, source=source, missing_only=missing_only, limit=int(limit)) if lm_filter_items else items[:int(limit)]
    st.markdown(f"### Visible records ({len(visible)})")
    rows = []
    for item in visible:
        rows.append({
            "id": item.get("id"), "design": item.get("design_no"), "label": item.get("primary_label"),
            "work": item.get("work_type"), "neck": item.get("neck_type"), "dress": item.get("dress_type"),
            "tags": ", ".join(_as_list(item.get("tags"))[:8]), "exists": Path(str(item.get("image_path") or "")).exists(),
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)

    with st.expander("Preview cards"):
        for item in visible[:40]:
            with st.container(border=True):
                c_img, c_text = st.columns([0.28, 1.0])
                with c_img:
                    p = Path(str(item.get("image_path") or ""))
                    if p.exists():
                        st.image(str(p), use_container_width=True)
                    else:
                        st.caption("missing preview")
                with c_text:
                    st.markdown(f"#### {item.get('design_no')} — {item.get('primary_label')}")
                    st.caption(f"{item.get('work_type')} · {item.get('neck_type')} · {item.get('dress_type')} · {item.get('source')}")
                    st.write("Tags: " + " · ".join(f"`{x}`" for x in _as_list(item.get("tags"))[:16]))
                    st.code(str(item.get("image_path") or ""), language="text")

    st.markdown("### Bulk relabel visible/selected records")
    selection_labels = [f"{x.get('design_no') or x.get('source_name')} | {x.get('id')}" for x in visible[:500]]
    selected = st.multiselect("Select records to update", selection_labels)
    selected_ids = [x.split("|")[-1].strip() for x in selected]
    b1, b2, b3, b4 = st.columns(4)
    new_work = b1.text_input("New work type", placeholder="cut_work")
    new_neck = b2.text_input("New neck type", placeholder="u_shaped_neck")
    new_dress = b3.text_input("New dress type", placeholder="blouse")
    tags_text = b4.text_input("Add tags", placeholder="full_hand, floral")
    if st.button("Apply selected relabel", type="primary"):
        if not selected_ids:
            st.warning("Select records first.")
        elif lm_apply_bulk_labels is None:
            st.error("Bulk label helper unavailable.")
        else:
            tags = [t.strip() for t in tags_text.split(",") if t.strip()]
            result = lm_apply_bulk_labels(APP_ROOT, selected_ids, work_type=new_work.strip() or None, neck_type=new_neck.strip() or None, dress_type=new_dress.strip() or None, add_tags=tags)
            st.success(f"Updated {result.get('changed', 0)} records.")

    st.markdown("### Manager actions")
    a1, a2, a3, a4, a5 = st.columns(5)
    if a1.button("Export visible CSV"):
        out = lm_export_csv(APP_ROOT, visible, filename=f"library_visible_{int(time.time())}.csv")
        _download_file_button(out, "Download CSV", "text/csv")
    if a2.button("Export visible JSON"):
        out = lm_export_json(APP_ROOT, visible, filename=f"library_visible_{int(time.time())}.json")
        _download_file_button(out, "Download JSON", "application/json")
    if a3.button("Backup library index"):
        out = lm_backup_library(APP_ROOT, include_images=False)
        _download_file_button(out, "Download backup ZIP", "application/zip")
    if a4.button("Check duplicates"):
        result = lm_dedupe_records(APP_ROOT, dry_run=True)
        st.json(result)
    if a5.button("Remove missing records"):
        result = lm_remove_missing_records(APP_ROOT)
        st.success(f"Removed {result.get('removed', 0)} missing records.")

    with st.expander("Library group summary"):
        st.json(summary)


def google_drive_page() -> None:
    hero("Google Drive", "Google Drive page restored: connect local OAuth, download public Drive files, browse authenticated Drive folders, and import downloaded images/ZIPs into the local library.")
    st.caption(str(GOOGLE_BRIDGE_VERSION))
    if google_status is None:
        st.error("Google bridge module is unavailable.")
        return
    status = google_status(APP_ROOT)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("OAuth config", "ready" if status.get("configured") else "not set")
    c2.metric("Token", "saved" if status.get("token_saved") else "not connected")
    c3.metric("Requests", "ready" if status.get("requests_available") else "missing")
    c4.metric("Mode", "local")

    tab1, tab2, tab3 = st.tabs(["Connect", "Public Drive download", "Drive browser"])
    with tab1:
        st.markdown("### Local Google connection")
        cfg = load_google_config(APP_ROOT) if load_google_config is not None else {}
        c1, c2 = st.columns(2)
        client_id = c1.text_input("Client ID", value=str(cfg.get("client_id") or ""))
        client_secret = c2.text_input("Client Secret", value=str(cfg.get("client_secret") or ""), type="password")
        redirect_uri = st.text_input("Redirect URI", value=str(cfg.get("redirect_uri") or "http://localhost:8501"))
        scopes = st.text_area("Scopes", value=str(cfg.get("scopes") or ""), height=72)
        if st.button("Save local Google config"):
            save_google_config(APP_ROOT, {"client_id": client_id, "client_secret": client_secret, "redirect_uri": redirect_uri, "scopes": scopes})
            st.success("Saved to local_config/google_connections.json. Keep this file private.")
        if build_oauth_url is not None and client_id:
            st.markdown("#### Sign-in URL")
            st.code(build_oauth_url(APP_ROOT), language="text")
            code = st.text_input("Paste OAuth code after sign-in", type="password")
            if code and st.button("Connect Google account"):
                with animated_loader("Connecting Google account…", "Exchanging OAuth code locally and saving token outside git"):
                    result = exchange_oauth_code(APP_ROOT, code) if exchange_oauth_code is not None else {"ok": False, "error": "exchange unavailable"}
                if result.get("ok"):
                    st.success("Google account connected locally.")
                else:
                    st.error(result.get("error") or result)
        st.caption("For public Drive links you do not need OAuth. For private Drive/Gmail, add your own Google OAuth client locally.")

    with tab2:
        st.markdown("### Download public Drive file")
        link = st.text_input("Paste Drive file/folder link or file ID", placeholder="https://drive.google.com/file/d/... or id")
        out_dir = APP_ROOT / "downloads" / "gdrive"
        if link and parse_drive_id is not None:
            parsed = parse_drive_id(link)
            st.json(parsed)
            if parsed.get("id") and st.button("Download Drive file"):
                with animated_loader("Downloading from Google Drive…", "Saving into downloads/gdrive"):
                    result = drive_download_file(APP_ROOT, parsed["id"], out_dir) if drive_download_file is not None else {"ok": False, "error": "download unavailable"}
                if result.get("ok"):
                    st.success(f"Downloaded: {result.get('name')}")
                    p = Path(str(result.get("path") or ""))
                    _download_file_button(p, "Download local copy")
                    if p.suffix.lower() in IMAGE_EXTENSIONS or p.suffix.lower() == ".zip":
                        if st.button("Import downloaded file/folder into library cache"):
                            with animated_loader("Importing Drive download…", "Adding downloaded images/ZIPs to local library cache"):
                                if p.suffix.lower() == ".zip":
                                    res = import_zip_to_library(p.read_bytes(), zip_name=p.name, analyze=True, build_fingerprints=True, limit=500)
                                else:
                                    res = scan_folder_to_index(str(out_dir), analyze=True, build_fingerprints=True, limit=500)
                            st.success(f"Imported {len(res.get('items', []))} records.")
                else:
                    st.error(result.get("error") or result)

    with tab3:
        st.markdown("### Authenticated Drive browser")
        folder = st.text_input("Folder ID", placeholder="optional")
        query = st.text_input("Name contains", placeholder="HB or cut work")
        page_size = st.slider("Files to list", 10, 100, 30, 10)
        if st.button("List Drive files"):
            with animated_loader("Browsing Google Drive…", "Reading file list using your local OAuth token"):
                result = drive_list_files(APP_ROOT, folder_id=folder.strip(), query=query.strip(), page_size=int(page_size)) if drive_list_files is not None else {"ok": False, "error": "browser unavailable"}
            if result.get("ok"):
                files = result.get("files") or []
                st.dataframe(files, use_container_width=True, hide_index=True)
                st.session_state["gdrive_files"] = files
            else:
                st.error(result.get("error") or result)
        files = st.session_state.get("gdrive_files") or []
        if files:
            choices = [f"{f.get('name')} | {f.get('id')}" for f in files]
            choice = st.selectbox("Download one listed file", choices)
            if choice and st.button("Download selected Drive file"):
                file_id = choice.split("|")[-1].strip()
                filename = choice.split("|")[0].strip()
                result = drive_download_file(APP_ROOT, file_id, APP_ROOT / "downloads" / "gdrive", filename=filename) if drive_download_file is not None else {"ok": False, "error": "download unavailable"}
                if result.get("ok"):
                    st.success(f"Downloaded {result.get('name')}")
                else:
                    st.error(result.get("error") or result)


def gmail_signin_page() -> None:
    hero("Gmail Sign In", "Gmail sign page restored with local Google OAuth status, profile check, and recent-message reader for your connected account.")
    st.caption(str(GOOGLE_BRIDGE_VERSION))
    if google_status is None:
        st.error("Google bridge module is unavailable.")
        return
    status = google_status(APP_ROOT)
    c1, c2, c3 = st.columns(3)
    c1.metric("OAuth config", "ready" if status.get("configured") else "not set")
    c2.metric("Gmail token", "connected" if status.get("token_saved") else "not connected")
    c3.metric("Config path", "local_config")
    if not status.get("configured"):
        st.warning("Open Google Drive → Connect first, save your local OAuth client, then return here.")
    if st.button("Check Gmail profile", type="primary"):
        with animated_loader("Checking Gmail sign-in…", "Reading Google profile with local token", small=True):
            profile = gmail_profile(APP_ROOT) if gmail_profile is not None else {"ok": False, "error": "profile unavailable"}
        if profile.get("ok"):
            st.success(f"Signed in as {profile.get('email')}")
            st.json(profile)
        else:
            st.error(profile.get("error") or profile)
    max_results = st.slider("Recent messages to preview", 5, 30, 10, 5)
    if st.button("Read recent Gmail headers"):
        with animated_loader("Reading Gmail headers…", "Fetching recent messages without storing message bodies", small=True):
            result = gmail_recent_messages(APP_ROOT, max_results=int(max_results)) if gmail_recent_messages is not None else {"ok": False, "error": "gmail unavailable", "messages": []}
        if result.get("ok"):
            msgs = result.get("messages") or []
            if msgs:
                st.dataframe(msgs, use_container_width=True, hide_index=True)
            else:
                st.info("No recent messages returned.")
        else:
            st.error(result.get("error") or result)
    st.caption("This page keeps secrets/tokens in local_config/, which is ignored by git. Do not commit that folder.")

def brain_parts_page() -> None:
    hero("Brain Parts", "Check that every brain file is below 25 MB before GitHub upload.")
    with animated_loader("Checking brain parts…", "Verifying manifest and under-25MB files", small=True):
        status = brain_part_status()
    if status.get("ok"):
        st.success("Brain parts are OK for your under-25MB rule.")
    else:
        st.error("Brain parts need attention before GitHub upload.")
    c1, c2, c3 = st.columns(3)
    c1.metric("Parts", status.get("parts_count", 0))
    c2.metric("Total brain size", f"{status.get('total_mb', 0)} MB")
    c3.metric("Manifest", "found" if status.get("manifest_exists") else "missing")
    if status.get("parts"):
        st.dataframe(status["parts"], use_container_width=True, hide_index=True)
    st.markdown("#### GitHub-safe commands")
    st.code("""git add streamlit_app.py imgs_training.py turbothinker_*.py teacher_search_memory_v5_4.json imgs_training/models/shards/ imgs_training/models/turbothinker_superbrain_v5_3_model.json .gitignore .gitattributes README.md docs scripts\ngit commit -m \"Update clean v5.3 TurboThinker GUI and 24MB brain parts\"\ngit push""", language="bash")
    st.markdown("#### Keep these local only")
    st.code("""training ZIPs\nlibrary/\ncache/\nuploads/\nimgs_training/samples/\nimgs_training/crops/\nimgs_training/design_json/\nimgs_training/seed_training/ if it grows large""", language="text")


def settings_page() -> None:
    hero("Settings", "Clean local setup details.")
    st.markdown("### Visible UI version")
    st.write(f"`{APP_VERSION} — {APP_RELEASE}`")
    st.markdown("### Runtime paths")
    st.json({
        "app_root": str(APP_ROOT),
        "brain_manifest": brain_part_status().get("manifest_path"),
        "training_root": str(APP_ROOT / "imgs_training"),
    })
    st.markdown("### Cleaned out of the navigation")
    st.write("External API/sign-in panels and duplicate Streamlit page sidebar. Local import, local search, local training, cache/resync, selector reader, and teacher search are visible again.")
    st.markdown("### Raw engine access")
    if st.checkbox("Show full local model summaries"):
        with animated_loader("Loading full local model summaries…", "Reading all summary files", small=True):
            st.json(load_all_summaries())


# -----------------------------
# Main
# -----------------------------

def main() -> None:
    init_page()
    if ensure_training_dirs is not None:
        ensure_training_dirs(APP_ROOT)
    nav = sidebar_nav()
    if nav == "Dashboard":
        dashboard_page()
    elif nav == "DST to PNG Converter":
        dst_to_png_converter_page()
    elif nav == "4K Design Reader":
        design_reader_4k_page()
    elif nav == "Import Library":
        import_library_page()
    elif nav == "Image Searcher":
        image_searcher_page()
    elif nav == "TurboThinker GUI":
        turbothinker_gui_page()
    elif nav == "Interactive Searcher":
        interactive_searcher_page()
    elif nav == "IMGS Training BETA":
        imgs_training_beta_page()
    elif nav == "Teach / Train":
        teach_train_page()
    elif nav == "Maximum Library Manager":
        maximum_library_manager_page()
    elif nav == "Library Cache":
        library_cache_page()
    elif nav == "Google Drive":
        google_drive_page()
    elif nav == "Gmail Sign In":
        gmail_signin_page()
    elif nav == "Brain Parts":
        brain_parts_page()
    else:
        settings_page()


if __name__ == "__main__":
    main()

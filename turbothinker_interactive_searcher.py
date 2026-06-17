"""Interactive local search utilities for EMBORGANIZER v5.4.

This module is deliberately Streamlit-free so it can be tested with normal
Python and reused by the GUI.  It searches three local sources:

1. v5.4 teacher memory examples/rules.
2. User corrections saved by TurboThinker GUI.
3. Optional local image files / training index rows.

No internet, no API, and no filename-as-label training.  Filename/design number
is used only for searching and locating a file, never as a teacher label.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

SEARCHER_VERSION = "TurboThinker Interactive Searcher v5.4"
MEMORY_FILE = "teacher_search_memory_v5_4.json"

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}

WORK_TYPE_OPTIONS = [
    "any",
    "cut_work",
    "normal_work",
    "net_work",
    "rangoli_work",
    "heavy_work",
]

NECK_TYPE_OPTIONS = [
    "any",
    "u_shaped_neck",
    "drop_neck",
    "back_drop_neck",
    "pot_neck",
    "boat_neck",
    "kurta_neck",
    "front_slit_neck",
    "pointed_back_drop",
    "irregular_border",
    "designer_neck",
]

DRESS_TYPE_OPTIONS = ["any", "blouse", "kurta", "motif_panel", "unknown"]

FEATURE_OPTIONS = [
    "any",
    "full_hand",
    "back_drop",
    "floral",
    "peacock",
    "rangoli",
    "kolam",
    "diamond_motif",
    "loop_dot_border",
    "irregular_inside_border",
    "scallop_edge",
    "vertical_lines",
    "jali",
    "hanging_lines",
    "rose",
    "lotus",
    "cow_motif",
    "kurta",
]

# Common misspellings and Shiva-style naming.  These aliases are used only for
# search/facet inference; they do not overwrite teacher labels.
ALIASES: Dict[str, str] = {
    "cutwork": "cut_work",
    "cut work": "cut_work",
    "cut wirj": "cut_work",
    "cut wirh": "cut_work",
    "cut wirj ": "cut_work",
    "cutwork design": "cut_work",
    "network": "net_work",
    "net work": "net_work",
    "snet work": "net_work",
    "jali": "net_work",
    "jali work": "net_work",
    "rangoli": "rangoli_work",
    "kolam": "rangoli_work",
    "normal": "normal_work",
    "normal work": "normal_work",
    "regular work": "normal_work",
    "heavy embroidery": "heavy_work",
    "u neck": "u_shaped_neck",
    "u-neck": "u_shaped_neck",
    "u shaped": "u_shaped_neck",
    "u-shaped": "u_shaped_neck",
    "u head": "u_shaped_neck",
    "u haed": "u_shaped_neck",
    "uhead": "u_shaped_neck",
    "potneck": "pot_neck",
    "pot neck": "pot_neck",
    "boatneck": "boat_neck",
    "boat neck": "boat_neck",
    "dropneck": "drop_neck",
    "drop neck": "drop_neck",
    "back drop": "back_drop_neck",
    "backdrop": "back_drop_neck",
    "back drop neck": "back_drop_neck",
    "front slit": "front_slit_neck",
    "slit neck": "front_slit_neck",
    "kurti": "kurta",
    "kurta": "kurta",
    "full hand": "full_hand",
    "full sleeve": "full_hand",
    "hand border": "hand_border",
    "inside border": "irregular_inside_border",
    "irregular border": "irregular_border",
    "irregular inside": "irregular_inside_border",
    "scallop": "scallop_edge",
    "scalloped": "scallop_edge",
    "diamond": "diamond_motif",
    "loop dot": "loop_dot_border",
    "loop/dot": "loop_dot_border",
    "vertical line": "vertical_lines",
    "vertical lines": "vertical_lines",
    "hanging line": "hanging_lines",
    "hanging lines": "hanging_lines",
}

WORK_ALIASES = {"cut_work", "normal_work", "net_work", "rangoli_work", "heavy_work"}
NECK_ALIASES = {
    "u_shaped_neck",
    "drop_neck",
    "back_drop_neck",
    "pot_neck",
    "boat_neck",
    "front_slit_neck",
    "irregular_border",
    "designer_neck",
}

DESIGN_RE = re.compile(r"\b([A-Z]{1,3}\s*\d{2,5}[A-Z]?)\b", re.IGNORECASE)


def _read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def normalize_text(value: Any) -> str:
    text = str(value or "").lower()
    text = text.replace("_", " ").replace("-", " ").replace("/", " ")
    text = re.sub(r"[^a-z0-9\s]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_design_no(value: Any) -> str:
    raw = str(value or "").strip().upper().replace(" ", "")
    m = DESIGN_RE.search(raw)
    if m:
        return m.group(1).upper().replace(" ", "")
    return raw


def extract_design_numbers(text: str) -> List[str]:
    found: List[str] = []
    for m in DESIGN_RE.finditer(str(text or "")):
        code = normalize_design_no(m.group(1))
        if code and code not in found:
            found.append(code)
    return found


def alias_hits(query: str) -> List[str]:
    q = normalize_text(query)
    hits: List[str] = []
    for phrase, alias in ALIASES.items():
        phrase_n = normalize_text(phrase)
        if phrase_n and phrase_n in q and alias not in hits:
            hits.append(alias)
    return hits


def infer_query_facets(query: str) -> Dict[str, List[str]]:
    hits = alias_hits(query)
    work_types = [h for h in hits if h in WORK_ALIASES]
    neck_types = [h for h in hits if h in NECK_ALIASES]
    features = [h for h in hits if h not in WORK_ALIASES and h not in NECK_ALIASES]

    q = normalize_text(query)
    if "kurta" in q and "kurta" not in features:
        features.append("kurta")
    if "peacock" in q and "peacock" not in features:
        features.append("peacock")
    if "flower" in q or "floral" in q:
        if "floral" not in features:
            features.append("floral")
    if "rose" in q and "rose" not in features:
        features.append("rose")

    return {
        "design_numbers": extract_design_numbers(query),
        "work_types": work_types,
        "neck_types": neck_types,
        "features": features,
    }


def load_teacher_memory(app_root: Path) -> Dict[str, Any]:
    data = _read_json(Path(app_root) / MEMORY_FILE, {})
    if not isinstance(data, dict):
        data = {}
    data.setdefault("version", "v5.4")
    data.setdefault("rules", [])
    data.setdefault("examples", [])
    return data


def _record_search_text(row: Dict[str, Any]) -> str:
    pieces: List[str] = []
    for key in (
        "design_no",
        "student_answer",
        "neck_type",
        "work_type",
        "dress_type",
        "source",
        "notes",
        "source_name",
        "final_label",
        "predicted_type",
        "title",
    ):
        val = row.get(key)
        if val:
            pieces.append(str(val))
    for key in ("features", "tags", "manual_tags", "search_groups"):
        val = row.get(key)
        if isinstance(val, list):
            pieces.extend(str(x) for x in val)
        elif val:
            pieces.append(str(val))
    return normalize_text(" ".join(pieces))


def _finalize_record(row: Dict[str, Any], source: str) -> Dict[str, Any]:
    out = dict(row)
    out.setdefault("source", source)
    out.setdefault("design_no", normalize_design_no(out.get("design_no") or out.get("source_name") or out.get("name") or ""))
    out.setdefault("student_answer", out.get("title") or out.get("final_label") or out.get("predicted_type") or "Design record")
    out.setdefault("neck_type", "unknown")
    out.setdefault("work_type", out.get("final_label") or out.get("predicted_type") or "unknown")
    out.setdefault("dress_type", "unknown")
    out.setdefault("features", [])
    out.setdefault("teacher_confirmed", False)
    out["search_text"] = _record_search_text(out)
    return out


def teacher_memory_records(app_root: Path) -> List[Dict[str, Any]]:
    memory = load_teacher_memory(app_root)
    records = []
    for row in memory.get("examples", []) or []:
        if isinstance(row, dict):
            records.append(_finalize_record(row, "v5.4 teacher memory"))
    return records


def correction_records(app_root: Path) -> List[Dict[str, Any]]:
    data = _read_json(Path(app_root) / "imgs_training" / "corrections.json", {"samples": []})
    records: List[Dict[str, Any]] = []
    for row in data.get("samples", []) or []:
        if not isinstance(row, dict):
            continue
        tags = list(row.get("tags") or []) + list(row.get("manual_tags") or [])
        work_type = row.get("final_label") or row.get("predicted_type") or "unknown"
        rec = {
            "design_no": normalize_design_no(row.get("source_name") or row.get("sample_id") or ""),
            "student_answer": row.get("notes") or f"Teacher correction: {work_type}",
            "neck_type": ", ".join([t for t in tags if "neck" in str(t) or t in {"pot_neck", "boat_neck"}]) or "unknown",
            "work_type": work_type,
            "dress_type": "unknown",
            "features": tags,
            "tags": tags,
            "notes": row.get("notes") or "Saved teacher correction.",
            "teacher_confirmed": True,
            "image_path": row.get("sample_image_path"),
            "source_name": row.get("source_name"),
            "sample_id": row.get("sample_id"),
            "created_at": row.get("created_at"),
        }
        records.append(_finalize_record(rec, "local teacher corrections"))
    return records


def training_index_records(app_root: Path) -> List[Dict[str, Any]]:
    data = _read_json(Path(app_root) / "imgs_training" / "imgs_index.json", {"items": {}})
    items = data.get("items") or {}
    records: List[Dict[str, Any]] = []
    if isinstance(items, dict):
        iterator = items.values()
    elif isinstance(items, list):
        iterator = items
    else:
        iterator = []
    for row in iterator:
        if not isinstance(row, dict):
            continue
        tags = list(row.get("tags") or [])
        label = row.get("predicted_type") or "unknown_review"
        rec = {
            "design_no": normalize_design_no(row.get("name") or row.get("relative_path") or row.get("id") or ""),
            "student_answer": f"Indexed design: {label}",
            "neck_type": ", ".join([t for t in tags if "neck" in str(t) or t in {"pot_neck", "boat_neck"}]) or "unknown",
            "work_type": label,
            "dress_type": "unknown",
            "features": tags,
            "tags": tags,
            "notes": "Local training index row.",
            "teacher_confirmed": False,
            "image_path": row.get("preview_path") or row.get("source_path"),
            "source_name": row.get("name") or row.get("relative_path"),
            "confidence": row.get("confidence"),
        }
        records.append(_finalize_record(rec, "local training index"))
    return records


def scan_image_records(app_root: Path, extra_dirs: Optional[Iterable[str]] = None, max_files: int = 2000) -> List[Dict[str, Any]]:
    roots: List[Path] = []
    for rel in ("library", "uploads", "imgs_training/samples"):
        p = Path(app_root) / rel
        if p.exists():
            roots.append(p)
    for value in extra_dirs or []:
        try:
            p = Path(str(value)).expanduser()
            if p.exists() and p.is_dir():
                roots.append(p)
        except Exception:
            continue

    seen: set[str] = set()
    records: List[Dict[str, Any]] = []
    for root in roots:
        try:
            iterator = root.rglob("*")
        except Exception:
            continue
        for path in iterator:
            if len(records) >= max_files:
                return records
            if not path.is_file() or path.suffix.lower() not in IMAGE_EXTS:
                continue
            key = str(path.resolve())
            if key in seen:
                continue
            seen.add(key)
            design_no = normalize_design_no(path.stem)
            rec = {
                "design_no": design_no,
                "student_answer": f"Local image file: {path.name}",
                "neck_type": "unknown",
                "work_type": "unknown",
                "dress_type": "unknown",
                "features": [path.suffix.lower().lstrip("."), "local_image"],
                "notes": "Scanned local image file. Use TurboThinker GUI to analyze and save a teacher correction.",
                "teacher_confirmed": False,
                "image_path": str(path),
                "source_name": path.name,
            }
            records.append(_finalize_record(rec, "local image scan"))
    return records


def build_search_records(
    app_root: Path,
    include_teacher_memory: bool = True,
    include_corrections: bool = True,
    include_training_index: bool = True,
    include_local_images: bool = False,
    extra_dirs: Optional[Iterable[str]] = None,
) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    if include_teacher_memory:
        records.extend(teacher_memory_records(app_root))
    if include_corrections:
        records.extend(correction_records(app_root))
    if include_training_index:
        records.extend(training_index_records(app_root))
    if include_local_images:
        records.extend(scan_image_records(app_root, extra_dirs=extra_dirs))

    # De-duplicate by source + design + image path/student answer, preserving
    # teacher-confirmed records ahead of lower-confidence local rows.
    records.sort(key=lambda r: (not bool(r.get("teacher_confirmed")), str(r.get("source"))))
    deduped: List[Dict[str, Any]] = []
    seen: set[Tuple[str, str, str]] = set()
    for row in records:
        key = (
            str(row.get("design_no") or ""),
            str(row.get("source") or ""),
            str(row.get("image_path") or row.get("student_answer") or "")[:160],
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def _split_terms(query: str) -> List[str]:
    q = normalize_text(query)
    terms = [t for t in q.split() if len(t) >= 2]
    stop = {"what", "this", "that", "design", "is", "a", "the", "and", "with", "for", "me", "show", "find", "search"}
    return [t for t in terms if t not in stop]


def _contains_facet(record: Dict[str, Any], facet: str) -> bool:
    """Return True when a record positively contains a facet.

    Work and neck facets are checked against their structured fields first so
    phrases such as "not net work" in notes do not become false positives.
    """
    facet_n = normalize_text(facet)
    if facet == "any" or not facet_n:
        return True

    work_field = normalize_text(record.get("work_type") or "")
    neck_field = normalize_text(record.get("neck_type") or "")
    dress_field = normalize_text(record.get("dress_type") or "")
    feature_field = normalize_text(" ".join(str(x) for x in (record.get("features") or [])))
    tag_field = normalize_text(" ".join(str(x) for x in (record.get("tags") or [])))

    if facet in WORK_ALIASES:
        return facet_n in work_field
    if facet in NECK_ALIASES or facet in {"kurta_neck", "pointed_back_drop"}:
        return facet_n in neck_field or (facet == "kurta_neck" and "kurta" in dress_field)
    if facet in {"blouse", "kurta", "motif_panel", "unknown"}:
        return facet_n in dress_field

    positive_text = " ".join([
        normalize_text(record.get("design_no") or ""),
        normalize_text(record.get("student_answer") or ""),
        work_field, neck_field, dress_field, feature_field, tag_field,
    ])
    return facet_n in positive_text


def score_record(record: Dict[str, Any], query: str, inferred: Optional[Dict[str, List[str]]] = None) -> Tuple[float, List[str]]:
    inferred = inferred or infer_query_facets(query)
    text = str(record.get("search_text") or "")
    score = 0.0
    reasons: List[str] = []

    design_numbers = inferred.get("design_numbers") or []
    design_no = normalize_design_no(record.get("design_no") or "")
    if design_numbers:
        if design_no in design_numbers:
            score += 100.0
            reasons.append(f"design number match: {design_no}")
        else:
            # A code-specific search should strongly prefer exact matches.
            score -= 20.0

    for work in inferred.get("work_types") or []:
        if _contains_facet(record, work):
            score += 18.0
            reasons.append(f"work match: {work}")

    for neck in inferred.get("neck_types") or []:
        if _contains_facet(record, neck):
            score += 14.0
            reasons.append(f"neck match: {neck}")

    for feature in inferred.get("features") or []:
        if _contains_facet(record, feature):
            score += 9.0
            reasons.append(f"feature match: {feature}")

    terms = _split_terms(query)
    if terms:
        term_hits = 0
        for term in terms:
            if term in text:
                term_hits += 1
        if term_hits:
            score += min(24.0, term_hits * 4.0)
            reasons.append(f"keyword hits: {term_hits}")

    if bool(record.get("teacher_confirmed")):
        score += 3.0
        reasons.append("teacher-confirmed memory")

    # No query means show teacher examples first.
    if not query.strip():
        score += 1.0 if bool(record.get("teacher_confirmed")) else 0.1

    return score, reasons


def search_records(
    records: Sequence[Dict[str, Any]],
    query: str = "",
    work_type: str = "any",
    neck_type: str = "any",
    dress_type: str = "any",
    feature: str = "any",
    confirmed_only: bool = False,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    inferred = infer_query_facets(query)
    out: List[Dict[str, Any]] = []
    for record in records:
        if confirmed_only and not bool(record.get("teacher_confirmed")):
            continue
        if work_type != "any" and not _contains_facet(record, work_type):
            continue
        if neck_type != "any" and not _contains_facet(record, neck_type):
            # Convenience: searching kurta neck should match dress type kurta.
            if not (neck_type == "kurta_neck" and _contains_facet(record, "kurta")):
                continue
        if dress_type != "any" and not _contains_facet(record, dress_type):
            continue
        if feature != "any" and not _contains_facet(record, feature):
            continue
        score, reasons = score_record(record, query, inferred=inferred)
        # With filters but no query, include all matching filtered rows.
        if query.strip() and score <= 0:
            continue
        row = dict(record)
        row["search_score"] = round(score, 2)
        row["match_reasons"] = reasons[:8]
        out.append(row)
    out.sort(key=lambda r: (float(r.get("search_score") or 0), bool(r.get("teacher_confirmed"))), reverse=True)
    return out[: max(1, int(limit))]


def summarize_records(records: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    def count_key(key: str) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for row in records:
            raw = str(row.get(key) or "unknown")
            for part in [p.strip() for p in raw.split(",") if p.strip()]:
                counts[part] = counts.get(part, 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: kv[1], reverse=True))

    return {
        "records": len(records),
        "teacher_confirmed": sum(1 for r in records if r.get("teacher_confirmed")),
        "by_work_type": count_key("work_type"),
        "by_neck_type": count_key("neck_type"),
        "by_dress_type": count_key("dress_type"),
    }


def student_answer_for(record: Dict[str, Any]) -> str:
    return str(record.get("student_answer") or record.get("title") or "Design record")


def rule_cards(app_root: Path) -> List[Dict[str, str]]:
    memory = load_teacher_memory(app_root)
    rows: List[Dict[str, str]] = []
    for row in memory.get("rules", []) or []:
        if isinstance(row, dict):
            rows.append({"name": str(row.get("name") or "rule"), "rule": str(row.get("teacher_rule") or "")})
    return rows

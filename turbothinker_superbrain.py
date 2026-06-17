"""
turbothinker_superbrain.py
EMBORGANIZER v5.1 TurboThinker SuperBrain.

A larger local recognition layer above v5.0 UltraBrain. It is designed to make
training wiser, not artificially huge. It adds:
- multi-cortex visual feature expansion
- positive/negative per-label cortex weights
- per-label prototypes and variance capsules
- larger nearest-neighbor visual memory
- teacher-correction priority hooks
- uncertainty/failure diagnosis for the GUI

Still local-only. No API. Filenames are never treated as labels unless a future
GUI toggle explicitly marks folder names as teacher labels.
"""
from __future__ import annotations

import json
import math
import random
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    from turbothinker_ultrabrain import (
        PRIMARY_OUTPUT_LABELS,
        normalize_tag,
        stable_labels,
        safe_vector,
        training_rows_from_seed_bank,
        training_rows_from_corrections,
        _safe_float,  # internal but tiny/stable helper in this bundled project
        _l2,
        _cosine,
    )
except Exception:  # pragma: no cover
    PRIMARY_OUTPUT_LABELS = []

    def normalize_tag(value: Any) -> str:
        return "_".join("".join(ch.lower() if ch.isalnum() else " " for ch in str(value or "")).split())

    def stable_labels(extra_labels: Optional[Iterable[str]] = None) -> List[str]:
        labels: List[str] = []
        for x in list(extra_labels or []):
            t = normalize_tag(x)
            if t and t not in labels:
                labels.append(t)
        return labels

    def safe_vector(raw: Any, feature_count: Optional[int] = None) -> List[float]:
        out = [float(x or 0.0) for x in (raw if isinstance(raw, (list, tuple)) else [])]
        if feature_count:
            out = (out + [0.0] * feature_count)[:feature_count]
        return out

    def training_rows_from_seed_bank(seed_bank: Dict[str, Any], output_labels: List[str]) -> List[Dict[str, Any]]:
        return []

    def training_rows_from_corrections(corrections: Dict[str, Any], output_labels: List[str]) -> List[Dict[str, Any]]:
        return []

    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            f = float(value)
            return f if math.isfinite(f) else default
        except Exception:
            return default

    def _l2(a: Sequence[float], b: Sequence[float]) -> float:
        m = max(len(a), len(b), 1)
        return math.sqrt(sum(((a[i] if i < len(a) else 0.0) - (b[i] if i < len(b) else 0.0)) ** 2 for i in range(m)) / m)

    def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
        num = sum(x * y for x, y in zip(a, b))
        da = math.sqrt(max(1e-12, sum(x * x for x in a)))
        db = math.sqrt(max(1e-12, sum(y * y for y in b)))
        return max(-1.0, min(1.0, num / (da * db)))

SUPERBRAIN_VERSION = "TurboThinker SuperBrain v5.3 • 24MB brain-part cortex + teacher GUI + failure diagnosis • no API"
SUPERBRAIN_MODEL_FILENAME = "turbothinker_superbrain_v5_3_model.json"
SUPERBRAIN_REPORT_FILENAME = "last_superbrain_training_report.json"


try:
    from turbothinker_model_store import save_json_model, load_json_model, storage_summary
except Exception:  # pragma: no cover
    save_json_model = None
    load_json_model = None
    storage_summary = None

STYLE_NOISE_TAGS = {
    "imgs_engine", "turbothinker_engine", "imgs_training_engine", "imgs engine", "turbothinker engine",
    "density_low", "density_medium", "density_high", "wide_horizontal", "tall_vertical", "symmetrical",
    "multi_part_possible", "heavy_outline",
}

LABEL_GROUPS: Dict[str, List[str]] = {
    "layout": ["multi_design_preview", "all_over_design", "stitched_photo_reference"],
    "neck": ["front_neck", "back_neck", "boat_neck", "pot_neck", "v_neck_designs", "back_drop_neck"],
    "hand": ["short_hand", "full_hand", "hand_design", "sleeve_panel"],
    "work": ["heavy_work", "cut_work", "net_work", "cutwork", "net_designs", "mirror_designs", "kutch_work", "3d_emboss"],
    "motif": ["butti", "border", "flower_border", "flowers", "mango", "peacock_parrot", "lotus_roses", "rangoli_design", "saree_pallus"],
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def model_path(app_root: Path) -> Path:
    return Path(app_root) / "imgs_training" / "models" / SUPERBRAIN_MODEL_FILENAME


def report_path(app_root: Path) -> Path:
    return Path(app_root) / "imgs_training" / "models" / SUPERBRAIN_REPORT_FILENAME


def _read_json(path: Path, default: Any) -> Any:
    try:
        p = Path(path)
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def _write_json(path: Path, data: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _clip(v: float, lo: float = -8.0, hi: float = 8.0) -> float:
    return max(lo, min(hi, _safe_float(v)))


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-min(60.0, x))
        return 1.0 / (1.0 + z)
    z = math.exp(max(-60.0, x))
    return z / (1.0 + z)


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(float(x) * float(y) for x, y in zip(a, b))


def _mean_std(matrix: List[List[float]]) -> Tuple[List[float], List[float]]:
    if not matrix:
        return [], []
    m = max(len(r) for r in matrix)
    means: List[float] = []
    stds: List[float] = []
    for j in range(m):
        vals = [row[j] if j < len(row) else 0.0 for row in matrix]
        mu = sum(vals) / max(1, len(vals))
        var = sum((v - mu) ** 2 for v in vals) / max(1, len(vals))
        means.append(mu)
        stds.append(max(1e-5, math.sqrt(var)))
    return means, stds


def _standardize(vec: Sequence[float], means: Sequence[float], stds: Sequence[float]) -> List[float]:
    return [_clip(((vec[j] if j < len(vec) else 0.0) - means[j]) / (stds[j] if j < len(stds) and stds[j] else 1.0)) for j in range(len(means))]


def cortex_expand(raw_vec: Sequence[float], feature_count: int) -> List[float]:
    """Large deterministic visual expansion: the v5.1 cortex.

    For a 19-value base vector this creates 300+ values: raw features, non-linear
    transforms, pair/triple interactions, layout contrast detectors, and rough
    embroidery heuristics. This gives the local model far more shapes to learn
    without adding fake bulk or external dependencies.
    """
    x = safe_vector(raw_vec, feature_count)
    if not x:
        x = [0.0] * feature_count
    x = [_clip(v, -4.0, 4.0) for v in x]
    out: List[float] = []
    # Cortex A: direct sensory channels.
    out.extend(x)
    # Cortex B: nonlinear channels.
    out.extend([v * v for v in x])
    out.extend([v * v * v for v in x])
    out.extend([math.sqrt(abs(v)) if v >= 0 else -math.sqrt(abs(v)) for v in x])
    out.extend([math.log1p(abs(v)) if v >= 0 else -math.log1p(abs(v)) for v in x])
    out.extend([1.0 - max(0.0, min(1.0, v)) for v in x])
    # Cortex C: pair interactions. For 19 base dims this adds 171 channels.
    max_pair = min(len(x), 22)
    for i in range(max_pair):
        for j in range(i + 1, max_pair):
            out.append(x[i] * x[j])
    # Cortex D: contrast and ratios between layout zones.
    def val(i: int, d: float = 0.0) -> float:
        return x[i] if i < len(x) else d

    density = val(0)
    aspect = val(1, 1.0)
    coverage = val(2)
    net = val(3)
    scattered = val(4)
    edge = val(5)
    regions = val(6)
    complexity = val(7)
    hsym = val(8, 24)
    vsym = val(9, 24)
    comps = val(10)
    top = val(11, density)
    mid = val(12, density)
    bot = val(13, density)
    left = val(14, density)
    center = val(15, density)
    right = val(16, density)
    cx = val(17, 24)
    cy = val(18, 24)
    eps = 1e-4
    layout_features = [
        density + coverage,
        density * regions,
        coverage * regions,
        net * edge,
        scattered * comps,
        edge - density,
        coverage - density,
        abs(left - right),
        abs(top - bot),
        abs(center - ((left + right) / 2.0)),
        max(top, mid, bot),
        max(left, center, right),
        min(top, mid, bot),
        min(left, center, right),
        mid - ((top + bot) / 2.0),
        center - ((left + right) / 2.0),
        bot - top,
        right - left,
        abs(cx - 24),
        abs(cy - 24),
        (net + edge + density) / 3.0,
        (scattered + comps + coverage) / 3.0,
        (hsym + vsym) / 2.0,
        (density + edge + coverage + regions) / 4.0,
        net / (edge + eps),
        edge / (density + eps),
        coverage / (density + eps),
        scattered / (coverage + eps),
        complexity * regions,
        aspect * coverage,
        aspect * edge,
        aspect * net,
        (1.0 - min(1.0, aspect)) * density,
    ]
    out.extend(layout_features)
    # Cortex E: soft threshold detectors. They make failure reasons easier to read.
    thresholds = [0.08, 0.16, 0.24, 0.32, 0.45, 0.60, 0.75]
    for v in [density, coverage, net, scattered, edge, regions, complexity, hsym, vsym, comps, top, mid, bot, left, center, right]:
        for t in thresholds:
            out.append(_sigmoid((v - t) * 12.0))
    # Cortex F: selected triple interactions for embroidery semantics.
    triples = [
        (density, edge, coverage),
        (net, edge, coverage),
        (scattered, comps, coverage),
        (regions, complexity, coverage),
        (hsym, vsym, coverage),
        (aspect, edge, net),
        (top, mid, bot),
        (left, center, right),
    ]
    for a, b, c in triples:
        out.append(a * b * c)
        out.append((a + b + c) / 3.0)
        out.append(max(a, b, c) - min(a, b, c))
    return [_clip(v) for v in out]


def _clean_labels(labels: Iterable[Any], output_labels: List[str]) -> List[str]:
    known = set(output_labels)
    out: List[str] = []
    for value in labels:
        tag = normalize_tag(value)
        if not tag or tag in STYLE_NOISE_TAGS:
            continue
        if tag not in known and len(tag) < 3:
            continue
        if tag not in out:
            out.append(tag)
    return out


def _synth_rows(rows: List[Dict[str, Any]], output_labels: List[str], feature_count: int, target_multiplier: int = 4) -> List[Dict[str, Any]]:
    """Create local visual augment rows from feature vectors, not from filenames.

    These are low-weight rows. They help the brain learn tolerance around each
    training example and reduce brittle failures when previews vary slightly.
    """
    rng = random.Random(5101)
    augmented: List[Dict[str, Any]] = []
    for idx, row in enumerate(rows):
        base = safe_vector(row.get("feature_vector"), feature_count)
        labels = _clean_labels(row.get("labels") or [], output_labels)
        if not base or not labels:
            continue
        # Always keep original row with stronger weight.
        augmented.append({**row, "labels": labels, "feature_vector": base, "weight": float(row.get("weight") or 1.0)})
        for k in range(max(0, target_multiplier - 1)):
            vec = []
            for j, v in enumerate(base):
                # deterministic jitter, small enough to be visual tolerance rather than invented labels
                amp = 0.018 + 0.010 * ((j + k) % 3)
                nv = v + rng.uniform(-amp, amp)
                vec.append(max(0.0, min(1.0, nv)) if -0.001 <= v <= 1.001 else _clip(nv, -4, 4))
            # Make some augment rows focus on region/layout channels.
            if len(vec) >= 7 and k == 1:
                vec[6] = max(vec[6], min(1.0, vec[6] * 1.12 + 0.04))
            if len(vec) >= 6 and k == 2:
                vec[5] = max(0.0, min(1.0, vec[5] * 1.10 + 0.02))
            augmented.append({
                "sample_id": f"{row.get('sample_id') or 'row'}_super_aug_{k+1}",
                "source": "superbrain_visual_augmentation",
                "feature_vector": vec,
                "labels": labels,
                "weight": max(0.32, min(1.4, float(row.get("weight") or 1.0) * 0.46)),
                "trained_from_filename": False,
            })
    return augmented


def _label_group(label: str) -> str:
    for group, labels in LABEL_GROUPS.items():
        if label in labels:
            return group
    return "other"


def _build_label_graph(rows: List[Dict[str, Any]], output_labels: List[str]) -> Dict[str, Any]:
    counts = Counter()
    pair_counts: Dict[str, Counter] = {label: Counter() for label in output_labels}
    group_counts: Dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        labs = sorted(set(_clean_labels(row.get("labels") or [], output_labels)))
        for a in labs:
            counts[a] += 1
            group_counts[_label_group(a)][a] += 1
            for b in labs:
                if a != b:
                    pair_counts[a][b] += 1
    graph = {}
    for label in output_labels:
        denom = max(1, counts[label])
        graph[label] = {b: round(c / denom, 5) for b, c in pair_counts[label].most_common(18) if c > 0}
    return {
        "cooccurrence": graph,
        "group_counts": {g: dict(c.most_common()) for g, c in group_counts.items()},
        "label_counts": dict(counts),
    }


def _centroid(vectors: List[List[float]]) -> List[float]:
    if not vectors:
        return []
    m = len(vectors[0])
    return [sum(v[j] for v in vectors) / len(vectors) for j in range(m)]


def _build_capsules(matrix: List[List[float]], rows: List[Dict[str, Any]], output_labels: List[str]) -> Dict[str, Any]:
    capsules: Dict[str, Any] = {}
    all_centroid = _centroid(matrix)
    for label in output_labels:
        pos = [x for x, row in zip(matrix, rows) if label in set(row.get("labels") or [])]
        neg = [x for x, row in zip(matrix, rows) if label not in set(row.get("labels") or [])]
        if not pos:
            continue
        pc = _centroid(pos)
        nc = _centroid(neg) if neg else all_centroid
        distances = [_l2(x, pc) for x in pos]
        spread = max(0.16, sorted(distances)[int(0.75 * (len(distances) - 1))] if distances else 0.45)
        # Centroid-difference head: a fast trained linear direction.
        weights = []
        for j, p in enumerate(pc):
            n = nc[j] if j < len(nc) else 0.0
            weights.append(max(-3.0, min(3.0, p - n)))
        bias = -24 * _dot(weights, [(pc[j] + (nc[j] if j < len(nc) else 0.0)) for j in range(len(pc))])
        capsules[label] = {
            "label": label,
            "group": _label_group(label),
            "positive_count": len(pos),
            "negative_count": len(neg),
            "centroid": [round(v, 6) for v in pc],
            "negative_centroid": [round(v, 6) for v in nc[:len(pc)]],
            "spread": round(float(spread), 6),
            "mean_distance": round(sum(distances) / max(1, len(distances)), 6),
            "linear_weights": [round(v, 6) for v in weights],
            "linear_bias": round(float(bias), 6),
            "threshold": 0.39 if len(pos) >= 16 else 0.47,
        }
    return capsules


def _build_memory(matrix: List[List[float]], rows: List[Dict[str, Any]], output_labels: List[str], max_rows: int) -> List[Dict[str, Any]]:
    memory: List[Dict[str, Any]] = []
    # Keep higher-weight corrections first, but include broad seed rows too.
    ranked = sorted(zip(matrix, rows), key=lambda xr: float(xr[1].get("weight") or 1.0), reverse=True)
    for x, row in ranked[:max_rows]:
        labels = _clean_labels(row.get("labels") or [], output_labels)
        if not labels:
            continue
        memory.append({
            "sample_id": row.get("sample_id"),
            "source": row.get("source"),
            "labels": labels[:16],
            "vector": [round(v, 6) for v in x],
            "weight": round(float(row.get("weight") or 1.0), 3),
            "teacher_strength": round(float(row.get("weight") or 1.0), 3),
        })
    return memory


def train_superbrain_model(
    app_root: Path,
    seed_bank: Dict[str, Any],
    corrections: Optional[Dict[str, Any]] = None,
    extra_labels: Optional[Iterable[str]] = None,
    target_multiplier: int = 4,
    max_memory_rows: int = 5000,
) -> Dict[str, Any]:
    started = time.time()
    output_labels = stable_labels(list(PRIMARY_OUTPUT_LABELS or []) + list(extra_labels or []))
    raw_rows = training_rows_from_seed_bank(seed_bank or {}, output_labels)
    correction_rows = training_rows_from_corrections(corrections or {}, output_labels)
    # Corrections must be louder than pseudo seed rows.
    for r in correction_rows:
        r["weight"] = max(float(r.get("weight") or 1.0), 3.8)
        r["source"] = r.get("source") or "teacher_correction"
    raw_rows.extend(correction_rows)
    raw_rows = [r for r in raw_rows if safe_vector(r.get("feature_vector"))]
    if not raw_rows:
        raise RuntimeError("SuperBrain needs seed-bank rows or teacher corrections before training.")
    feature_count = max(len(safe_vector(r.get("feature_vector"))) for r in raw_rows)
    rows = _synth_rows(raw_rows, output_labels, feature_count, target_multiplier=max(2, int(target_multiplier)))
    cortex = [cortex_expand(r.get("feature_vector") or [], feature_count) for r in rows]
    means, stds = _mean_std(cortex)
    matrix = [_standardize(v, means, stds) for v in cortex]
    label_graph = _build_label_graph(rows, output_labels)
    capsules = _build_capsules(matrix, rows, output_labels)
    memory = _build_memory(matrix, rows, output_labels, max_rows=max_memory_rows)
    positive_counts = Counter()
    source_counts = Counter()
    for row in rows:
        source_counts[str(row.get("source") or "unknown")] += 1
        for lab in set(_clean_labels(row.get("labels") or [], output_labels)):
            positive_counts[lab] += 1
    model = {
        "version": SUPERBRAIN_VERSION,
        "model_type": "local_superbrain_multicortex_capsule_knn_teacher_priority",
        "created_at": utc_now(),
        "trained_from_filename": False,
        "source_name_used_for_label": False,
        "feature_count": int(feature_count),
        "cortex_feature_count": len(means),
        "output_labels": output_labels,
        "standardization": {"means": [round(v, 7) for v in means], "stds": [round(v, 7) for v in stds]},
        "capsules": capsules,
        "memory_rows": memory,
        "label_graph": label_graph,
        "positive_counts": dict(sorted(positive_counts.items())),
        "source_counts": dict(source_counts.most_common()),
        "teacher_policy": {
            "corrections_override_seed": True,
            "seed_rows_are_weak_when_uncorrected": True,
            "filenames_are_not_labels": True,
            "recommended_workflow": "Correct 20-50 samples per important label, then retrain SuperBrain.",
        },
        "failure_policy": {
            "low_confidence_below": 0.42,
            "conflict_gap_below": 0.08,
            "multi_preview_lock_when_regions_ge": 4,
        },
        "training_summary": {
            "raw_rows": len(raw_rows),
            "training_rows_after_visual_augmentation": len(rows),
            "correction_rows": len(correction_rows),
            "seed_rows": len(raw_rows) - len(correction_rows),
            "labels_with_capsules": len(capsules),
            "memory_rows": len(memory),
            "feature_count": int(feature_count),
            "cortex_feature_count": len(means),
            "seconds": round(time.time() - started, 3),
        },
    }
    if save_json_model is not None:
        save_json_model(model_path(app_root), model, shard_size=24_000_000, force_shards=True)
    else:
        _write_json(model_path(app_root), model)
    report = superbrain_report(model, model_path(app_root))
    _write_json(report_path(app_root), report)
    return report


def load_superbrain_model(app_root: Path) -> Dict[str, Any]:
    path = model_path(app_root)
    if load_json_model is not None:
        loaded = load_json_model(path, {})
        if loaded:
            return loaded
    # Backward compatibility: v5.1 monolithic model name.
    old_path = Path(app_root) / "imgs_training" / "models" / "turbothinker_superbrain_v5_1_model.json"
    if load_json_model is not None:
        loaded_old = load_json_model(old_path, {})
        if loaded_old:
            return loaded_old
    return _read_json(path, {})


def superbrain_report(model: Dict[str, Any], path: Optional[Path] = None) -> Dict[str, Any]:
    return {
        "exists": bool(model),
        "status": "trained" if model else "missing",
        "version": model.get("version") or SUPERBRAIN_VERSION,
        "model_type": model.get("model_type"),
        "model_path": str(path or ""),
        "training_summary": model.get("training_summary") or {},
        "feature_count": model.get("feature_count"),
        "cortex_feature_count": model.get("cortex_feature_count"),
        "output_labels": len(model.get("output_labels") or []),
        "labels_with_capsules": len(model.get("capsules") or {}),
        "memory_rows": len(model.get("memory_rows") or []),
        "trained_from_filename": False,
        "source_name_used_for_label": False,
        "top_positive_counts": dict(Counter(model.get("positive_counts") or {}).most_common(20)),
        "source_counts": model.get("source_counts") or {},
        "teacher_policy": model.get("teacher_policy") or {},
        "created_at": model.get("created_at"),
        "storage": storage_summary(path) if (path is not None and storage_summary is not None) else {},
    }


def superbrain_summary(app_root: Path) -> Dict[str, Any]:
    model = load_superbrain_model(app_root)
    if not model:
        return {"exists": False, "version": SUPERBRAIN_VERSION}
    return superbrain_report(model, model_path(app_root))


def _model_vector(model: Dict[str, Any], raw_vec: Sequence[float]) -> List[float]:
    feature_count = int(model.get("feature_count") or len(raw_vec) or 1)
    cortex = cortex_expand(raw_vec, feature_count)
    std = model.get("standardization") or {}
    return _standardize(cortex, std.get("means") or [], std.get("stds") or [])


def _memory_scores(model: Dict[str, Any], qx: Sequence[float], k: int = 36) -> Tuple[Dict[str, float], List[Dict[str, Any]]]:
    rows = model.get("memory_rows") or []
    scored: List[Tuple[float, Dict[str, Any]]] = []
    for row in rows:
        vec = row.get("vector") or []
        dist = _l2(qx, vec)
        cos = _cosine(qx, vec)
        sim = max(0.0, 0.62 * (1.0 - min(1.0, dist / 3.5)) + 0.38 * ((cos + 1.0) / 2.0))
        if sim > 0:
            scored.append((sim * max(0.2, min(5.0, float(row.get("weight") or 1.0))), row))
    scored.sort(key=lambda item: item[0], reverse=True)
    top = scored[:k]
    totals: Dict[str, float] = defaultdict(float)
    denom = 1e-8
    neighbors: List[Dict[str, Any]] = []
    for weighted_score, row in top:
        denom += weighted_score
        for label in row.get("labels") or []:
            totals[label] += weighted_score
        neighbors.append({
            "sample_id": row.get("sample_id"),
            "source": row.get("source"),
            "similarity": round(min(0.999, weighted_score / max(0.2, float(row.get("weight") or 1.0))), 4),
            "labels": list(row.get("labels") or [])[:10],
            "teacher_strength": row.get("teacher_strength"),
        })
    return {label: min(0.995, value / denom) for label, value in totals.items()}, neighbors


def diagnose_failure(scores: Dict[str, float], neighbors: List[Dict[str, Any]], base_scores: Optional[Dict[str, float]] = None) -> List[str]:
    ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    notes: List[str] = []
    if not ordered:
        return ["No SuperBrain scores were produced; train the model or add teacher corrections."]
    top_label, top_score = ordered[0]
    second_score = ordered[1][1] if len(ordered) > 1 else 0.0
    if top_score < 0.42:
        notes.append(f"Low-confidence warning: top label `{top_label}` is only {top_score:.2f}. Add/correct more samples for this type.")
    if top_score - second_score < 0.08 and len(ordered) > 1:
        notes.append(f"Conflict warning: `{top_label}` is close to `{ordered[1][0]}`. Save a correction to teach the difference.")
    teacher_hits = [n for n in neighbors if str(n.get("source", "")).startswith("teacher") or "correction" in str(n.get("source", ""))]
    if not teacher_hits:
        notes.append("Teacher-memory warning: nearest matches are mostly auto seed rows, not your manual corrections yet.")
    if base_scores:
        base_top = max(base_scores.items(), key=lambda kv: kv[1])[0] if base_scores else ""
        if base_top and base_top != top_label:
            notes.append(f"Model disagreement: earlier reader preferred `{base_top}`, SuperBrain prefers `{top_label}`. Review before trusting.")
    if not notes:
        notes.append("SuperBrain confidence looks usable, but review is still recommended before sorting many files.")
    return notes[:5]


def predict_superbrain_vector(
    model: Dict[str, Any],
    feature_vector: Sequence[float],
    base_scores: Optional[Dict[str, float]] = None,
    k: int = 36,
) -> Dict[str, Any]:
    if not model:
        return {"scores": {}, "neighbors": [], "reason": ["SuperBrain model is not trained yet."]}
    qx = _model_vector(model, feature_vector)
    capsules = model.get("capsules") or {}
    output_labels = list(model.get("output_labels") or capsules.keys())
    base_scores = {normalize_tag(k): _safe_float(v) for k, v in (base_scores or {}).items()}
    capsule_scores: Dict[str, float] = {}
    prototype_scores: Dict[str, float] = {}
    linear_scores: Dict[str, float] = {}
    for label in output_labels:
        cap = capsules.get(label) or {}
        if not cap:
            continue
        centroid = cap.get("centroid") or []
        spread = max(0.16, _safe_float(cap.get("spread"), 0.45))
        if centroid:
            dist = _l2(qx, centroid)
            proto = math.exp(-24 * (dist / spread) ** 2)
            prototype_scores[label] = proto
        weights = cap.get("linear_weights") or []
        if weights:
            lin = _sigmoid((_dot(qx, weights) + _safe_float(cap.get("linear_bias"))) / max(1.0, math.sqrt(len(weights)) / 7.0))
            linear_scores[label] = lin
        capsule_scores[label] = max(prototype_scores.get(label, 0.0), 0.62 * linear_scores.get(label, 0.0) + 0.38 * prototype_scores.get(label, 0.0))
    memory, neighbors = _memory_scores(model, qx, k=k)
    merged: Dict[str, float] = {}
    for label in output_labels:
        cap = capsule_scores.get(label, 0.0)
        near = memory.get(label, 0.0)
        base = base_scores.get(label, 0.0)
        # v5.1: memory/capsules dominate because they are trained rows; base still helps when model is unsure.
        score = 0.46 * cap + 0.38 * near + 0.16 * base
        merged[label] = max(0.0, min(0.995, score))
    # Tag graph expansion.
    graph = (model.get("label_graph") or {}).get("cooccurrence") or {}
    top_parents = [label for label, score in sorted(merged.items(), key=lambda kv: kv[1], reverse=True)[:8] if score >= 0.36]
    for parent in top_parents:
        parent_score = merged.get(parent, 0.0)
        for child, assoc in (graph.get(parent) or {}).items():
            assoc_f = _safe_float(assoc)
            if assoc_f >= 0.10:
                merged[child] = min(0.995, max(merged.get(child, 0.0), merged.get(child, 0.0) + parent_score * assoc_f * 0.13))
    sorted_scores = sorted(merged.items(), key=lambda kv: kv[1], reverse=True)
    reasons: List[str] = []
    if sorted_scores:
        reasons.append(f"SuperBrain top label `{sorted_scores[0][0]}` scored {sorted_scores[0][1]:.2f} using multi-cortex capsules and nearest visual memory.")
    reasons.append(f"SuperBrain used {len(model.get('memory_rows') or [])} local visual memory rows and {len(capsules)} label capsules.")
    reasons.append("Teacher corrections have higher weight than auto seed rows; filenames are not used as labels.")
    failure_notes = diagnose_failure(dict(sorted_scores), neighbors, base_scores=base_scores)
    return {
        "scores": {k: round(float(v), 5) for k, v in sorted_scores},
        "capsule_scores": {k: round(float(v), 5) for k, v in sorted(capsule_scores.items(), key=lambda kv: kv[1], reverse=True)[:22]},
        "prototype_scores": {k: round(float(v), 5) for k, v in sorted(prototype_scores.items(), key=lambda kv: kv[1], reverse=True)[:22]},
        "linear_scores": {k: round(float(v), 5) for k, v in sorted(linear_scores.items(), key=lambda kv: kv[1], reverse=True)[:22]},
        "memory_scores": {k: round(float(v), 5) for k, v in sorted(memory.items(), key=lambda kv: kv[1], reverse=True)[:22]},
        "neighbors": neighbors,
        "reason": reasons,
        "failure_notes": failure_notes,
    }


__all__ = [
    "SUPERBRAIN_VERSION",
    "SUPERBRAIN_MODEL_FILENAME",
    "model_path",
    "train_superbrain_model",
    "load_superbrain_model",
    "superbrain_summary",
    "predict_superbrain_vector",
    "diagnose_failure",
    "cortex_expand",
]

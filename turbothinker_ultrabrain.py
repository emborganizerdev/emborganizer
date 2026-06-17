"""
turbothinker_ultrabrain.py
EMBORGANIZER v5.0 local UltraBrain recognition engine.

This module adds a larger local recognition layer above the v4.9 student model.
It is still fully local, dependency-light, and does not use any file title/name
as a label. It learns from image-derived feature vectors, user corrections, and
visual seed banks.

UltraBrain is intentionally built as an expandable ensemble instead of one huge
opaque script:
- one-vs-rest trainable logistic heads with saved weights
- per-tag visual prototypes
- k-nearest visual memory over the training bank
- tag co-occurrence graph for embroidery-specific reasoning
- confidence calibration and strict multi_design_preview first-tag support

Model output path:
    imgs_training/models/turbothinker_ultrabrain_v5_model.json
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

ULTRABRAIN_VERSION = "TurboThinker UltraBrain v5.0 • local ensemble recognition brain • no API"
ULTRABRAIN_MODEL_FILENAME = "turbothinker_ultrabrain_v5_model.json"
ULTRABRAIN_REPORT_FILENAME = "last_ultrabrain_training_report.json"

PRIMARY_OUTPUT_LABELS: List[str] = [
    "multi_design_preview",
    "heavy_work",
    "all_over_design",
    "front_neck",
    "back_neck",
    "boat_neck",
    "pot_neck",
    "v_neck_designs",
    "short_hand",
    "full_hand",
    "hand_design",
    "sleeve_panel",
    "cut_work",
    "net_work",
    "butti",
    "border",
    "flower_border",
    "flowers",
    "rangoli_design",
    "stitched_photo_reference",
    "back_drop_neck",
    "one_side_design",
    "mango",
    "mirror_designs",
    "peacock_parrot",
    "lotus_roses",
    "saree_pallus",
    "simple_designs",
    "kutch_work",
    "latkans",
    "3d_emboss",
    "cutwork",
    "net_designs",
    "allover_blouses",
    "back_drop_designs",
    "double_shoulder_neck_designs",
    "different_front_blouses",
    "heavy_outline",
]

TAG_ALIASES: Dict[str, str] = {
    "net_design": "net_work",
    "net_designs": "net_work",
    "cutwork": "cut_work",
    "boat_necks": "boat_neck",
    "pot_necks": "pot_neck",
    "allover_blouses": "all_over_design",
    "back_drop_designs": "back_drop_neck",
    "one_side_designs": "one_side_design",
    "blouse_back": "back_neck",
    "blouse_front": "front_neck",
    "hand_lines": "hand_design",
    "handlines_for_blouses": "hand_design",
    "flowers": "flowers",
    "flower": "flowers",
    "heavy": "heavy_work",
    "heavywork": "heavy_work",
    "multi_preview": "multi_design_preview",
    "multi_part_possible": "multi_design_preview",
}

ENGINE_TAGS = {
    "imgs_engine",
    "turbothinker_engine",
    "imgs_training_engine",
    "imgs engine",
    "turbothinker engine",
}

# Tags that can be displayed but should not become the main folder prediction.
STYLE_ONLY_TAGS = {
    "density_low",
    "density_medium",
    "density_high",
    "wide_horizontal",
    "tall_vertical",
    "symmetrical",
    "heavy_outline",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def model_path(app_root: Path) -> Path:
    return Path(app_root) / "imgs_training" / "models" / ULTRABRAIN_MODEL_FILENAME


def report_path(app_root: Path) -> Path:
    return Path(app_root) / "imgs_training" / "models" / ULTRABRAIN_REPORT_FILENAME


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


def normalize_tag(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    cleaned = "_".join("".join(ch.lower() if ch.isalnum() else " " for ch in text).split())
    return TAG_ALIASES.get(cleaned, cleaned)


def stable_labels(extra_labels: Optional[Iterable[str]] = None) -> List[str]:
    labels: List[str] = []
    for value in list(PRIMARY_OUTPUT_LABELS) + list(extra_labels or []):
        tag = normalize_tag(value)
        if tag and tag not in ENGINE_TAGS and tag not in labels:
            labels.append(tag)
    # Ensure aliases do not produce duplicate labels but keep user-facing useful tags.
    return labels


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        f = float(value)
        if math.isfinite(f):
            return f
    except Exception:
        pass
    return default


def safe_vector(raw: Any, feature_count: Optional[int] = None) -> List[float]:
    if not isinstance(raw, (list, tuple)):
        raw = []
    vec: List[float] = []
    for value in raw:
        f = _safe_float(value)
        # Most IMGS features are already in 0..1. Keep aspect-like features bounded.
        vec.append(max(-4.0, min(4.0, f)))
    if feature_count is not None:
        if len(vec) < feature_count:
            vec.extend([0.0] * (feature_count - len(vec)))
        elif len(vec) > feature_count:
            vec = vec[:feature_count]
    return vec


def _feature_vector_from_features(features: Dict[str, Any]) -> List[float]:
    """Build the same rough vector shape from an analysis features dict.

    imgs_training.py normally provides feature_vector rows for seed-bank samples.
    Corrections usually store named features, so this helper reconstructs a
    compatible vector without importing imgs_training.py (avoids circular import).
    """
    if isinstance(features.get("feature_vector"), list):
        return safe_vector(features.get("feature_vector"))
    keys = [
        "ink_density",
        "ink_coverage",
        "foreground_ratio",
        "net_score",
        "scattered_score",
        "edge_strength",
        "estimated_region_count_norm",
        "horizontal_balance",
        "symmetry_left_right",
        "symmetry_top_bottom",
        "component_count_norm",
        "colorfulness",
        "center_mass_x",
        "center_mass_y",
        "top_density",
        "middle_density",
        "bottom_density",
        "left_density",
        "right_density",
    ]
    # Use known names when they exist, then fill with derived approximations.
    vec: List[float] = []
    density = _safe_float(features.get("ink_density"))
    coverage = _safe_float(features.get("ink_coverage"))
    net = _safe_float(features.get("net_score"))
    scattered = _safe_float(features.get("scattered_score"))
    edge = _safe_float(features.get("edge_strength"))
    regions = _safe_float(features.get("estimated_region_count"))
    comp = _safe_float(features.get("component_count"))
    aspect = _safe_float(features.get("aspect") or features.get("original_aspect"), 1.0)
    fallback = {
        "ink_density": density,
        "ink_coverage": coverage,
        "foreground_ratio": coverage,
        "net_score": net,
        "scattered_score": scattered,
        "edge_strength": edge,
        "estimated_region_count_norm": max(0.0, min(1.0, regions / 6.0)),
        "horizontal_balance": max(0.0, min(1.0, aspect / 2.5)),
        "symmetry_left_right": _safe_float(features.get("symmetry_left_right"), 24),
        "symmetry_top_bottom": _safe_float(features.get("symmetry_top_bottom"), 24),
        "component_count_norm": max(0.0, min(1.0, comp / 60.0)),
        "colorfulness": _safe_float(features.get("colorfulness"), 0.1),
        "center_mass_x": _safe_float(features.get("center_mass_x"), 24),
        "center_mass_y": _safe_float(features.get("center_mass_y"), 24),
        "top_density": _safe_float(features.get("top_density"), density),
        "middle_density": _safe_float(features.get("middle_density"), density),
        "bottom_density": _safe_float(features.get("bottom_density"), density),
        "left_density": _safe_float(features.get("left_density"), density),
        "right_density": _safe_float(features.get("right_density"), density),
    }
    for key in keys:
        vec.append(_safe_float(features.get(key), fallback.get(key, 0.0)))
    return vec


def augment_vector(vec: Sequence[float], feature_count: int) -> List[float]:
    """Expand compact image features into a richer local model vector.

    This is where the new brain gets more expressive without external libraries.
    It adds non-linear terms and embroidery-specific interactions like density ×
    net_score, coverage × regions, edge × symmetry, etc.
    """
    x = safe_vector(vec, feature_count)
    if not x:
        x = [0.0] * feature_count
    out: List[float] = []
    out.extend(x)
    out.extend([v * v for v in x])
    out.extend([math.sqrt(abs(v)) if v >= 0 else -math.sqrt(abs(v)) for v in x])
    # Selected interactions. The base v4.8/4.9 feature vectors are usually 19 dims.
    pairs = [
        (0, 1), (0, 3), (0, 5), (0, 6),
        (1, 3), (1, 6), (1, 8),
        (3, 5), (3, 6), (3, 10),
        (4, 10), (5, 8), (5, 9),
        (6, 7), (6, 17), (6, 18),
        (8, 9), (13, 14), (15, 16), (17, 18),
    ]
    for a, b in pairs:
        va = x[a] if a < len(x) else 0.0
        vb = x[b] if b < len(x) else 0.0
        out.append(va * vb)
    # Hand-built aggregate detectors.
    density = x[0] if len(x) > 0 else 0.0
    coverage = x[2] if len(x) > 2 else (x[1] if len(x) > 1 else 0.0)
    net = x[3] if len(x) > 3 else 0.0
    scattered = x[4] if len(x) > 4 else 0.0
    edge = x[5] if len(x) > 5 else 0.0
    regions = x[6] if len(x) > 6 else 0.0
    symmetry_lr = x[8] if len(x) > 8 else 24
    symmetry_tb = x[9] if len(x) > 9 else 24
    top = x[14] if len(x) > 14 else density
    mid = x[15] if len(x) > 15 else density
    bot = x[16] if len(x) > 16 else density
    left = x[17] if len(x) > 17 else density
    right = x[18] if len(x) > 18 else density
    out.extend([
        density + coverage,
        density * max(0.0, regions),
        coverage * max(0.0, regions),
        net * edge,
        scattered * edge,
        abs(left - right),
        abs(top - bot),
        max(top, mid, bot),
        max(left, right),
        min(1.0, (symmetry_lr + symmetry_tb) / 2.0),
        max(0.0, mid - (top + bot) / 2.0),
        max(0.0, bot - top),
    ])
    return [max(-6.0, min(6.0, _safe_float(v))) for v in out]


def _mean_std(matrix: List[List[float]]) -> Tuple[List[float], List[float]]:
    if not matrix:
        return [], []
    n = len(matrix)
    m = max(len(row) for row in matrix)
    means: List[float] = []
    stds: List[float] = []
    for j in range(m):
        vals = [row[j] if j < len(row) else 0.0 for row in matrix]
        mu = sum(vals) / max(1, n)
        var = sum((v - mu) ** 2 for v in vals) / max(1, n)
        means.append(mu)
        stds.append(max(1e-5, math.sqrt(var)))
    return means, stds


def _standardize(vec: Sequence[float], means: Sequence[float], stds: Sequence[float]) -> List[float]:
    out = []
    for j in range(len(means)):
        v = vec[j] if j < len(vec) else 0.0
        out.append(max(-8.0, min(8.0, (v - means[j]) / (stds[j] if j < len(stds) and stds[j] else 1.0))))
    return out


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-min(60.0, x))
        return 1.0 / (1.0 + z)
    z = math.exp(max(-60.0, x))
    return z / (1.0 + z)


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(float(x) * float(y) for x, y in zip(a, b))


def _l2(a: Sequence[float], b: Sequence[float]) -> float:
    m = max(len(a), len(b))
    if m <= 0:
        return 999.0
    total = 0.0
    for i in range(m):
        av = a[i] if i < len(a) else 0.0
        bv = b[i] if i < len(b) else 0.0
        d = av - bv
        total += d * d
    return math.sqrt(total / m)


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    num = _dot(a, b)
    da = math.sqrt(max(1e-12, _dot(a, a)))
    db = math.sqrt(max(1e-12, _dot(b, b)))
    return max(-1.0, min(1.0, num / (da * db)))


def _labels_from_row(row: Dict[str, Any], output_labels: List[str]) -> List[str]:
    labels: List[str] = []
    scores = row.get("scores") or {}
    for value in [row.get("predicted_type"), row.get("final_label"), row.get("image_mode")]:
        tag = normalize_tag(value)
        if tag and tag not in STYLE_ONLY_TAGS and tag not in ENGINE_TAGS and tag not in labels:
            labels.append(tag)
    for value in row.get("tags") or []:
        tag = normalize_tag(value)
        if tag and tag not in ENGINE_TAGS and tag not in labels:
            labels.append(tag)
    # Convert strong scores into labels, while avoiding weak leftover pollution.
    if isinstance(scores, dict):
        for key, value in scores.items():
            tag = normalize_tag(key)
            score = _safe_float(value)
            if tag and score >= 0.30 and tag not in labels:
                labels.append(tag)
    # Keep only known output labels when possible, but allow a tiny future expansion.
    known = set(output_labels)
    final = [tag for tag in labels if tag in known or tag not in STYLE_ONLY_TAGS]
    return final



def _labels_from_part_hint(part: Dict[str, Any]) -> List[str]:
    hint = normalize_tag(part.get("review_hint") or part.get("zone") or "")
    zone = normalize_tag(part.get("zone") or "")
    labels: List[str] = []
    text = f"{hint} {zone}"
    mapping = [
        ("front_neck", "front_neck"),
        ("back_neck", "back_neck"),
        ("boat_neck", "boat_neck"),
        ("pot_neck", "pot_neck"),
        ("short_hand", "short_hand"),
        ("full_hand", "full_hand"),
        ("sleeve", "sleeve_panel"),
        ("hand", "hand_design"),
        ("border", "border"),
        ("butti", "butti"),
        ("stitched_photo", "stitched_photo_reference"),
        ("hanging_panel", "border"),
    ]
    for key, label in mapping:
        if key in text and label not in labels:
            labels.append(label)
    return labels


def _augmented_view_rows_from_seed(raw: Dict[str, Any], base_vec: List[float], base_labels: List[str], output_labels: List[str]) -> List[Dict[str, Any]]:
    """Create image-derived part rows from TurboThinker's detected zones.

    These are not filename labels. They are weak part-teaching rows derived from
    the original image's visual zone densities and review hints. They help the
    model learn that a multi-preview page contains several sub-design regions.
    """
    rows: List[Dict[str, Any]] = []
    parts = list(raw.get("parts_detected") or [])[:5]
    known = set(output_labels)
    for idx, part in enumerate(parts, start=1):
        zone_density = max(0.0, min(1.0, _safe_float(part.get("zone_density"))))
        if zone_density <= 0.025:
            continue
        vec = list(base_vec)
        if len(vec) >= 1:
            vec[0] = max(0.0, min(1.0, zone_density))
        if len(vec) >= 3:
            vec[2] = max(0.0, min(1.0, vec[2] * 245 + zone_density * 0.45))
        if len(vec) >= 5:
            vec[4] = max(0.0, min(1.0, vec[4] * 0.70 + 0.12))
        if len(vec) >= 7:
            vec[6] = max(0.0, min(1.0, 1.0 / 6.0))
        if len(vec) >= 18:
            zone = normalize_tag(part.get("zone"))
            if "left" in zone:
                vec[17] = max(vec[17], zone_density)
            if "right" in zone and len(vec) >= 19:
                vec[18] = max(vec[18], zone_density)
        labels = []
        for tag in _labels_from_part_hint(part) + base_labels:
            tag = normalize_tag(tag)
            if tag in known and tag not in labels:
                labels.append(tag)
        # A part crop is often no longer the whole multi preview. Keep it as a
        # supporting tag only if the hint is still multi-like.
        if "multi_design_preview" in labels and len(labels) > 1:
            labels = [x for x in labels if x != "multi_design_preview"] + ["multi_design_preview"]
        if not labels:
            continue
        rows.append({
            "sample_id": f"{raw.get('sample_id') or 'seed'}_visual_part_{idx}",
            "source": "seed_visual_part_augmentation",
            "feature_vector": vec,
            "labels": labels[:10],
            "weight": 248,
            "predicted_type": labels[0],
            "image_mode": "part_view",
            "trained_from_filename": False,
        })
    return rows

def training_rows_from_seed_bank(seed_bank: Dict[str, Any], output_labels: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    labels = stable_labels(output_labels)
    rows: List[Dict[str, Any]] = []
    for raw in seed_bank.get("rows") or []:
        if not isinstance(raw, dict):
            continue
        vec = safe_vector(raw.get("feature_vector"))
        if not vec:
            continue
        tags = _labels_from_row(raw, labels)
        if not tags:
            continue
        base_row = {
            "sample_id": str(raw.get("sample_id") or f"seed_{len(rows)}"),
            "source": "seed_visual_bank",
            "feature_vector": vec,
            "labels": tags,
            "weight": 1.0,
            "predicted_type": normalize_tag(raw.get("predicted_type")),
            "image_mode": normalize_tag(raw.get("image_mode")),
            "trained_from_filename": False,
        }
        rows.append(base_row)
        rows.extend(_augmented_view_rows_from_seed(raw, vec, tags, labels))
    return rows


def training_rows_from_corrections(corrections: Dict[str, Any], output_labels: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    labels = stable_labels(output_labels)
    rows: List[Dict[str, Any]] = []
    for raw in corrections.get("samples") or []:
        if not isinstance(raw, dict):
            continue
        features = raw.get("features") or {}
        vec = safe_vector(raw.get("feature_vector") or _feature_vector_from_features(features))
        if not vec:
            continue
        row_labels = _labels_from_row(raw, labels)
        final_label = normalize_tag(raw.get("final_label"))
        if final_label and final_label not in row_labels:
            row_labels.insert(0, final_label)
        if not row_labels:
            continue
        rows.append({
            "sample_id": str(raw.get("sample_id") or f"correction_{len(rows)}"),
            "source": "user_correction",
            "feature_vector": vec,
            "labels": row_labels,
            "weight": 2.8,
            "predicted_type": normalize_tag(raw.get("predicted_type")),
            "final_label": final_label,
            "trained_from_filename": False,
        })
    for raw in corrections.get("selector_samples") or []:
        if not isinstance(raw, dict):
            continue
        selector = raw.get("selector_result") or {}
        analysis = selector.get("analysis") or raw.get("analysis") or {}
        features = analysis.get("features") or raw.get("features") or {}
        vec = safe_vector(selector.get("feature_vector") or raw.get("feature_vector") or _feature_vector_from_features(features))
        if not vec:
            continue
        row_labels = []
        for value in list(selector.get("selector_tags") or []) + list(raw.get("manual_tags") or []):
            tag = normalize_tag(value)
            if tag and tag not in row_labels:
                row_labels.append(tag)
        if not row_labels:
            continue
        rows.append({
            "sample_id": str(raw.get("sample_id") or f"selector_{len(rows)}"),
            "source": "selector_correction",
            "feature_vector": vec,
            "labels": row_labels,
            "weight": 3.4,
            "trained_from_filename": False,
        })
    return rows


def _build_cooccurrence(rows: List[Dict[str, Any]], output_labels: List[str]) -> Dict[str, Dict[str, float]]:
    counts = Counter()
    pairs: Dict[str, Counter] = {label: Counter() for label in output_labels}
    for row in rows:
        row_labels = [tag for tag in row.get("labels") or [] if tag in output_labels]
        unique = sorted(set(row_labels))
        for a in unique:
            counts[a] += 1
            for b in unique:
                if a != b:
                    pairs[a][b] += 1
    graph: Dict[str, Dict[str, float]] = {}
    for a in output_labels:
        denom = max(1, counts[a])
        graph[a] = {b: round(c / denom, 5) for b, c in pairs[a].most_common(12) if c > 0}
    return graph


def _train_logistic_head(
    matrix: List[List[float]],
    targets: List[int],
    weights_for_rows: List[float],
    epochs: int,
    lr: float,
    l2: float,
    seed: int,
) -> Tuple[List[float], float, Dict[str, Any]]:
    rng = random.Random(seed)
    if not matrix:
        return [], 0.0, {"loss": None}
    n = len(matrix)
    m = len(matrix[0])
    w = [rng.uniform(-0.015, 0.015) for _ in range(m)]
    pos = sum(1 for t in targets if t)
    neg = n - pos
    if pos <= 0:
        return [0.0] * m, -8.0, {"positive": 0, "negative": neg, "skipped": "no_positive_rows"}
    # Prior bias from class frequency.
    p = max(0.005, min(0.995, pos / max(1, n)))
    b = math.log(p / (1.0 - p))
    order = list(range(n))
    final_loss = 0.0
    # Class balancing prevents rare tags from disappearing.
    pos_scale = 24 * n / max(1, pos)
    neg_scale = 24 * n / max(1, neg)
    for epoch in range(max(1, int(epochs))):
        rng.shuffle(order)
        eta = lr / (1.0 + epoch * 0.012)
        loss = 0.0
        for idx in order:
            x = matrix[idx]
            y = 1.0 if targets[idx] else 0.0
            class_scale = pos_scale if y else neg_scale
            rw = max(0.1, min(4.0, weights_for_rows[idx])) * class_scale
            z = _dot(w, x) + b
            pred = _sigmoid(z)
            err = (pred - y) * rw
            for j in range(m):
                w[j] -= eta * (err * x[j] + l2 * w[j])
            b -= eta * err
            loss += -(y * math.log(max(1e-8, pred)) + (1 - y) * math.log(max(1e-8, 1 - pred))) * rw
        final_loss = loss / max(1, n)
    return [round(v, 7) for v in w], round(b, 7), {
        "positive": int(pos),
        "negative": int(neg),
        "loss": round(float(final_loss), 6),
    }


def _build_prototypes(matrix: List[List[float]], rows: List[Dict[str, Any]], output_labels: List[str]) -> Dict[str, Dict[str, Any]]:
    by_label: Dict[str, List[List[float]]] = {label: [] for label in output_labels}
    for x, row in zip(matrix, rows):
        labels = set(row.get("labels") or [])
        for label in output_labels:
            if label in labels:
                by_label[label].append(x)
    prototypes: Dict[str, Dict[str, Any]] = {}
    for label, vectors in by_label.items():
        if not vectors:
            continue
        m = len(vectors[0])
        centroid = [sum(row[j] for row in vectors) / len(vectors) for j in range(m)]
        distances = [_l2(row, centroid) for row in vectors]
        spread = max(0.18, sorted(distances)[int(0.75 * (len(distances) - 1))] if distances else 0.3)
        prototypes[label] = {
            "count": len(vectors),
            "centroid": [round(v, 7) for v in centroid],
            "spread": round(float(spread), 7),
            "mean_distance": round(sum(distances) / max(1, len(distances)), 7),
        }
    return prototypes


def train_ultrabrain_model(
    app_root: Path,
    seed_bank: Dict[str, Any],
    corrections: Optional[Dict[str, Any]] = None,
    epochs: int = 260,
    extra_labels: Optional[Iterable[str]] = None,
    max_knn_rows: int = 1600,
) -> Dict[str, Any]:
    started = time.time()
    output_labels = stable_labels(list(extra_labels or []))
    rows = training_rows_from_seed_bank(seed_bank, output_labels)
    correction_rows = training_rows_from_corrections(corrections or {}, output_labels)
    rows.extend(correction_rows)
    if not rows:
        raise RuntimeError("UltraBrain needs seed-bank rows or user corrections before training.")
    requested_epochs = int(epochs)
    # Keep local training practical in Streamlit even when UltraBrain generates
    # thousands of visual part rows. The ensemble also uses prototypes/KNN, so
    # very high logistic epochs are not needed.
    if len(rows) >= 1200:
        epochs = min(requested_epochs, 55)
    elif len(rows) >= 700:
        epochs = min(requested_epochs, 75)
    else:
        epochs = min(requested_epochs, 120)
    feature_count = max(len(safe_vector(row.get("feature_vector"))) for row in rows)
    augmented = [augment_vector(row.get("feature_vector") or [], feature_count) for row in rows]
    means, stds = _mean_std(augmented)
    matrix = [_standardize(vec, means, stds) for vec in augmented]
    row_weights = [float(row.get("weight") or 1.0) for row in rows]
    positive_counts = Counter()
    for row in rows:
        for label in set(row.get("labels") or []):
            if label in output_labels:
                positive_counts[label] += 1
    label_models: Dict[str, Dict[str, Any]] = {}
    trainable_labels = [label for label in output_labels if positive_counts[label] > 0]
    for i, label in enumerate(trainable_labels):
        targets = [1 if label in set(row.get("labels") or []) else 0 for row in rows]
        w, b, stats = _train_logistic_head(
            matrix,
            targets,
            row_weights,
            epochs=epochs,
            lr=0.045,
            l2=0.0009,
            seed=5000 + i,
        )
        label_models[label] = {
            "weights": w,
            "bias": b,
            "positive_count": int(positive_counts[label]),
            "training_stats": stats,
            "threshold": 0.42 if positive_counts[label] >= 8 else 240,
        }
    prototypes = _build_prototypes(matrix, rows, output_labels)
    cooccurrence = _build_cooccurrence(rows, output_labels)
    # KNN memory uses standardized augmented vectors. Keep all rows by default; still tiny.
    knn_rows: List[Dict[str, Any]] = []
    for x, row in zip(matrix[:max_knn_rows], rows[:max_knn_rows]):
        labels = [tag for tag in row.get("labels") or [] if tag in output_labels]
        if not labels:
            continue
        knn_rows.append({
            "sample_id": row.get("sample_id"),
            "source": row.get("source"),
            "labels": labels[:14],
            "vector": [round(v, 6) for v in x],
            "weight": round(float(row.get("weight") or 1.0), 3),
        })
    model = {
        "version": ULTRABRAIN_VERSION,
        "model_type": "local_ensemble_logistic_prototype_knn_cooccurrence",
        "created_at": utc_now(),
        "trained_from_filename": False,
        "source_name_used_for_label": False,
        "note": "UltraBrain trains from visual features, seed-bank pseudo labels, and user corrections. User corrections should be preferred over auto labels.",
        "feature_count": int(feature_count),
        "augmented_feature_count": len(means),
        "output_labels": output_labels,
        "standardization": {
            "means": [round(v, 7) for v in means],
            "stds": [round(v, 7) for v in stds],
        },
        "label_models": label_models,
        "prototypes": prototypes,
        "cooccurrence": cooccurrence,
        "knn_rows": knn_rows,
        "positive_counts": dict(sorted(positive_counts.items())),
        "training_summary": {
            "rows": len(rows),
            "seed_rows": len(rows) - len(correction_rows),
            "correction_rows": len(correction_rows),
            "labels_with_positive_rows": len(trainable_labels),
            "output_labels": len(output_labels),
            "epochs": int(epochs),
            "requested_epochs": int(requested_epochs),
            "seconds": round(time.time() - started, 3),
        },
    }
    path = model_path(app_root)
    _write_json(path, model)
    report = ultrabrain_report(model, path)
    _write_json(report_path(app_root), report)
    return report


def ultrabrain_report(model: Dict[str, Any], path: Optional[Path] = None) -> Dict[str, Any]:
    summary = model.get("training_summary") or {}
    return {
        "status": "trained",
        "version": model.get("version"),
        "model_type": model.get("model_type"),
        "model_path": str(path or ""),
        "training_summary": summary,
        "feature_count": model.get("feature_count"),
        "augmented_feature_count": model.get("augmented_feature_count"),
        "output_labels": len(model.get("output_labels") or []),
        "labels_with_weights": len(model.get("label_models") or {}),
        "knn_memory_rows": len(model.get("knn_rows") or []),
        "trained_from_filename": False,
        "source_name_used_for_label": False,
        "top_positive_counts": dict(Counter(model.get("positive_counts") or {}).most_common(16)),
        "created_at": model.get("created_at"),
    }


def load_ultrabrain_model(app_root: Path) -> Dict[str, Any]:
    return _read_json(model_path(app_root), {})


def ultrabrain_summary(app_root: Path) -> Dict[str, Any]:
    model = load_ultrabrain_model(app_root)
    if not model:
        return {"exists": False, "version": ULTRABRAIN_VERSION}
    report = ultrabrain_report(model, model_path(app_root))
    report["exists"] = True
    return report


def _model_vector(model: Dict[str, Any], raw_vec: Sequence[float]) -> List[float]:
    feature_count = int(model.get("feature_count") or len(raw_vec) or 1)
    aug = augment_vector(raw_vec, feature_count)
    std = model.get("standardization") or {}
    return _standardize(aug, std.get("means") or [], std.get("stds") or [])


def _knn_scores(model: Dict[str, Any], qx: Sequence[float], k: int = 18) -> Tuple[Dict[str, float], List[Dict[str, Any]]]:
    rows = model.get("knn_rows") or []
    scored: List[Tuple[float, Dict[str, Any]]] = []
    for row in rows:
        vec = row.get("vector") or []
        dist = _l2(qx, vec)
        cos = _cosine(qx, vec)
        sim = max(0.0, 245 * (1.0 - min(1.0, dist / 3.2)) + 0.45 * ((cos + 1.0) / 2.0))
        if sim > 0:
            scored.append((sim * float(row.get("weight") or 1.0), row))
    scored.sort(key=lambda item: item[0], reverse=True)
    top = scored[:k]
    totals: Dict[str, float] = defaultdict(float)
    denom = 1e-8
    neighbors: List[Dict[str, Any]] = []
    for score, row in top:
        denom += score
        for label in row.get("labels") or []:
            totals[label] += score
        neighbors.append({
            "sample_id": row.get("sample_id"),
            "source": row.get("source"),
            "similarity": round(min(0.999, score / max(0.1, float(row.get("weight") or 1.0))), 4),
            "labels": list(row.get("labels") or [])[:8],
        })
    return {label: min(0.99, value / denom) for label, value in totals.items()}, neighbors


def predict_ultrabrain_vector(
    model: Dict[str, Any],
    feature_vector: Sequence[float],
    base_scores: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    if not model:
        return {"scores": {}, "neighbors": [], "reason": ["UltraBrain model is not trained yet."]}
    qx = _model_vector(model, feature_vector)
    output_labels = list(model.get("output_labels") or [])
    label_models = model.get("label_models") or {}
    prototypes = model.get("prototypes") or {}
    base_scores = {normalize_tag(k): _safe_float(v) for k, v in (base_scores or {}).items()}
    logistic_scores: Dict[str, float] = {}
    prototype_scores: Dict[str, float] = {}
    for label in output_labels:
        head = label_models.get(label) or {}
        if head.get("weights"):
            logistic_scores[label] = _sigmoid(_dot(qx, head.get("weights") or []) + _safe_float(head.get("bias")))
        proto = prototypes.get(label) or {}
        if proto.get("centroid"):
            dist = _l2(qx, proto.get("centroid") or [])
            spread = max(0.18, _safe_float(proto.get("spread"), 0.45))
            prototype_scores[label] = math.exp(-24 * (dist / spread) ** 2)
    knn, neighbors = _knn_scores(model, qx)
    merged: Dict[str, float] = {}
    for label in output_labels:
        logit = logistic_scores.get(label, 0.0)
        proto = prototype_scores.get(label, 0.0)
        near = knn.get(label, 0.0)
        base = base_scores.get(label, 0.0)
        # Keep rule/student scores alive, but let UltraBrain dominate when it has visual evidence.
        score = 0.40 * logit + 0.25 * proto + 0.22 * near + 0.13 * base
        merged[label] = max(0.0, min(0.995, score))
    # Co-occurrence reasoning: if a visual parent is strong, nudge common sibling tags.
    graph = model.get("cooccurrence") or {}
    top_parents = [label for label, score in sorted(merged.items(), key=lambda kv: kv[1], reverse=True)[:6] if score >= 0.38]
    for parent in top_parents:
        parent_score = merged.get(parent, 0.0)
        for child, assoc in (graph.get(parent) or {}).items():
            assoc_f = _safe_float(assoc)
            if assoc_f >= 0.12:
                merged[child] = min(0.995, max(merged.get(child, 0.0), merged.get(child, 0.0) + parent_score * assoc_f * 0.11))
    sorted_scores = sorted(merged.items(), key=lambda kv: kv[1], reverse=True)
    reasons = []
    if sorted_scores:
        top_label, top_score = sorted_scores[0]
        reasons.append(f"UltraBrain top visual label `{top_label}` scored {top_score:.2f} using local weights, prototypes, and nearest visual memory.")
    if neighbors:
        reasons.append(f"UltraBrain compared the query against {len(model.get('knn_rows') or [])} local visual memory rows and used the closest {min(len(neighbors), 18)} neighbors.")
    reasons.append("UltraBrain does not learn from filenames; source names are only saved for review/debugging.")
    return {
        "scores": {k: round(float(v), 5) for k, v in sorted_scores},
        "logistic_scores": {k: round(float(v), 5) for k, v in sorted(logistic_scores.items(), key=lambda kv: kv[1], reverse=True)[:18]},
        "prototype_scores": {k: round(float(v), 5) for k, v in sorted(prototype_scores.items(), key=lambda kv: kv[1], reverse=True)[:18]},
        "knn_scores": {k: round(float(v), 5) for k, v in sorted(knn.items(), key=lambda kv: kv[1], reverse=True)[:18]},
        "neighbors": neighbors,
        "reason": reasons,
    }


__all__ = [
    "ULTRABRAIN_VERSION",
    "ULTRABRAIN_MODEL_FILENAME",
    "PRIMARY_OUTPUT_LABELS",
    "normalize_tag",
    "model_path",
    "train_ultrabrain_model",
    "load_ultrabrain_model",
    "ultrabrain_summary",
    "predict_ultrabrain_vector",
    "training_rows_from_seed_bank",
    "training_rows_from_corrections",
]

"""
turbothinker_student.py
EMBORGANIZER v4.9 local AI-student model.

This module is intentionally small and dependency-free. It trains real model
weights locally from visual feature vectors extracted from images. It does not
call any API and it does not use filenames as labels.

Model type
- Multi-label logistic student model.
- Input: compact visual feature vector from imgs_training.extract_visual_features.
- Output: probabilities for embroidery tags/types such as multi_design_preview,
  heavy_work, front_neck, cut_work, border, etc.
- Saved model: imgs_training/models/turbothinker_student_v4_9_weights.json

Important honesty
- If labels came from the rule engine/seed bank, the model is a real trained
  weighted model, but the labels are pseudo-labels and still need user review.
- User corrections are treated as stronger supervised training rows.
"""
from __future__ import annotations

import json
import math
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

STUDENT_MODEL_VERSION = "TurboThinker Student v4.9 • local trained weights • no API"
MODEL_FILENAME = "turbothinker_student_v4_9_weights.json"

# Keep this list stable so old weights remain loadable. Labels can be expanded in
# later versions by retraining.
DEFAULT_OUTPUT_LABELS: List[str] = [
    "multi_design_preview",
    "heavy_work",
    "all_over_design",
    "front_neck",
    "back_neck",
    "boat_neck",
    "pot_neck",
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
    "one_side_design",
    "back_drop_neck",
    "heavy_outline",
    "mango",
    "mirror_designs",
    "peacock_parrot",
    "lotus_roses",
    "saree_pallus",
    "simple_designs",
    "v_neck_designs",
]

ENGINE_TAGS = {"imgs_engine", "turbothinker_engine", "imgs training engine", "turbothinker engine"}
ALIASES = {
    "net_design": "net_work",
    "net_designs": "net_work",
    "cutwork": "cut_work",
    "boat_necks": "boat_neck",
    "pot_necks": "pot_neck",
    "allover_blouses": "all_over_design",
    "one_side_designs": "one_side_design",
    "back_drop_designs": "back_drop_neck",
    "blouse_back": "back_neck",
    "blouse_front": "front_neck",
    "hand_lines": "hand_design",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_label(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    cleaned = "_".join("".join(ch.lower() if ch.isalnum() else " " for ch in text).split())
    return ALIASES.get(cleaned, cleaned)


def student_model_path(app_root: Path) -> Path:
    return Path(app_root) / "imgs_training" / "models" / MODEL_FILENAME


def ensure_model_dir(app_root: Path) -> Path:
    p = student_model_path(app_root)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _read_json(path: Path, default: Any) -> Any:
    try:
        if Path(path).exists():
            return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def _write_json(path: Path, data: Any) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-min(60.0, x))
        return 1.0 / (1.0 + z)
    z = math.exp(max(-60.0, x))
    return z / (1.0 + z)


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(float(x) * float(y) for x, y in zip(a, b))


def _safe_vector(raw: Any, feature_count: Optional[int] = None) -> List[float]:
    if not isinstance(raw, (list, tuple)):
        raw = []
    vec = []
    for v in raw:
        try:
            f = float(v)
            if not math.isfinite(f):
                f = 0.0
        except Exception:
            f = 0.0
        vec.append(f)
    if feature_count is not None:
        if len(vec) < feature_count:
            vec.extend([0.0] * (feature_count - len(vec)))
        elif len(vec) > feature_count:
            vec = vec[:feature_count]
    return vec


def _mean_std(vectors: List[List[float]]) -> Tuple[List[float], List[float]]:
    n = len(vectors)
    d = max((len(v) for v in vectors), default=0)
    if n <= 0 or d <= 0:
        return [], []
    padded = [_safe_vector(v, d) for v in vectors]
    mean = [sum(v[i] for v in padded) / n for i in range(d)]
    std: List[float] = []
    for i in range(d):
        var = sum((v[i] - mean[i]) ** 2 for v in padded) / max(1, n)
        s = math.sqrt(var)
        std.append(s if s >= 1e-6 else 1.0)
    return mean, std


def _normalize_vector(vec: Sequence[float], mean: Sequence[float], std: Sequence[float]) -> List[float]:
    d = len(mean)
    v = _safe_vector(vec, d)
    return [(v[i] - float(mean[i])) / max(1e-6, float(std[i])) for i in range(d)]


def _labels_from_row(row: Dict[str, Any], output_labels: Sequence[str], score_cutoff: float = 0.24) -> List[str]:
    allowed = set(output_labels)
    labels = set()
    for t in row.get("tags") or []:
        nt = normalize_label(t)
        if nt and nt not in ENGINE_TAGS and nt in allowed:
            labels.add(nt)
    # Scores are often more useful than the final primary type for multi-preview
    # training because one collage can contain neck + hand + border + motif tags.
    for k, v in (row.get("scores") or {}).items():
        nt = normalize_label(k)
        try:
            score = float(v)
        except Exception:
            score = 0.0
        if nt in allowed and score >= score_cutoff:
            labels.add(nt)
    pred = normalize_label(row.get("final_label") or row.get("predicted_type"))
    if pred in allowed:
        labels.add(pred)
    image_mode = str(row.get("image_mode") or "")
    if image_mode == "multi_design_preview":
        labels.add("multi_design_preview")
    # Keep important implied tags from features/mode.
    est = row.get("estimated_unique_designs") or {}
    if isinstance(est, dict):
        try:
            if int(est.get("min") or 1) >= 4 and "multi_design_preview" in allowed:
                labels.add("multi_design_preview")
        except Exception:
            pass
    return sorted(labels)


def rows_from_seed_bank(seed_bank: Dict[str, Any], output_labels: Sequence[str]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for row in seed_bank.get("rows") or []:
        vec = _safe_vector(row.get("feature_vector") or [])
        if not vec:
            continue
        labels = _labels_from_row(row, output_labels)
        if not labels:
            continue
        conf = float(row.get("confidence") or 45) / 100.0
        # Pseudo labels are real training targets but lower trust than manual corrections.
        weight = 0.40 + min(245, max(0.0, conf) * 245)
        rows.append({
            "source": "seed_visual_bank",
            "sample_id": row.get("sample_id"),
            "feature_vector": vec,
            "labels": labels,
            "weight": round(weight, 4),
            "trusted": False,
        })
    return rows


def rows_from_corrections(corrections: Dict[str, Any], output_labels: Sequence[str], feature_vector_func=None) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for sample in corrections.get("samples") or []:
        labels = []
        final_label = normalize_label(sample.get("final_label"))
        if final_label in output_labels:
            labels.append(final_label)
        for t in sample.get("final_tags") or sample.get("tags") or []:
            nt = normalize_label(t)
            if nt in output_labels and nt not in labels:
                labels.append(nt)
        if not labels:
            continue
        if sample.get("feature_vector"):
            vec = _safe_vector(sample.get("feature_vector"))
        elif callable(feature_vector_func):
            try:
                vec = _safe_vector(feature_vector_func(sample.get("features") or {}))
            except Exception:
                vec = []
        else:
            vec = []
        if not vec:
            continue
        rows.append({
            "source": "user_correction",
            "sample_id": sample.get("sample_id") or sample.get("source_name"),
            "feature_vector": vec,
            "labels": labels,
            "weight": 2.60,
            "trusted": True,
        })
    return rows


def train_multilabel_student(
    training_rows: List[Dict[str, Any]],
    output_labels: Optional[Sequence[str]] = None,
    epochs: int = 320,
    lr: float = 0.075,
    l2: float = 0.0006,
    seed: int = 49,
) -> Dict[str, Any]:
    labels = list(output_labels or DEFAULT_OUTPUT_LABELS)
    vectors = [_safe_vector(row.get("feature_vector") or []) for row in training_rows if row.get("feature_vector")]
    if len(vectors) < 2:
        raise ValueError("Need at least 2 visual training rows to train the local student model.")
    feature_count = max(len(v) for v in vectors)
    vectors = [_safe_vector(v, feature_count) for v in vectors]
    mean, std = _mean_std(vectors)
    x_all = [_normalize_vector(v, mean, std) for v in vectors]
    y_sets = [set(row.get("labels") or []) for row in training_rows if row.get("feature_vector")]
    row_weights = [float(row.get("weight") or 1.0) for row in training_rows if row.get("feature_vector")]
    n = len(x_all)
    rng = random.Random(seed)
    weights: Dict[str, List[float]] = {}
    bias: Dict[str, float] = {}
    losses: Dict[str, float] = {}
    positive_counts: Dict[str, int] = {}

    for label in labels:
        y = [1.0 if label in y_set else 0.0 for y_set in y_sets]
        pos = int(sum(y))
        neg = n - pos
        positive_counts[label] = pos
        if pos <= 0:
            weights[label] = [0.0] * feature_count
            bias[label] = -8.0
            losses[label] = 0.0
            continue
        if neg <= 0:
            # All examples are positive. Save a real learned constant output.
            weights[label] = [0.0] * feature_count
            bias[label] = 8.0
            losses[label] = 0.0
            continue
        w = [rng.uniform(-0.015, 0.015) for _ in range(feature_count)]
        # Class prior gives stable learning even for rare tags.
        b = math.log((pos + 1.0) / (neg + 1.0))
        pos_balance = n / max(1.0, 2.0 * pos)
        neg_balance = n / max(1.0, 2.0 * neg)
        final_loss = 0.0
        for ep in range(max(40, int(epochs))):
            grad_w = [0.0] * feature_count
            grad_b = 0.0
            loss = 0.0
            total_w = 0.0
            order = list(range(n))
            rng.shuffle(order)
            for idx in order:
                x = x_all[idx]
                yi = y[idx]
                balance = pos_balance if yi >= 24 else neg_balance
                sw = max(0.05, row_weights[idx]) * balance
                z = b + _dot(w, x)
                p = _sigmoid(z)
                err = (p - yi) * sw
                grad_b += err
                for j in range(feature_count):
                    grad_w[j] += err * x[j]
                # Clamped log loss for reporting only.
                pp = min(0.999999, max(0.000001, p))
                loss += (-(yi * math.log(pp) + (1.0 - yi) * math.log(1.0 - pp))) * sw
                total_w += sw
            denom = max(1.0, total_w)
            for j in range(feature_count):
                w[j] -= lr * ((grad_w[j] / denom) + l2 * w[j])
            b -= lr * (grad_b / denom)
            if ep == max(40, int(epochs)) - 1:
                final_loss = loss / denom
        weights[label] = [round(float(v), 8) for v in w]
        bias[label] = round(float(b), 8)
        losses[label] = round(float(final_loss), 6)

    trusted = sum(1 for row in training_rows if row.get("trusted"))
    model = {
        "version": STUDENT_MODEL_VERSION,
        "created_at": utc_now(),
        "model_type": "multi_label_logistic_student",
        "trained_from_filename": False,
        "source_name_used_for_label": False,
        "feature_count": feature_count,
        "output_labels": labels,
        "feature_mean": [round(float(v), 8) for v in mean],
        "feature_std": [round(float(v), 8) for v in std],
        "weights": weights,
        "bias": bias,
        "positive_counts": positive_counts,
        "loss_by_label": losses,
        "training_summary": {
            "rows": n,
            "trusted_user_corrections": trusted,
            "pseudo_seed_rows": n - trusted,
            "epochs": int(epochs),
            "learning_rate": lr,
            "l2": l2,
            "note": "Real local weights trained from image visual features. Pseudo labels still need review; user corrections are weighted stronger.",
        },
    }
    return model


def save_student_model(app_root: Path, model: Dict[str, Any]) -> Path:
    p = ensure_model_dir(app_root)
    _write_json(p, model)
    return p


def load_student_model(app_root: Path) -> Dict[str, Any]:
    return _read_json(student_model_path(app_root), {})


def student_model_summary(app_root: Path) -> Dict[str, Any]:
    p = student_model_path(app_root)
    m = load_student_model(app_root)
    if not m:
        return {"exists": False, "path": str(p)}
    ts = m.get("training_summary") or {}
    return {
        "exists": True,
        "path": str(p),
        "version": m.get("version"),
        "created_at": m.get("created_at"),
        "model_type": m.get("model_type"),
        "feature_count": m.get("feature_count"),
        "labels": len(m.get("output_labels") or []),
        "training_rows": ts.get("rows"),
        "pseudo_seed_rows": ts.get("pseudo_seed_rows"),
        "trusted_user_corrections": ts.get("trusted_user_corrections"),
        "trained_from_filename": bool(m.get("trained_from_filename")),
    }


def predict_vector(model: Dict[str, Any], feature_vector: Sequence[float]) -> Dict[str, float]:
    labels = list(model.get("output_labels") or [])
    mean = [float(v) for v in model.get("feature_mean") or []]
    std = [float(v) for v in model.get("feature_std") or []]
    weights = model.get("weights") or {}
    bias = model.get("bias") or {}
    if not labels or not mean or not weights:
        return {}
    x = _normalize_vector(feature_vector, mean, std)
    out: Dict[str, float] = {}
    for label in labels:
        w = [float(v) for v in weights.get(label) or []]
        b = float(bias.get(label) or 0.0)
        if len(w) < len(x):
            w = w + [0.0] * (len(x) - len(w))
        p = _sigmoid(b + _dot(w, x))
        out[label] = round(float(p), 6)
    return out

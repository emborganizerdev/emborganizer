"""
imgs_training.py
Local IMGS BetaV1 + TurboThinker training/cache helpers for EMBORGANIZER.

Goals
- No external API. Everything runs on the local Streamlit/server process.
- Read embroidery preview images and produce a best-effort type guess.
- Save the guess, visual features, optional fingerprint path, and user corrections as JSON.
- Keep this logic outside streamlit_app.py so the app does not become too large.

Important: v4.9 has two layers: the old rule/feature reader plus a real local
AI-student model trained into saved weights from image visual features. It is
still meant to be reviewed and corrected; corrections become stronger supervised
training rows for the next model rebuild.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from PIL import Image, ImageFilter, ImageOps, ImageStat

try:  # optional: reuse existing IMGS fingerprint engine when available
    from imagesearch import create_fingerprint_from_path, create_fingerprint_from_image
except Exception:  # pragma: no cover
    create_fingerprint_from_path = None
    create_fingerprint_from_image = None

try:  # v4.9 local trainable student model (no API, no external service)
    from turbothinker_student import (
        STUDENT_MODEL_VERSION,
        DEFAULT_OUTPUT_LABELS as STUDENT_OUTPUT_LABELS,
        train_multilabel_student,
        rows_from_seed_bank,
        rows_from_corrections,
        save_student_model,
        load_student_model,
        student_model_summary,
        predict_vector as predict_student_vector,
        student_model_path,
    )
except Exception:  # pragma: no cover
    STUDENT_MODEL_VERSION = "TurboThinker Student unavailable"
    STUDENT_OUTPUT_LABELS = []
    train_multilabel_student = None
    rows_from_seed_bank = None
    rows_from_corrections = None
    save_student_model = None
    load_student_model = None
    student_model_summary = None
    predict_student_vector = None
    student_model_path = None

try:  # v5.0 local ensemble recognition brain (no API, no external service)
    from turbothinker_ultrabrain import (
        ULTRABRAIN_VERSION,
        PRIMARY_OUTPUT_LABELS as ULTRABRAIN_OUTPUT_LABELS,
        train_ultrabrain_model as _train_ultrabrain_model,
        load_ultrabrain_model,
        ultrabrain_summary,
        predict_ultrabrain_vector,
        model_path as ultrabrain_model_path,
        normalize_tag as ultrabrain_normalize_tag,
    )
except Exception:  # pragma: no cover
    ULTRABRAIN_VERSION = "TurboThinker UltraBrain unavailable"
    ULTRABRAIN_OUTPUT_LABELS = []
    _train_ultrabrain_model = None
    load_ultrabrain_model = None
    ultrabrain_summary = None
    predict_ultrabrain_vector = None
    ultrabrain_model_path = None
    ultrabrain_normalize_tag = None

try:  # v5.3.1 24MB brain-part cortex + clean teacher GUI support
    from turbothinker_superbrain import (
        SUPERBRAIN_VERSION,
        train_superbrain_model as _train_superbrain_model,
        load_superbrain_model,
        superbrain_summary,
        predict_superbrain_vector,
        model_path as superbrain_model_path,
    )
except Exception:  # pragma: no cover
    SUPERBRAIN_VERSION = "TurboThinker SuperBrain unavailable"
    _train_superbrain_model = None
    load_superbrain_model = None
    superbrain_summary = None
    predict_superbrain_vector = None
    superbrain_model_path = None

IMGS_TRAINING_VERSION = "IMGS BetaV1 + TurboThinker SuperBrain Local Recognition Engine v5.3.1"
TURBOTHINKER_ENGINE_VERSION = "TurboThinker v5.3.1 • 24MB brain-part SuperBrain + clean GUI + teacher correction loop"
IMGS_TRAINING_TAG = "IMGS Engine"
TURBOTHINKER_TAG = "TurboThinker Engine"
IMGS_TRAINING_WARNING = (
    "IMGS BetaV1 / TurboThinker is local and experimental. Auto tags may not be accurate yet; "
    "please review, correct, and resync before trusting sorted library folders."
)

# Keep labels short and folder-safe. These become search groups and folder types.
IMGS_LABELS: List[str] = [
    "front_neck",
    "back_neck",
    "boat_neck",
    "pot_neck",
    "cut_work",
    "net_design",
    "heavy_work",
    "all_over_design",
    "short_hand",
    "full_hand",
    "butti",
    "border",
    "rangoli_design",
    "back_drop_neck",
    "stitched_photo_reference",
    "multi_design_preview",
    "unknown_review",
]


# Category tags gathered from Anne Creations HB category/design pages and used as optional local training tags.
# These are tags, not forced primary labels. Users can add/correct them in the Training Center.
ANNE_CATEGORY_TAGS: List[str] = [
    "3D Emboss",
    "Allover Blouses",
    "Animals n Birds",
    "Back Drop Designs",
    "Belts",
    "Birds",
    "Blouse Necks",
    "Boat Necks",
    "BRIDAL",
    "Bunches n Buties",
    "Butterfly,Features,Leafs",
    "Chain stitch",
    "Collar, Coat Neck",
    "Creative Designs N Gods",
    "Creative Pattern blouses",
    "Cross n Checks Hand",
    "Cross Stitch",
    "Cutwork",
    "Different Front blouses",
    "Double Shoulder neck designs",
    "Elephant",
    "Figures",
    "Flowers",
    "Free Designs",
    "Hand lines",
    "Handlines for blouses",
    "Jewels Instruments",
    "Kids Necks",
    "Kurties,Dress",
    "Kutch Work",
    "Latkans",
    "Lotus , Roses",
    "Mango",
    "Mirror Designs",
    "Net Designs",
    "One Side Designs",
    "Painting with Embroidery",
    "Peacock,Parrot",
    "Pineapple, Circle Hands",
    "Pot Necks",
    "RANGOLI",
    "Saree Pallus",
    "Simple Designs",
    "V Neck Designs",
]

ANNE_CATEGORY_TAG_SLUGS: Dict[str, str] = {
    "3D Emboss": "3d_emboss",
    "Allover Blouses": "allover_blouses",
    "Animals n Birds": "animals_birds",
    "Back Drop Designs": "back_drop_designs",
    "Belts": "belts",
    "Birds": "birds",
    "Blouse Necks": "blouse_necks",
    "Boat Necks": "boat_necks",
    "BRIDAL": "bridal",
    "Bunches n Buties": "bunches_butties",
    "Butterfly,Features,Leafs": "butterfly_features_leafs",
    "Chain stitch": "chain_stitch",
    "Collar, Coat Neck": "collar_coat_neck",
    "Creative Designs N Gods": "creative_designs_gods",
    "Creative Pattern blouses": "creative_pattern_blouses",
    "Cross n Checks Hand": "cross_checks_hand",
    "Cross Stitch": "cross_stitch",
    "Cutwork": "cutwork",
    "Different Front blouses": "different_front_blouses",
    "Double Shoulder neck designs": "double_shoulder_neck_designs",
    "Elephant": "elephant",
    "Figures": "figures",
    "Flowers": "flowers",
    "Free Designs": "free_designs",
    "Hand lines": "hand_lines",
    "Handlines for blouses": "handlines_for_blouses",
    "Jewels Instruments": "jewels_instruments",
    "Kids Necks": "kids_necks",
    "Kurties,Dress": "kurties_dress",
    "Kutch Work": "kutch_work",
    "Latkans": "latkans",
    "Lotus , Roses": "lotus_roses",
    "Mango": "mango",
    "Mirror Designs": "mirror_designs",
    "Net Designs": "net_designs",
    "One Side Designs": "one_side_designs",
    "Painting with Embroidery": "painting_with_embroidery",
    "Peacock,Parrot": "peacock_parrot",
    "Pineapple, Circle Hands": "pineapple_circle_hands",
    "Pot Necks": "pot_necks",
    "RANGOLI": "rangoli",
    "Saree Pallus": "saree_pallus",
    "Simple Designs": "simple_designs",
    "V Neck Designs": "v_neck_designs",
}

VISUAL_TAGS: List[str] = [
    "multi_design_preview", "front_neck", "back_neck", "boat_neck", "boat_neck_style",
    "pot_neck", "cut_work", "cutwork", "net_work", "net_designs", "heavy_work",
    "all_over_design", "short_hand", "full_hand", "hand_design", "sleeve_panel",
    "butti", "border", "flower_border", "flowers", "stitched_photo_reference",
    "blouse_back", "blouse_front", "rangoli_design", "back_drop_neck",
    "one_side_design", "heavy_outline", "triangle_arc", "semi_arc", "unknown_review",
]

TAG_CATALOG: Dict[str, Any] = {
    "version": "v5.0",
    "primary_labels": IMGS_LABELS,
    "anne_category_tags": ANNE_CATEGORY_TAG_SLUGS,
    "visual_tags": VISUAL_TAGS,
}


def normalize_tag(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text in ANNE_CATEGORY_TAG_SLUGS:
        return ANNE_CATEGORY_TAG_SLUGS[text]
    cleaned = "_".join("".join(ch.lower() if ch.isalnum() else " " for ch in text).split())
    aliases = {
        "net_design": "net_work",
        "net_designs": "net_work",
        "boat_necks": "boat_neck",
        "pot_necks": "pot_neck",
        "cutwork": "cut_work",
        "allover_blouses": "allover_blouses",
        "one_side_designs": "one_side_design",
        "back_drop_designs": "back_drop_neck",
        "saree_pallus": "saree_pallus",
    }
    return aliases.get(cleaned, cleaned)


def ordered_unique_tags(tags: Iterable[str], *, scores: Optional[Dict[str, float]] = None, primary: str = "", image_mode: str = "", manual_tags: Optional[Iterable[str]] = None, limit: int = 18, keep_engine_tags: bool = True) -> List[str]:
    scores = scores or {}
    manual_set = {normalize_tag(t) for t in (manual_tags or []) if normalize_tag(t)}
    raw = [normalize_tag(t) for t in tags if normalize_tag(t)]
    engine = [t for t in raw if t in {normalize_tag(IMGS_TRAINING_TAG), normalize_tag(TURBOTHINKER_TAG)} or t in {IMGS_TRAINING_TAG, TURBOTHINKER_TAG}]
    raw = [t for t in raw if t not in engine and t not in {normalize_tag(IMGS_TRAINING_TAG), normalize_tag(TURBOTHINKER_TAG)}]
    must_multi = image_mode == "multi_design_preview" or "multi_design_preview" in raw or normalize_tag(primary) == "multi_design_preview"
    order: List[str] = []
    if must_multi:
        order.append("multi_design_preview")
    p = normalize_tag(primary)
    if p and p != "unknown_review" and p not in order:
        order.append(p)
    priority = [
        "heavy_work", "all_over_design", "back_neck", "front_neck", "boat_neck", "pot_neck",
        "full_hand", "short_hand", "hand_design", "sleeve_panel", "cut_work", "net_work",
        "flower_border", "flowers", "butti", "border", "mango", "lotus_roses",
        "peacock_parrot", "mirror_designs", "stitched_photo_reference", "one_side_design",
    ]
    for t in priority:
        if t in raw and t not in order:
            order.append(t)
    # Add high-score primary label tags next, then the remaining visual/category tags.
    for t, _score in sorted(scores.items(), key=lambda kv: float(kv[1]), reverse=True):
        nt = normalize_tag(t)
        if nt and nt != "unknown_review" and nt not in order and (float(_score) >= 0.24 or nt in manual_set):
            order.append(nt)
    for t in raw:
        if t not in order:
            order.append(t)
    for t in manual_set:
        if t not in order:
            order.append(t)
    if not order:
        order.append("unknown_review")
    if keep_engine_tags:
        order.extend([IMGS_TRAINING_TAG, TURBOTHINKER_TAG])
    out: List[str] = []
    seen = set()
    for t in order:
        if t and t not in seen:
            out.append(t)
            seen.add(t)
    return out[:limit]

SEARCH_GROUPS: Dict[str, List[str]] = {
    "front_neck": ["front_neck", "back_neck", "boat_neck", "pot_neck"],
    "back_neck": ["back_neck", "boat_neck", "back_drop_neck", "front_neck"],
    "boat_neck": ["boat_neck", "back_neck", "front_neck"],
    "pot_neck": ["pot_neck", "front_neck", "back_neck", "net_design"],
    "cut_work": ["cut_work", "border", "back_neck", "front_neck"],
    "net_design": ["net_design", "pot_neck", "heavy_work", "all_over_design"],
    "heavy_work": ["heavy_work", "all_over_design", "back_neck", "front_neck", "full_hand"],
    "all_over_design": ["all_over_design", "heavy_work", "butti", "full_hand"],
    "short_hand": ["short_hand", "full_hand", "border"],
    "full_hand": ["full_hand", "short_hand", "border", "heavy_work"],
    "butti": ["butti", "all_over_design", "rangoli_design"],
    "border": ["border", "short_hand", "full_hand", "cut_work"],
    "rangoli_design": ["rangoli_design", "butti", "all_over_design"],
    "back_drop_neck": ["back_drop_neck", "back_neck", "boat_neck"],
    "stitched_photo_reference": ["back_neck", "front_neck", "short_hand", "full_hand", "heavy_work"],
    "multi_design_preview": ["back_neck", "front_neck", "short_hand", "full_hand", "heavy_work", "all_over_design"],
    "unknown_review": IMGS_LABELS[:-1],
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def training_root(app_root: Path) -> Path:
    return Path(app_root) / "imgs_training"


def ensure_training_dirs(app_root: Path) -> Dict[str, Path]:
    root = training_root(app_root)
    paths = {
        "root": root,
        "samples": root / "samples",
        "crops": root / "crops",
        "design_json": root / "design_json",
        "fingerprints": root / "fingerprints",
        "indexes": root / "indexes",
        "review": root / "unknown_review",
        "type_folders": root / "type_folders",
        "turbothinker": root / "turbothinker",
        "seed_training": root / "seed_training",
        "models": root / "models",
        "prototypes": root / "prototypes",
    }
    for p in paths.values():
        p.mkdir(parents=True, exist_ok=True)
    return paths


def _read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_training_index(app_root: Path) -> Dict[str, Any]:
    return _read_json(training_root(app_root) / "imgs_index.json", {"version": IMGS_TRAINING_VERSION, "by_type": {}, "items": {}})


def save_training_index(app_root: Path, data: Dict[str, Any]) -> None:
    data["version"] = IMGS_TRAINING_VERSION
    data["updated_at"] = utc_now()
    _write_json(training_root(app_root) / "imgs_index.json", data)


def load_corrections(app_root: Path) -> Dict[str, Any]:
    return _read_json(training_root(app_root) / "corrections.json", {"version": IMGS_TRAINING_VERSION, "samples": []})


def save_corrections(app_root: Path, data: Dict[str, Any]) -> None:
    data["version"] = IMGS_TRAINING_VERSION
    data["updated_at"] = utc_now()
    _write_json(training_root(app_root) / "corrections.json", data)


def _to_rgb(img: Image.Image) -> Image.Image:
    if img.mode in ("RGBA", "LA"):
        bg = Image.new("RGB", img.size, "white")
        rgba = img.convert("RGBA")
        bg.paste(rgba, mask=rgba.split()[-1])
        return bg
    return img.convert("RGB")



def _estimate_background_rgb(img: Image.Image) -> Tuple[float, float, float]:
    """Estimate screenshot/preview background from corners and edge samples."""
    rgb = _to_rgb(img)
    w, h = rgb.size
    sample = max(4, min(w, h) // 12)
    boxes = [
        (0, 0, sample, sample),
        (max(0, w - sample), 0, w, sample),
        (0, max(0, h - sample), sample, h),
        (max(0, w - sample), max(0, h - sample), w, h),
    ]
    vals: List[Tuple[int, int, int]] = []
    for box in boxes:
        crop = rgb.crop(box).resize((8, 8), Image.Resampling.BILINEAR)
        vals.extend(list(crop.getdata()))
    if not vals:
        return (255.0, 255.0, 255.0)
    vals_sorted = sorted(vals, key=lambda c: c[0] + c[1] + c[2])
    # Use median corner color: works for black, white, and plain color backgrounds.
    r, g, b = vals_sorted[len(vals_sorted) // 2]
    return float(r), float(g), float(b)


def _pixel_foreground_score(r: int, g: int, b: int, bg: Tuple[float, float, float]) -> float:
    br, bgc, bb = bg
    dist = math.sqrt((r - br) ** 2 + (g - bgc) ** 2 + (b - bb) ** 2)
    spread = max(r, g, b) - min(r, g, b)
    lum = (r * 0.299) + (g * 2487) + (b * 0.114)
    bg_lum = (br * 0.299) + (bgc * 2487) + (bb * 0.114)
    # Distance from the estimated background is the main signal.
    score = dist / 255.0
    # Colorful thread on dark/white background gets a boost.
    if spread > 30 and dist > 20:
        score += min(0.25, spread / 510.0)
    # Dark stitches on light background.
    if bg_lum > 190 and lum < bg_lum - 28:
        score += 0.25
    # Light stitches on black background.
    if bg_lum < 65 and lum > bg_lum + 35:
        score += 0.25
    return max(0.0, min(1.0, score))


def _background_bbox(img: Image.Image) -> Optional[Tuple[int, int, int, int]]:
    """Find design-ish pixels while treating black/white/plain preview backgrounds as background."""
    img = _to_rgb(img)
    w, h = img.size
    if w < 4 or h < 4:
        return None
    max_scan = 640
    scale = min(1.0, max_scan / max(w, h))
    small = img.resize((max(2, int(w * scale)), max(2, int(h * scale))), Image.Resampling.BILINEAR) if scale < 1.0 else img
    sw, sh = small.size
    bg = _estimate_background_rgb(small)
    pix = small.load()
    xs: List[int] = []
    ys: List[int] = []
    for y in range(sh):
        for x in range(sw):
            r, g, b = pix[x, y]
            if _pixel_foreground_score(r, g, b, bg) > 0.18:
                xs.append(x)
                ys.append(y)
    if not xs or not ys:
        return None
    inv = 1.0 / scale
    pad = max(6, int(min(w, h) * 0.035))
    left = max(0, int(min(xs) * inv) - pad)
    top = max(0, int(min(ys) * inv) - pad)
    right = min(w, int((max(xs) + 1) * inv) + pad)
    bottom = min(h, int((max(ys) + 1) * inv) + pad)
    if right <= left or bottom <= top:
        return None
    return left, top, right, bottom

def _resize_for_fast_analysis(img: Image.Image, max_side: int) -> Image.Image:
    """Shrink large previews before pixel-level work; keeps 300+ ZIP training fast."""
    rgb = _to_rgb(img)
    w, h = rgb.size
    if max(w, h) <= max_side:
        return rgb
    scale = max_side / float(max(w, h))
    return rgb.resize((max(2, int(w * scale)), max(2, int(h * scale))), Image.Resampling.BILINEAR)


def _looks_like_center_watermark_pixel(r: int, g: int, b: int) -> bool:
    """Softly ignore pale preview title/watermark strokes without reading filenames."""
    lum = (r * 0.299) + (g * 2487) + (b * 0.114)
    spread = max(r, g, b) - min(r, g, b)
    # Most HB/sample watermarks are pale green/white/pink text over a dark background.
    pale = lum > 112 and spread < 118
    greenish = g >= max(r, b) * 0.82
    pinkish = r >= g * 0.82 and b >= g * 0.62
    whitish = spread < 42 and lum > 135
    return bool(pale and (greenish or pinkish or whitish))


def clean_preview_image(img: Image.Image, size: int = 384) -> Image.Image:
    # The older v4.8.1 cleaner scanned every original pixel. This v4.8.2 path
    # downsamples first, making 300+ training files practical while still keeping
    # enough visual structure for embroidery type tags.
    work = _resize_for_fast_analysis(img, max(320, size * 3))
    original_bg = _estimate_background_rgb(work)
    bbox = _background_bbox(work)
    if bbox:
        work = work.crop(bbox)
    bg = original_bg
    ww, hh = work.size
    center_y0 = int(hh * 0.34)
    center_y1 = int(hh * 0.67)
    center_x0 = int(ww * 0.18)
    center_x1 = int(ww * 0.82)
    pixels = []
    for idx, (r, g, b) in enumerate(work.getdata()):
        y, x = divmod(idx, ww)
        fg = _pixel_foreground_score(int(r), int(g), int(b), bg)
        # Ignore obvious pale center watermark/title text. This never uses the
        # filename; it only suppresses visual text-like overlay pixels.
        if center_x0 <= x <= center_x1 and center_y0 <= y <= center_y1 and _looks_like_center_watermark_pixel(int(r), int(g), int(b)):
            fg *= 0.30
        if fg <= 0.18:
            pixels.append((255, 255, 255))
        else:
            pixels.append((int(r), int(g), int(b)))
    cleaned = Image.new("RGB", work.size, "white")
    cleaned.putdata(pixels)
    canvas = Image.new("RGB", (size, size), "white")
    margin = max(8, int(size * 0.05))
    cleaned.thumbnail((size - margin * 2, size - margin * 2), Image.Resampling.LANCZOS)
    canvas.paste(cleaned, ((size - cleaned.width) // 2, (size - cleaned.height) // 2))
    return canvas


def _binary_mask_values(img: Image.Image, size: int = 96) -> Tuple[List[float], int, int]:
    small = clean_preview_image(img, size=size)
    bg = _estimate_background_rgb(small)
    pix = list(small.getdata())
    vals = []
    for r, g, b in pix:
        v = _pixel_foreground_score(int(r), int(g), int(b), bg)
        vals.append(v if v > 0.16 else 0.0)
    return vals, size, size

def _grid_density(vals: List[float], w: int, h: int, gx: int, gy: int) -> List[float]:
    out: List[float] = []
    for yy in range(gy):
        y0 = int(yy * h / gy)
        y1 = int((yy + 1) * h / gy)
        for xx in range(gx):
            x0 = int(xx * w / gx)
            x1 = int((xx + 1) * w / gx)
            s = 0.0
            n = 0
            for y in range(y0, max(y0 + 1, y1)):
                base = y * w
                for x in range(x0, max(x0 + 1, x1)):
                    s += vals[base + x]
                    n += 1
            out.append(round(s / max(1, n), 6))
    return out


def _component_count(vals: List[float], w: int, h: int, threshold: float = 0.08) -> int:
    # Very small connected-component count on 64/96 image; enough to detect scattered butties.
    seen = bytearray(w * h)
    count = 0
    for i, v in enumerate(vals):
        if v <= threshold or seen[i]:
            continue
        count += 1
        stack = [i]
        seen[i] = 1
        while stack:
            p = stack.pop()
            y, x = divmod(p, w)
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if 0 <= nx < w and 0 <= ny < h:
                    ni = ny * w + nx
                    if not seen[ni] and vals[ni] > threshold:
                        seen[ni] = 1
                        stack.append(ni)
    return count


def _edge_strength(img: Image.Image, size: int = 128) -> float:
    gray = ImageOps.grayscale(clean_preview_image(img, size=size))
    edges = gray.filter(ImageFilter.FIND_EDGES)
    stat = ImageStat.Stat(edges)
    return round(float(stat.mean[0]) / 255.0, 6)


def _line_profiles(vals: List[float], w: int, h: int) -> Tuple[List[float], List[float]]:
    rows: List[float] = []
    cols: List[float] = []
    for y in range(h):
        rows.append(sum(vals[y * w + x] for x in range(w)) / max(1, w))
    for x in range(w):
        cols.append(sum(vals[y * w + x] for y in range(h)) / max(1, h))
    return rows, cols


def extract_visual_features(img: Image.Image) -> Dict[str, Any]:
    rgb = _to_rgb(img)
    w0, h0 = rgb.size
    bbox = _background_bbox(rgb)
    bbox_ratio = None
    if bbox:
        bw = max(1, bbox[2] - bbox[0])
        bh = max(1, bbox[3] - bbox[1])
        bbox_ratio = bw / max(1, bh)
    vals, w, h = _binary_mask_values(rgb, size=96)
    mass = sum(vals)
    density = mass / max(1, w * h)
    xs: List[int] = []
    ys: List[int] = []
    for i, v in enumerate(vals):
        if v > 0.08:
            y, x = divmod(i, w)
            xs.append(x)
            ys.append(y)
    if xs and ys:
        minx, maxx = min(xs), max(xs)
        miny, maxy = min(ys), max(ys)
        ink_w = max(1, maxx - minx + 1)
        ink_h = max(1, maxy - miny + 1)
        cx = sum(x * vals[y * w + x] for x, y in zip(xs, ys)) / max(1e-6, sum(vals[y * w + x] for x, y in zip(xs, ys)))
        cy = sum(y * vals[y * w + x] for x, y in zip(xs, ys)) / max(1e-6, sum(vals[y * w + x] for x, y in zip(xs, ys)))
    else:
        minx = miny = maxx = maxy = 0
        ink_w = ink_h = 1
        cx = cy = 48.0
    # Symmetry: lower value is more symmetric.
    hdiff = 0.0
    vdiff = 0.0
    for y in range(h):
        for x in range(w // 2):
            hdiff += abs(vals[y * w + x] - vals[y * w + (w - 1 - x)])
    for y in range(h // 2):
        for x in range(w):
            vdiff += abs(vals[y * w + x] - vals[(h - 1 - y) * w + x])
    hsym = 1.0 - min(1.0, hdiff / max(1.0, mass * 1.4))
    vsym = 1.0 - min(1.0, vdiff / max(1.0, mass * 1.4))
    rows, cols = _line_profiles(vals, w, h)
    top = sum(rows[: h // 3]) / max(1, h // 3)
    mid = sum(rows[h // 3 : 2 * h // 3]) / max(1, h // 3)
    bottom = sum(rows[2 * h // 3 :]) / max(1, h - 2 * h // 3)
    left = sum(cols[: w // 3]) / max(1, w // 3)
    center = sum(cols[w // 3 : 2 * w // 3]) / max(1, w // 3)
    right = sum(cols[2 * w // 3 :]) / max(1, w - 2 * w // 3)
    component_count = _component_count(vals, w, h)
    edge = _edge_strength(rgb, 128)
    grid4 = _grid_density(vals, w, h, 4, 4)
    grid8 = _grid_density(vals, w, h, 8, 8)

    aspect = ink_w / max(1, ink_h)
    original_aspect = w0 / max(1, h0)
    coverage = (ink_w * ink_h) / max(1, w * h)
    # Simple net hint: many alternating row/column peaks and high edge compared with mass.
    row_peaks = sum(1 for v in rows if v > density * 1.45 and v > 0.035)
    col_peaks = sum(1 for v in cols if v > density * 1.45 and v > 0.035)
    net_score = min(1.0, ((row_peaks + col_peaks) / 30.0) * 245 + max(0.0, edge - density) * 1.8)
    scattered_score = min(1.0, component_count / 26.0)
    density_name = "light"
    if density > 0.19:
        density_name = "heavy"
    elif density > 0.105:
        density_name = "medium"

    # TurboThinker rough part-count estimate. This is intentionally cautious:
    # it helps collage previews enter multi-design mode without forcing a bad
    # single label. The user correction loop remains the final teacher.
    region_estimate = 1
    if component_count >= 42 or (original_aspect > 1.45 and coverage > 0.28):
        region_estimate = 5
    elif component_count >= 28 or (original_aspect > 1.25 and coverage > 0.22):
        region_estimate = 4
    elif component_count >= 16 and scattered_score > 0.34:
        region_estimate = 3
    layout_complexity = min(1.0, (component_count / 60.0) * 245 + scattered_score * 0.25 + net_score * 0.20)

    return {
        "source_size": [w0, h0],
        "bbox": list(bbox) if bbox else None,
        "bbox_aspect": round(float(bbox_ratio), 4) if bbox_ratio else None,
        "ink_density": round(float(density), 6),
        "density_name": density_name,
        "ink_coverage": round(float(coverage), 6),
        "aspect": round(float(aspect), 4),
        "original_aspect": round(float(original_aspect), 4),
        "centroid": [round(cx / max(1, w - 1), 4), round(cy / max(1, h - 1), 4)],
        "horizontal_symmetry": round(float(hsym), 4),
        "vertical_symmetry": round(float(vsym), 4),
        "edge_strength": round(float(edge), 6),
        "component_count": int(component_count),
        "estimated_region_count": int(region_estimate),
        "layout_complexity": round(float(layout_complexity), 4),
        "net_score": round(float(net_score), 4),
        "scattered_score": round(float(scattered_score), 4),
        "zone_density": {
            "top": round(float(top), 6),
            "middle": round(float(mid), 6),
            "bottom": round(float(bottom), 6),
            "left": round(float(left), 6),
            "center": round(float(center), 6),
            "right": round(float(right), 6),
        },
        "grid4": grid4,
        "grid8": grid8,
    }


def _score_labels(features: Dict[str, Any]) -> Dict[str, float]:
    density = float(features.get("ink_density") or 0.0)
    aspect = float(features.get("aspect") or 1.0)
    original_aspect = float(features.get("original_aspect") or 1.0)
    coverage = float(features.get("ink_coverage") or 0.0)
    hsym = float(features.get("horizontal_symmetry") or 0.0)
    vsym = float(features.get("vertical_symmetry") or 0.0)
    net = float(features.get("net_score") or 0.0)
    scattered = float(features.get("scattered_score") or 0.0)
    comps = int(features.get("component_count") or 0)
    estimated_regions = int(features.get("estimated_region_count") or 1)
    layout_complexity = float(features.get("layout_complexity") or 0.0)
    edge = float(features.get("edge_strength") or 0.0)
    z = features.get("zone_density") or {}
    top, mid, bottom = float(z.get("top") or 0), float(z.get("middle") or 0), float(z.get("bottom") or 0)
    left, center, right = float(z.get("left") or 0), float(z.get("center") or 0), float(z.get("right") or 0)
    centroid = features.get("centroid") or [24, 24]
    cy = float(centroid[1]) if len(centroid) > 1 else 24

    scores = {label: 0.05 for label in IMGS_LABELS}

    # Global/collage/photo hints.
    if estimated_regions >= 4 or (original_aspect > 1.45 and coverage > 0.35 and comps > 10):
        scores["multi_design_preview"] += 242
        scores["heavy_work"] += 0.10
    if density > 0.18 or (density > 0.13 and comps > 12) or layout_complexity > 248:
        scores["heavy_work"] += 0.42
        scores["all_over_design"] += 0.25
    if scattered > 0.38 and density < 0.20:
        scores["butti"] += 0.34
        scores["all_over_design"] += 0.18
    if hsym > 0.64 and vsym > 0.48 and aspect < 1.35 and scattered < 245:
        scores["rangoli_design"] += 0.32

    # Net/cut hints.
    if net > 0.35:
        # Net-like line detection can fire on clean stitch-tooth borders. Give
        # true net work a strong score, but soften it for narrow partial-neck
        # previews where the visual sign is mostly a side corner border.
        net_bonus = 0.45
        if aspect < 0.82 and coverage < 245:
            net_bonus = 0.18
            scores["front_neck"] += 0.18
        scores["net_design"] += net_bonus
        if density > 0.12 and aspect >= 0.82:
            scores["heavy_work"] += 0.12
    if edge > density * 1.55 and 0.045 < density < 0.17 and coverage > 0.20:
        scores["cut_work"] += 0.34
    if edge > 0.11 and density < 0.11:
        scores["cut_work"] += 0.18

    # Shape/placement hints.
    if aspect > 2.2:
        scores["border"] += 0.45
        scores["short_hand"] += 0.22
        if net > 0.22:
            scores["full_hand"] += 0.14
    elif aspect > 1.35:
        scores["boat_neck"] += 0.30
        scores["border"] += 0.18
        if density > 0.12:
            scores["back_neck"] += 0.14
    elif aspect < 245:
        scores["full_hand"] += 0.38
        scores["short_hand"] += 0.22
    elif aspect < 0.82:
        scores["front_neck"] += 0.34
        scores["back_neck"] += 0.20
        # A tall narrow shape can be sleeve/full-hand, but if coverage is low
        # and it has a curved corner, keep front neck ahead for Type-1 previews.
        scores["full_hand"] += 0.10 if coverage < 240 else 0.15

    # U/neck-ish distribution: ink on sides/bottom with center opening.
    side_bias = max(0.0, ((left + right) / 2.0) - center)
    bottom_bias = max(0.0, bottom - mid * 0.75)
    top_open_hint = max(0.0, mid - top * 0.75)
    if side_bias > 0.012 and bottom_bias > 0.008:
        scores["back_neck"] += 0.36
        scores["front_neck"] += 0.22
        if aspect > 1.1:
            scores["boat_neck"] += 0.16
    if top_open_hint > 0.012 and cy > 0.48:
        scores["front_neck"] += 0.22
        scores["pot_neck"] += 0.12
    if aspect > 1.1 and aspect < 2.2 and side_bias > 0.006 and hsym > 0.45:
        scores["boat_neck"] += 0.28
    if aspect > 0.75 and aspect < 1.35 and net > 0.25 and density > 0.08:
        scores["pot_neck"] += 0.25

    # Back drop/open neck style often has lower density and a large central opening.
    if coverage > 0.25 and center < (left + right) / 2.4 and density < 0.16:
        scores["back_drop_neck"] += 0.22

    # Hand/sleeve panels often have repeated scattered components in a long shape.
    if (aspect > 1.55 or aspect < 0.75) and comps > 8:
        scores["short_hand"] += 0.18
        scores["full_hand"] += 0.20
    if density > 0.13 and (aspect < 0.8 or aspect > 1.8):
        scores["full_hand"] += 0.10 if comps < 10 else 0.18

    # Stitched/photo reference: high texture spread/collage-like images. Hard to detect with PIL only.
    if density > 0.22 and edge > 0.16 and coverage > 240:
        scores["stitched_photo_reference"] += 0.16

    return {k: round(max(0.0, min(1.0, v)), 4) for k, v in scores.items()}


def classify_features(features: Dict[str, Any]) -> Dict[str, Any]:
    scores = _score_labels(features)
    sorted_scores = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    best_label, best_score = sorted_scores[0]
    # Conservative fallback: do not over-confidently sort weak guesses.
    if best_score < 0.28:
        best_label = "unknown_review"
    confidence = int(round(min(0.96, max(0.15, best_score)) * 100)) if best_label != "unknown_review" else int(round(best_score * 100))
    secondary = [label for label, score in sorted_scores[1:6] if score >= 0.24 and label != best_label]
    tags = _tags_from_features(features, best_label, secondary)
    return {
        "predicted_type": best_label,
        "confidence": confidence,
        "secondary_types": secondary,
        "scores": scores,
        "tags": tags,
        "search_groups": candidate_search_groups(best_label, secondary),
    }


def _tags_from_features(features: Dict[str, Any], primary: str, secondary: List[str]) -> List[str]:
    # User requirement: for collage/mixed images, multi_design_preview must be
    # the first tag. Tags are ordered as: multi-preview → work/style → parts →
    # motifs → references → engine tags.
    scores = _score_labels(features)
    estimated_regions = int(features.get("estimated_region_count") or 1)
    image_mode = "multi_design_preview" if (primary == "multi_design_preview" or estimated_regions >= 4) else "single_design"
    tags: List[str] = []
    if image_mode == "multi_design_preview":
        tags.append("multi_design_preview")
    if primary:
        tags.append(primary)
    tags.extend(secondary[:8])
    density_name = str(features.get("density_name") or "")
    if density_name == "heavy":
        tags.append("heavy_work")
    elif density_name == "medium":
        tags.append("density_medium")
    if float(features.get("ink_coverage") or 0.0) > 0.34:
        tags.append("all_over_design")
    if float(features.get("net_score") or 0.0) > 0.35:
        tags.extend(["net_work", "net_designs"])
    if float(features.get("scattered_score") or 0.0) > 0.38:
        tags.extend(["butti", "flowers"])
    if float(features.get("edge_strength") or 0.0) > 0.12:
        tags.extend(["cut_work", "heavy_outline"])
    aspect = float(features.get("aspect") or 1.0)
    if aspect > 1.8:
        tags.extend(["border", "hand_lines", "wide_horizontal"])
    elif aspect < 0.75:
        tags.extend(["full_hand", "hand_design", "tall_vertical"])
    if float(features.get("horizontal_symmetry") or 0.0) > 0.62:
        tags.append("symmetrical")
    if estimated_regions >= 4:
        tags.append("multi_part_possible")
    tags.extend([IMGS_TRAINING_TAG, TURBOTHINKER_TAG])
    return ordered_unique_tags(tags, scores=scores, primary=primary, image_mode=image_mode, limit=14, keep_engine_tags=True)


def prune_prediction_tags(prediction: Dict[str, Any], min_score: float = 0.24, keep_engine_tags: bool = True) -> Dict[str, Any]:
    """Remove weak leftover type tags while keeping the best useful tags.

    Manual/user tags are preserved by record_training_correction after this pass.
    The multi_design_preview first-tag lock is always respected.
    """
    pred = dict(prediction or {})
    scores = {str(k): float(v) for k, v in (pred.get("scores") or {}).items()}
    tags = [normalize_tag(t) for t in list(pred.get("tags") or []) if normalize_tag(t)]
    primary = str(pred.get("predicted_type") or "unknown_review")
    image_mode = str(pred.get("image_mode") or ("multi_design_preview" if "multi_design_preview" in tags else ""))
    kept: List[str] = []
    for t in tags:
        if t in {normalize_tag(IMGS_TRAINING_TAG), normalize_tag(TURBOTHINKER_TAG)}:
            continue
        if t in [normalize_tag(x) for x in IMGS_LABELS] and normalize_tag(t) != normalize_tag(primary) and scores.get(t, scores.get(str(t), 0.0)) < float(min_score):
            continue
        kept.append(t)
    pred["tags"] = ordered_unique_tags(kept, scores=scores, primary=primary, image_mode=image_mode, limit=14, keep_engine_tags=keep_engine_tags)
    pred["auto_removed_low_score_tags"] = True
    pred["tag_min_score"] = float(min_score)
    return pred


def add_manual_tags(prediction: Dict[str, Any], manual_tags: Iterable[str]) -> Dict[str, Any]:
    pred = dict(prediction or {})
    tags = list(pred.get("tags") or [])
    manual_clean: List[str] = []
    for tag in manual_tags or []:
        nt = normalize_tag(str(tag).strip())
        if nt:
            manual_clean.append(nt)
    tags.extend(manual_clean)
    pred["tags"] = ordered_unique_tags(
        tags,
        scores=pred.get("scores") or {},
        primary=str(pred.get("predicted_type") or ""),
        image_mode=str(pred.get("image_mode") or ("multi_design_preview" if "multi_design_preview" in tags else "")),
        manual_tags=manual_clean,
        limit=24,
        keep_engine_tags=True,
    )
    return pred


def explain_prediction(features: Dict[str, Any], prediction: Dict[str, Any], turbothinker: Optional[Dict[str, Any]] = None) -> List[str]:
    """Human-readable local reasons for the Training Center."""
    pred_type = str((prediction or {}).get("predicted_type") or "unknown_review")
    density = float(features.get("ink_density") or 0.0)
    coverage = float(features.get("ink_coverage") or 0.0)
    aspect = float(features.get("aspect") or 1.0)
    original_aspect = float(features.get("original_aspect") or 1.0)
    net = float(features.get("net_score") or 0.0)
    scattered = float(features.get("scattered_score") or 0.0)
    comps = int(features.get("component_count") or 0)
    edge = float(features.get("edge_strength") or 0.0)
    regions = int(features.get("estimated_region_count") or 1)
    hsym = float(features.get("horizontal_symmetry") or 0.0)
    reasons: List[str] = []
    reasons.append(f"Prediction `{pred_type}` came from local visual features only, not filename/title.")
    if pred_type == "multi_design_preview" or regions >= 4:
        reasons.append(f"Multi-preview hint: the image has about {regions} active design regions and wide/complex layout, so the first tag is `multi_design_preview`.")
    if density > 0.18:
        reasons.append(f"Heavy-work hint: foreground stitch density is high ({density:.3f}).")
    elif density < 0.075:
        reasons.append(f"Light-work hint: foreground stitch density is low ({density:.3f}); weak leftover tags can be auto-removed.")
    if coverage > 0.34:
        reasons.append(f"Large coverage hint: embroidery covers a broad area ({coverage:.2f}), useful for all-over/heavy designs.")
    if net > 0.35:
        reasons.append(f"Net-work hint: many repeated line peaks/edges were detected (net score {net:.2f}).")
    if scattered > 0.38 or comps > 24:
        reasons.append(f"Butti/flower hint: many separated components were found ({comps}), so flowers/butties may be present.")
    if edge > max(0.11, density * 1.45):
        reasons.append(f"Cut/border hint: edge strength is high ({edge:.2f}) compared with density.")
    if aspect > 1.6:
        reasons.append("Shape hint: the useful embroidery area is wide, so it may be border, boat neck, short hand, or panel work.")
    elif aspect < 0.75:
        reasons.append("Shape hint: the useful embroidery area is tall, so it may be front neck side, full hand, or sleeve panel.")
    if hsym > 0.62:
        reasons.append(f"Symmetry hint: left-right symmetry is strong ({hsym:.2f}), common in neck/rangoli/center designs.")
    if turbothinker:
        mode = turbothinker.get("image_mode", "single_design")
        count = turbothinker.get("unique_design_file_count") or {}
        reasons.append(f"TurboThinker mode: `{mode}`; estimated unique files {count.get('min', 1)}–{count.get('max', 1)}.")
    return reasons[:9]


def candidate_search_groups(predicted_type: str, secondary_types: Optional[Iterable[str]] = None) -> List[str]:
    groups: List[str] = []
    for label in [predicted_type, *(secondary_types or [])]:
        for g in SEARCH_GROUPS.get(str(label), [str(label)]):
            if g not in groups and g in IMGS_LABELS:
                groups.append(g)
    return groups or ["unknown_review"]


def _feature_vector(features: Dict[str, Any]) -> List[float]:
    z = features.get("zone_density") or {}
    centroid = features.get("centroid") or [24, 24]
    return [
        float(features.get("ink_density") or 0.0),
        min(3.0, float(features.get("aspect") or 1.0)) / 3.0,
        float(features.get("ink_coverage") or 0.0),
        float(features.get("net_score") or 0.0),
        float(features.get("scattered_score") or 0.0),
        float(features.get("edge_strength") or 0.0),
        min(1.0, float(features.get("estimated_region_count") or 1) / 5.0),
        float(features.get("layout_complexity") or 0.0),
        float(features.get("horizontal_symmetry") or 0.0),
        float(features.get("vertical_symmetry") or 0.0),
        min(1.0, float(features.get("component_count") or 0) / 120.0),
        float(z.get("top") or 0.0),
        float(z.get("middle") or 0.0),
        float(z.get("bottom") or 0.0),
        float(z.get("left") or 0.0),
        float(z.get("center") or 0.0),
        float(z.get("right") or 0.0),
        float(centroid[0]) if len(centroid) > 0 else 24,
        float(centroid[1]) if len(centroid) > 1 else 24,
    ]


def _vector_distance(a: List[float], b: List[float]) -> float:
    n = min(len(a), len(b))
    if n <= 0:
        return 99.0
    # Weighted Euclidean-ish distance for compact local correction memory.
    weights = [1.1, 1.0, 0.8, 1.0, 0.75, 0.7, 245, 245, 245, 24, 0.65, 24, 24, 0.65, 24, 0.45, 0.45]
    s = 0.0
    wsum = 0.0
    for i in range(n):
        wgt = weights[i] if i < len(weights) else 24
        s += ((a[i] - b[i]) ** 2) * wgt
        wsum += wgt
    return math.sqrt(s / max(1e-6, wsum))


def apply_correction_memory(app_root: Path, analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Use saved user corrections as a small local memory boost.

    This is not a trained ML model yet. It is a safe BetaV1 nearest-neighbor memory:
    similar corrected samples add score to their final label, so your corrections
    start helping future imports/resyncs immediately.
    """
    try:
        corrections = load_corrections(app_root).get("samples") or []
        if not corrections:
            return analysis
        pred = dict(analysis.get("prediction") or {})
        features = analysis.get("features") or {}
        qv = _feature_vector(features)
        scores = dict(pred.get("scores") or {})
        matches: List[Dict[str, Any]] = []
        for sample in corrections[-1500:]:  # cap memory for speed
            label = str(sample.get("final_label") or "")
            sf = sample.get("features") or {}
            if label not in IMGS_LABELS or not sf:
                continue
            dist = _vector_distance(qv, _feature_vector(sf))
            sim = max(0.0, 1.0 - (dist / 0.42))
            if sim <= 0.0:
                continue
            scores[label] = min(1.0, float(scores.get(label, 0.05)) + sim * 0.38)
            matches.append({
                "source_name": sample.get("source_name"),
                "final_label": label,
                "distance": round(dist, 5),
                "similarity": round(sim, 4),
            })
        if not matches:
            return analysis
        sorted_scores = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        best_label, best_score = sorted_scores[0]
        secondary = [label for label, score in sorted_scores[1:6] if score >= 0.24 and label != best_label]
        pred.update({
            "predicted_type": best_label if best_score >= 0.28 else "unknown_review",
            "confidence": int(round(min(0.98, max(0.15, best_score)) * 100)),
            "secondary_types": secondary,
            "scores": {k: round(float(v), 4) for k, v in scores.items()},
            "tags": _tags_from_features(features, best_label, secondary),
            "search_groups": candidate_search_groups(best_label, secondary),
            "learned_from_local_corrections": True,
            "nearest_corrections": sorted(matches, key=lambda m: m["distance"])[:5],
        })
        analysis = dict(analysis)
        analysis["prediction"] = pred
        return analysis
    except Exception:
        return analysis



def infer_turbothinker_parts(features: Dict[str, Any]) -> Dict[str, Any]:
    """Return a local, explainable multi-part reading for training screenshots.

    This is deliberately lightweight. It does not claim perfect detection; it gives
    the Training Center a better starting point: single design vs collage, minimum
    unique file count, and likely zones to review/crop/search separately.
    """
    density = float(features.get("ink_density") or 0.0)
    coverage = float(features.get("ink_coverage") or 0.0)
    aspect = float(features.get("original_aspect") or features.get("aspect") or 1.0)
    est_regions = int(features.get("estimated_region_count") or 1)
    grid8 = list(features.get("grid8") or [])
    # 3x3 zones derived from the 8x8 density grid.
    zone_boxes = {
        "top_left": (0, 0, 3, 3),
        "top_center": (3, 0, 5, 3),
        "top_right": (5, 0, 8, 3),
        "middle_left": (0, 3, 3, 5),
        "center": (3, 3, 5, 5),
        "middle_right": (5, 3, 8, 5),
        "bottom_left": (0, 5, 3, 8),
        "bottom_center": (3, 5, 5, 8),
        "bottom_right": (5, 5, 8, 8),
    }
    zone_scores: Dict[str, float] = {}
    if len(grid8) == 64:
        for name, (x0, y0, x1, y1) in zone_boxes.items():
            vals: List[float] = []
            for yy in range(y0, y1):
                for xx in range(x0, x1):
                    vals.append(float(grid8[yy * 8 + xx]))
            zone_scores[name] = round(sum(vals) / max(1, len(vals)), 6)
    else:
        z = features.get("zone_density") or {}
        zone_scores = {
            "top_center": float(z.get("top") or 0.0),
            "center": float(z.get("middle") or 0.0),
            "bottom_center": float(z.get("bottom") or 0.0),
            "middle_left": float(z.get("left") or 0.0),
            "middle_right": float(z.get("right") or 0.0),
        }

    active_threshold = max(0.006, density * 0.62)
    active_zones = [name for name, val in sorted(zone_scores.items(), key=lambda kv: kv[1], reverse=True) if val >= active_threshold]

    image_mode = "single_design"
    min_files = 1
    max_files = 1
    wide_multi_hint = aspect >= 1.12 and (len(active_zones) >= 4 or coverage > 0.16)
    zone_multi_hint = len(active_zones) >= 6 and coverage > 0.10
    strong_region_multi = est_regions >= 4 and not (aspect < 0.85 and coverage < 245)
    if strong_region_multi or wide_multi_hint or zone_multi_hint:
        image_mode = "multi_design_preview"
        min_files = 4 if strong_region_multi or len(active_zones) >= 4 else 3
        max_files = 5 if est_regions >= 5 or (len(active_zones) >= 5 and aspect > 1.05) or aspect > 1.55 else 4
    elif est_regions >= 3 or (aspect > 1.05 and len(active_zones) >= 3):
        image_mode = "possible_multi_design_preview"
        min_files = 2
        max_files = 3

    # Give likely labels by zone. These are hints for review, not final truth.
    hints = {
        "bottom_left": "back_neck_or_boat_neck",
        "middle_left": "front_neck_or_neck_border",
        "top_left": "short_hand_or_border_panel",
        "top_center": "short_hand_or_hanging_panel",
        "top_right": "stitched_photo_reference_or_sleeve",
        "middle_right": "stitched_photo_reference_or_full_hand",
        "bottom_right": "full_hand_or_border_panel",
        "bottom_center": "border_or_butti_panel",
        "center": "front_neck_or_shared_design_area",
    }
    parts: List[Dict[str, Any]] = []
    for idx, name in enumerate(active_zones[:8], start=1):
        score = float(zone_scores.get(name) or 0.0)
        parts.append({
            "part_id": idx,
            "zone": name,
            "review_hint": hints.get(name, "design_part"),
            "zone_density": round(score, 6),
            "action": "review_crop_clean_and_search_separately" if image_mode != "single_design" else "use_as_supporting_feature",
        })
    if not parts:
        parts.append({"part_id": 1, "zone": "full_image", "review_hint": "single_design", "zone_density": round(density, 6), "action": "classify_full_image"})

    return {
        "engine": TURBOTHINKER_ENGINE_VERSION,
        "image_mode": image_mode,
        "unique_design_file_count": {"min": int(min_files), "max": int(max_files)},
        "estimated_region_count": int(est_regions),
        "active_zone_count": int(len(active_zones)),
        "active_zones": active_zones,
        "parts_detected": parts,
        "strategy": "divide_sort_cache_search" if image_mode != "single_design" else "type_sort_cache_search",
        "note": "Local heuristic only. User correction in Training Center is the final label.",
    }

def analyze_image_for_training(img: Image.Image, source_name: str = "uploaded_image") -> Dict[str, Any]:
    features = extract_visual_features(img)
    turbothinker = infer_turbothinker_parts(features)
    prediction = classify_features(features)
    # If TurboThinker sees many useful parts, expose that as the image mode while
    # keeping the actual label scores available for review/correction.
    if turbothinker.get("image_mode") == "multi_design_preview":
        scores = dict(prediction.get("scores") or {})
        scores["multi_design_preview"] = max(float(scores.get("multi_design_preview", 0.0)), 0.72)
        sorted_scores = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        best_label, best_score = sorted_scores[0]
        secondary = [label for label, score in sorted_scores[1:6] if score >= 0.24 and label != best_label]
        prediction.update({
            "predicted_type": best_label,
            "confidence": int(round(min(0.96, max(0.15, best_score)) * 100)),
            "secondary_types": secondary,
            "scores": {k: round(float(v), 4) for k, v in scores.items()},
            "tags": _tags_from_features(features, best_label, secondary),
            "search_groups": candidate_search_groups(best_label, secondary),
            "image_mode": turbothinker.get("image_mode"),
        })
    # Add local explanation so the trainer can understand why it guessed the tag.
    prediction["reason"] = explain_prediction(features, prediction, turbothinker)
    return {
        "version": IMGS_TRAINING_VERSION,
        "turbothinker_engine": TURBOTHINKER_ENGINE_VERSION,
        "source_name": source_name,
        "created_at": utc_now(),
        "engine_tag": IMGS_TRAINING_TAG,
        "turbothinker_tag": TURBOTHINKER_TAG,
        "warning": IMGS_TRAINING_WARNING,
        "turbothinker": turbothinker,
        "features": features,
        "prediction": prediction,
    }


def analyze_preview_file(preview_path: Path, source_name: Optional[str] = None) -> Dict[str, Any]:
    with Image.open(preview_path) as img:
        return analyze_image_for_training(img.convert("RGB"), source_name or preview_path.name)


def _save_optional_fingerprint(img_or_path: Any, target_path: Path) -> Optional[str]:
    if str(os.environ.get("IMGS_TRAINING_SAVE_FINGERPRINTS", "true")).lower() not in {"1", "true", "yes", "on"}:
        return None
    try:
        if isinstance(img_or_path, (str, Path)) and create_fingerprint_from_path is not None:
            fp = create_fingerprint_from_path(Path(img_or_path))
        elif create_fingerprint_from_image is not None:
            fp = create_fingerprint_from_image(img_or_path)
        else:
            return None
        _write_json(target_path, fp)
        return str(target_path)
    except Exception:
        return None


def apply_imgs_training_to_item(app_root: Path, item: Dict[str, Any], force: bool = False) -> Dict[str, Any]:
    """Analyze one library item preview, save JSON/fingerprint, and attach summary to item."""
    paths = ensure_training_dirs(app_root)
    item_id = str(item.get("id") or hashlib.sha256(str(item).encode("utf-8")).hexdigest()[:16])
    json_path = paths["design_json"] / f"{item_id}.json"
    preview_path = Path(str(item.get("preview_path") or ""))
    if not preview_path.exists():
        item["imgs_training"] = {
            "engine": IMGS_TRAINING_VERSION,
            "status": "missing_preview",
            "predicted_type": "unknown_review",
            "confidence": 0,
        }
        return item
    if json_path.exists() and not force:
        data = _read_json(json_path, {})
    else:
        data = analyze_preview_file(preview_path, source_name=str(item.get("name") or preview_path.name))
        data = apply_seed_training_memory(app_root, data)
        data = apply_student_model_memory(app_root, data)
        data = apply_ultrabrain_memory(app_root, data)
        data = apply_correction_memory(app_root, data)
        data["item"] = {
            "id": item_id,
            "name": item.get("name"),
            "relative_path": item.get("relative_path"),
            "preview_path": str(preview_path),
            "source_path": item.get("path"),
        }
        fp_path = paths["fingerprints"] / f"{item_id}.json"
        fingerprint_path = _save_optional_fingerprint(preview_path, fp_path)
        if fingerprint_path:
            data["fingerprint_path"] = fingerprint_path
        _write_json(json_path, data)

    pred = (data.get("prediction") or {}) if isinstance(data, dict) else {}
    item["imgs_training"] = {
        "engine": IMGS_TRAINING_VERSION,
        "turbothinker_engine": TURBOTHINKER_ENGINE_VERSION,
        "engine_tag": IMGS_TRAINING_TAG,
        "turbothinker_tag": TURBOTHINKER_TAG,
        "status": "trained",
        "json_path": str(json_path),
        "fingerprint_path": data.get("fingerprint_path") if isinstance(data, dict) else None,
        "predicted_type": pred.get("predicted_type", "unknown_review"),
        "confidence": int(pred.get("confidence") or 0),
        "secondary_types": list(pred.get("secondary_types") or []),
        "tags": list(pred.get("tags") or []),
        "search_groups": list(pred.get("search_groups") or []),
        "turbothinker": (data.get("turbothinker") if isinstance(data, dict) else None),
        "updated_at": utc_now(),
    }
    return item


def build_training_index(app_root: Path, items: List[Dict[str, Any]]) -> Dict[str, Any]:
    ensure_training_dirs(app_root)
    index: Dict[str, Any] = {"version": IMGS_TRAINING_VERSION, "updated_at": utc_now(), "by_type": {}, "items": {}}
    for item in items:
        item_id = str(item.get("id") or "")
        train = item.get("imgs_training") or {}
        label = str(train.get("predicted_type") or "unknown_review")
        if label not in IMGS_LABELS:
            label = "unknown_review"
        row = {
            "id": item_id,
            "name": item.get("name"),
            "relative_path": item.get("relative_path"),
            "preview_path": item.get("preview_path"),
            "source_path": item.get("path"),
            "predicted_type": label,
            "confidence": train.get("confidence", 0),
            "tags": train.get("tags", []),
            "json_path": train.get("json_path"),
            "fingerprint_path": train.get("fingerprint_path"),
        }
        index["items"][item_id] = row
        index["by_type"].setdefault(label, []).append(item_id)
    save_training_index(app_root, index)
    return index


def record_training_correction(
    app_root: Path,
    sample_id: str,
    source_name: str,
    analysis: Dict[str, Any],
    final_label: str,
    notes: str = "",
    sample_image_path: Optional[str] = None,
    manual_tags: Optional[Iterable[str]] = None,
    auto_remove_low_tags: bool = False,
    tag_min_score: float = 0.24,
) -> Dict[str, Any]:
    if final_label not in IMGS_LABELS:
        final_label = "unknown_review"
    ensure_training_dirs(app_root)
    data = load_corrections(app_root)
    pred_for_save = dict(analysis.get("prediction") or {})
    if auto_remove_low_tags:
        pred_for_save = prune_prediction_tags(pred_for_save, min_score=tag_min_score)
    if manual_tags:
        pred_for_save = add_manual_tags(pred_for_save, manual_tags)

    sample = {
        "sample_id": sample_id,
        "source_name": source_name,
        "sample_image_path": sample_image_path,
        "ai_engine": IMGS_TRAINING_VERSION,
        "turbothinker_engine": TURBOTHINKER_ENGINE_VERSION,
        "engine_tag": IMGS_TRAINING_TAG,
        "turbothinker_tag": TURBOTHINKER_TAG,
        "predicted_type": pred_for_save.get("predicted_type"),
        "confidence": pred_for_save.get("confidence"),
        "final_label": final_label,
        "notes": notes,
        "features": analysis.get("features") or {},
        "tags": pred_for_save.get("tags") or [],
        "manual_tags": list(manual_tags or []),
        "auto_remove_low_tags": bool(auto_remove_low_tags),
        "tag_min_score": float(tag_min_score),
        "reason": pred_for_save.get("reason") or [],
        "created_at": utc_now(),
    }
    samples = list(data.get("samples") or [])
    # Update same sample_id instead of endlessly duplicating corrections.
    replaced = False
    for i, old in enumerate(samples):
        if old.get("sample_id") == sample_id:
            samples[i] = sample
            replaced = True
            break
    if not replaced:
        samples.append(sample)
    data["samples"] = samples
    save_corrections(app_root, data)
    _write_json(training_root(app_root) / "last_correction.json", sample)
    return sample


def save_uploaded_training_image(app_root: Path, img: Image.Image, source_name: str) -> Tuple[str, Path]:
    paths = ensure_training_dirs(app_root)
    rgb = _to_rgb(img)
    buf = rgb.tobytes() + str(source_name).encode("utf-8")
    sample_id = hashlib.sha256(buf).hexdigest()[:16]
    out = paths["samples"] / f"{sample_id}_{_safe_file_stem(source_name)}.png"
    if not out.exists():
        rgb.save(out, format="PNG", optimize=True)
    return sample_id, out


def _safe_file_stem(value: str, max_len: int = 60) -> str:
    stem = Path(str(value)).stem or "sample"
    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in stem).strip("_")
    return (cleaned or "sample")[:max_len]



def _seed_bank_path(app_root: Path) -> Path:
    return training_root(app_root) / "seed_training" / "seed_visual_bank.json"


def load_seed_training_bank(app_root: Path) -> Dict[str, Any]:
    return _read_json(_seed_bank_path(app_root), {"version": IMGS_TRAINING_VERSION, "rows": [], "summary": {}})


def save_seed_training_bank(app_root: Path, bank: Dict[str, Any]) -> None:
    bank["version"] = IMGS_TRAINING_VERSION
    bank["updated_at"] = utc_now()
    _write_json(_seed_bank_path(app_root), bank)



def _ultrabrain_region_bank_path(app_root: Path) -> Path:
    return training_root(app_root) / "seed_training" / "ultrabrain_region_visual_bank.json"


def load_ultrabrain_region_bank(app_root: Path) -> Dict[str, Any]:
    return _read_json(_ultrabrain_region_bank_path(app_root), {"version": IMGS_TRAINING_VERSION, "rows": [], "summary": {}})


def save_ultrabrain_region_bank(app_root: Path, bank: Dict[str, Any]) -> None:
    bank["version"] = IMGS_TRAINING_VERSION
    bank["updated_at"] = utc_now()
    _write_json(_ultrabrain_region_bank_path(app_root), bank)


def _ultrabrain_crop_boxes(width: int, height: int) -> List[Tuple[str, Tuple[int, int, int, int]]]:
    """Multi-scale crop map for teaching UltraBrain parts inside preview sheets."""
    w, h = max(1, int(width)), max(1, int(height))
    boxes = [
        ("center", (int(w * 0.20), int(h * 0.18), int(w * 0.80), int(h * 0.82))),
        ("top_band", (0, 0, w, int(h * 0.36))),
        ("middle_band", (0, int(h * 0.28), w, int(h * 0.72))),
        ("bottom_band", (0, int(h * 0.64), w, h)),
        ("left_half", (0, 0, int(w * 244), h)),
        ("right_half", (int(w * 0.46), 0, w, h)),
        ("top_left", (0, 0, int(w * 242), int(h * 242))),
        ("top_right", (int(w * 0.48), 0, w, int(h * 242))),
        ("bottom_left", (0, int(h * 0.48), int(w * 242), h)),
        ("bottom_right", (int(w * 0.48), int(h * 0.48), w, h)),
    ]
    clean: List[Tuple[str, Tuple[int, int, int, int]]] = []
    for name, box in boxes:
        x1, y1, x2, y2 = box
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, max(x1 + 8, x2)), min(h, max(y1 + 8, y2))
        if x2 - x1 >= 64 and y2 - y1 >= 64:
            clean.append((name, (x1, y1, x2, y2)))
    return clean


def build_ultrabrain_region_corpus_from_zip_bytes(
    app_root: Path,
    zip_payload: bytes,
    corpus_name: str = "training_zip_regions",
    limit: Optional[int] = None,
    crops_per_image: int = 8,
    tag_min_score: float = 0.24,
) -> Dict[str, Any]:
    """Create region/crop-level visual rows from the same training ZIP.

    This is a stronger training layer than full-image seed rows. It teaches
    UltraBrain from parts inside preview images: bands, corners, center, sleeve
    panels, neck areas, border zones, and stitched-photo regions. Source names
    remain review IDs only and are not used as labels.
    """
    ensure_training_dirs(app_root)
    started = time.time()
    rows: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    images_seen = 0
    for source_name, payload in _iter_zip_image_payloads(zip_payload):
        if limit is not None and images_seen >= int(limit):
            break
        images_seen += 1
        try:
            with Image.open(io.BytesIO(payload)) as raw_img:
                img = ImageOps.exif_transpose(raw_img).convert("RGB")
            w, h = img.size
            for crop_index, (zone, box) in enumerate(_ultrabrain_crop_boxes(w, h)[:max(1, int(crops_per_image))], start=1):
                crop = img.crop(box)
                # Skip very tiny blank-like crops cheaply.
                cf = extract_visual_features(crop)
                if float(cf.get("ink_density") or 0.0) < 0.012 and float(cf.get("edge_strength") or 0.0) < 0.035:
                    continue
                analysis = analyze_image_for_training(crop, f"{Path(source_name).name}::{zone}")
                pred = dict(analysis.get("prediction") or {})
                if tag_min_score:
                    pred = prune_prediction_tags(pred, min_score=float(tag_min_score))
                    analysis["prediction"] = pred
                features = analysis.get("features") or {}
                row_tags = list(pred.get("tags") or [])
                if zone not in row_tags:
                    row_tags.append(zone)
                row = {
                    "sample_id": hashlib.sha256(f"{source_name}|{zone}|{box}".encode("utf-8")).hexdigest()[:20],
                    "source_name": Path(source_name).name,
                    "source_path_in_zip": source_name,
                    "zone": zone,
                    "crop_box": list(box),
                    "trained_from_filename": False,
                    "source_name_used_for_label": False,
                    "predicted_type": pred.get("predicted_type", "unknown_review"),
                    "confidence": pred.get("confidence", 0),
                    "tags": row_tags,
                    "scores": pred.get("scores") or {},
                    "image_mode": pred.get("image_mode") or (analysis.get("turbothinker") or {}).get("image_mode"),
                    "estimated_unique_designs": (analysis.get("turbothinker") or {}).get("unique_design_file_count") or {"min": 1, "max": 1},
                    "parts_detected": (analysis.get("turbothinker") or {}).get("parts_detected") or [],
                    "feature_vector": _feature_vector(features),
                    "features": {
                        "source_size": features.get("source_size"),
                        "ink_density": features.get("ink_density"),
                        "ink_coverage": features.get("ink_coverage"),
                        "aspect": features.get("aspect"),
                        "original_aspect": features.get("original_aspect"),
                        "component_count": features.get("component_count"),
                        "estimated_region_count": features.get("estimated_region_count"),
                        "net_score": features.get("net_score"),
                        "edge_strength": features.get("edge_strength"),
                        "scattered_score": features.get("scattered_score"),
                    },
                    "reason": pred.get("reason") or [],
                    "created_at": utc_now(),
                    "review_status": "auto_region_seed_needs_user_review",
                }
                rows.append(row)
        except Exception as exc:
            errors.append({"source_name": Path(source_name).name, "error": str(exc)[:220]})
    count_by_type: Dict[str, int] = {}
    for row in rows:
        label = str(row.get("predicted_type") or "unknown_review")
        count_by_type[label] = count_by_type.get(label, 0) + 1
    bank = {
        "version": IMGS_TRAINING_VERSION,
        "turbothinker_engine": TURBOTHINKER_ENGINE_VERSION,
        "corpus_name": _safe_file_stem(corpus_name, 80),
        "created_at": utc_now(),
        "trained_from_filename": False,
        "note": "UltraBrain region bank. Crop labels are auto visual guesses and should be corrected over time.",
        "summary": {
            "images_seen": int(images_seen),
            "region_rows_indexed": len(rows),
            "errors": len(errors),
            "count_by_type": count_by_type,
            "seconds": round(time.time() - started, 2),
        },
        "rows": rows,
        "errors": errors[:100],
    }
    save_ultrabrain_region_bank(app_root, bank)
    return bank


def build_ultrabrain_region_corpus_from_zip_path(
    app_root: Path,
    zip_path: Path,
    corpus_name: Optional[str] = None,
    limit: Optional[int] = None,
    crops_per_image: int = 8,
    tag_min_score: float = 0.24,
) -> Dict[str, Any]:
    return build_ultrabrain_region_corpus_from_zip_bytes(
        app_root,
        Path(zip_path).read_bytes(),
        corpus_name=corpus_name or Path(zip_path).stem,
        limit=limit,
        crops_per_image=crops_per_image,
        tag_min_score=tag_min_score,
    )

def _iter_zip_image_payloads(zip_bytes_or_path: Any) -> Iterable[Tuple[str, bytes]]:
    source = zip_bytes_or_path
    if isinstance(source, (str, Path)):
        zf = zipfile.ZipFile(source)
    else:
        zf = zipfile.ZipFile(io.BytesIO(bytes(source)))
    with zf:
        for name in zf.namelist():
            low = name.lower()
            if low.endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp")) and not name.endswith("/"):
                try:
                    yield name, zf.read(name)
                except Exception:
                    continue


def _prototype_rows(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    grouped: Dict[str, List[List[float]]] = {}
    for row in rows:
        label = str(row.get("predicted_type") or "unknown_review")
        vec = row.get("feature_vector") or []
        if vec:
            grouped.setdefault(label, []).append([float(v) for v in vec])
    prototypes: Dict[str, Any] = {}
    for label, vectors in grouped.items():
        if not vectors:
            continue
        n = min(len(v) for v in vectors)
        avg = [round(sum(v[i] for v in vectors) / max(1, len(vectors)), 6) for i in range(n)]
        prototypes[label] = {"count": len(vectors), "feature_vector": avg}
    return prototypes


def build_seed_training_corpus_from_zip_bytes(
    app_root: Path,
    zip_payload: bytes,
    corpus_name: str = "training_zip",
    limit: Optional[int] = None,
    tag_min_score: float = 0.24,
    save_detail_json: bool = True,
) -> Dict[str, Any]:
    """Build an unlabeled visual seed bank from a ZIP of 300+ images.

    This is intentionally not filename-based and not a fake perfect ML model. It
    extracts visual features, auto-tags, feature vectors, and local reasons. User
    corrections can later turn these rows into stronger supervised memory.
    """
    paths = ensure_training_dirs(app_root)
    rows: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []
    count_by_type: Dict[str, int] = {}
    total_seen = 0
    started = time.time()
    detail_dir = paths["seed_training"] / "design_json"
    for source_name, payload in _iter_zip_image_payloads(zip_payload):
        if limit is not None and len(rows) >= int(limit):
            break
        total_seen += 1
        try:
            with Image.open(io.BytesIO(payload)) as img:
                rgb = img.convert("RGB")
            sample_id = hashlib.sha256(payload).hexdigest()[:20]
            analysis = analyze_image_for_training(rgb, Path(source_name).name)
            pred = prune_prediction_tags(analysis.get("prediction") or {}, min_score=float(tag_min_score))
            analysis = dict(analysis)
            analysis["prediction"] = pred
            features = analysis.get("features") or {}
            thinker = analysis.get("turbothinker") or {}
            row = {
                "sample_id": sample_id,
                "source_name": Path(source_name).name,
                "source_path_in_zip": source_name,
                "trained_from_filename": False,
                "source_name_used_for_label": False,
                "predicted_type": pred.get("predicted_type", "unknown_review"),
                "confidence": int(pred.get("confidence") or 0),
                "tags": list(pred.get("tags") or []),
                "scores": pred.get("scores") or {},
                "image_mode": thinker.get("image_mode", "single_design"),
                "estimated_unique_designs": thinker.get("unique_design_file_count") or {"min": 1, "max": 1},
                "parts_detected": thinker.get("parts_detected") or [],
                "feature_vector": _feature_vector(features),
                "features": {
                    "source_size": features.get("source_size"),
                    "ink_density": features.get("ink_density"),
                    "ink_coverage": features.get("ink_coverage"),
                    "aspect": features.get("aspect"),
                    "original_aspect": features.get("original_aspect"),
                    "component_count": features.get("component_count"),
                    "estimated_region_count": features.get("estimated_region_count"),
                    "net_score": features.get("net_score"),
                    "edge_strength": features.get("edge_strength"),
                    "scattered_score": features.get("scattered_score"),
                },
                "reason": pred.get("reason") or [],
                "created_at": utc_now(),
                "review_status": "auto_seed_needs_user_review",
            }
            rows.append(row)
            label = str(row["predicted_type"] or "unknown_review")
            count_by_type[label] = count_by_type.get(label, 0) + 1
            if save_detail_json:
                detail = dict(analysis)
                detail["seed_training_row"] = {k: v for k, v in row.items() if k not in {"scores", "feature_vector", "parts_detected"}}
                _write_json(detail_dir / f"{sample_id}.json", detail)
        except Exception as exc:
            errors.append({"source_name": Path(source_name).name, "error": str(exc)[:220]})
    prototypes = _prototype_rows(rows)
    bank = {
        "version": IMGS_TRAINING_VERSION,
        "turbothinker_engine": TURBOTHINKER_ENGINE_VERSION,
        "corpus_name": _safe_file_stem(corpus_name, 80),
        "created_at": utc_now(),
        "trained_from_filename": False,
        "note": "Visual seed bank only. Labels are auto guesses and should be reviewed/corrected locally.",
        "summary": {
            "images_seen": int(total_seen),
            "images_indexed": len(rows),
            "errors": len(errors),
            "count_by_type": count_by_type,
            "seconds": round(time.time() - started, 2),
        },
        "prototypes": prototypes,
        "rows": rows,
        "errors": errors[:100],
    }
    save_seed_training_bank(app_root, bank)
    _write_json(paths["prototypes"] / "seed_tag_prototypes.json", prototypes)
    _write_json(paths["root"] / "tag_catalog.json", TAG_CATALOG)
    return bank


def build_seed_training_corpus_from_zip_path(
    app_root: Path,
    zip_path: Path,
    corpus_name: Optional[str] = None,
    limit: Optional[int] = None,
    tag_min_score: float = 0.24,
) -> Dict[str, Any]:
    return build_seed_training_corpus_from_zip_bytes(
        app_root,
        Path(zip_path).read_bytes(),
        corpus_name=corpus_name or Path(zip_path).stem,
        limit=limit,
        tag_min_score=tag_min_score,
    )



def train_turbothinker_student_model(
    app_root: Path,
    epochs: int = 340,
    include_seed_bank: bool = True,
    include_user_corrections: bool = True,
) -> Dict[str, Any]:
    """Train the v4.9 local AI-student model and save real weights.

    This is the important v4.9 step requested by shiva shanth: not only a JSON
    visual seed bank, but a trainable local model whose weights are saved under
    imgs_training/models/. The seed-bank labels are pseudo labels from visual
    reading; user corrections are stronger supervised examples.
    """
    ensure_training_dirs(app_root)
    if train_multilabel_student is None or rows_from_seed_bank is None or save_student_model is None:
        raise RuntimeError("TurboThinker Student trainer is unavailable in this build.")
    training_rows: List[Dict[str, Any]] = []
    seed_summary: Dict[str, Any] = {}
    if include_seed_bank:
        bank = load_seed_training_bank(app_root)
        seed_summary = bank.get("summary") or {}
        training_rows.extend(rows_from_seed_bank(bank, STUDENT_OUTPUT_LABELS))
    correction_count = 0
    if include_user_corrections and rows_from_corrections is not None:
        correction_rows = rows_from_corrections(load_corrections(app_root), STUDENT_OUTPUT_LABELS, feature_vector_func=_feature_vector)
        correction_count = len(correction_rows)
        training_rows.extend(correction_rows)
    if not training_rows:
        raise RuntimeError("No visual training rows found. Build a seed bank from a ZIP or save corrections first.")
    model = train_multilabel_student(
        training_rows,
        output_labels=STUDENT_OUTPUT_LABELS,
        epochs=int(epochs),
        lr=0.075,
        l2=0.0006,
        seed=49,
    )
    model["training_summary"]["seed_bank_images_indexed"] = seed_summary.get("images_indexed")
    model["training_summary"]["correction_rows_loaded"] = correction_count
    path = save_student_model(app_root, model)
    report = {
        "status": "trained",
        "model_path": str(path),
        "version": model.get("version"),
        "model_type": model.get("model_type"),
        "feature_count": model.get("feature_count"),
        "output_labels": len(model.get("output_labels") or []),
        "training_summary": model.get("training_summary") or {},
        "positive_counts": model.get("positive_counts") or {},
        "trained_from_filename": False,
        "source_name_used_for_label": False,
        "created_at": model.get("created_at"),
    }
    _write_json(training_root(app_root) / "models" / "last_student_training_report.json", report)
    return report


def load_turbothinker_student_summary(app_root: Path) -> Dict[str, Any]:
    if student_model_summary is None:
        return {"exists": False, "error": "TurboThinker Student module unavailable"}
    return student_model_summary(app_root)


def _student_primary_candidates() -> List[str]:
    return [
        "multi_design_preview", "heavy_work", "all_over_design", "front_neck", "back_neck",
        "boat_neck", "pot_neck", "short_hand", "full_hand", "cut_work", "butti", "border",
        "rangoli_design", "back_drop_neck", "stitched_photo_reference",
    ]


def apply_student_model_memory(app_root: Path, analysis: Dict[str, Any], blend: float = 246) -> Dict[str, Any]:
    """Blend the v4.9 trained local AI-student model into a prediction.

    The student model has real saved weights. It is still kept under the rule
    reader and correction memory so user review stays in control.
    """
    try:
        if load_student_model is None or predict_student_vector is None:
            return analysis
        model = load_student_model(app_root)
        if not model:
            return analysis
        pred = dict(analysis.get("prediction") or {})
        features = analysis.get("features") or {}
        thinker = analysis.get("turbothinker") or {}
        qv = _feature_vector(features)
        probs = predict_student_vector(model, qv)
        if not probs:
            return analysis
        scores = {str(k): float(v) for k, v in (pred.get("scores") or {}).items()}
        regions = int(features.get("estimated_region_count") or thinker.get("estimated_region_count") or 1)
        image_mode = str(thinker.get("image_mode") or pred.get("image_mode") or "")
        learned_tags: List[str] = []
        primary_labels = set(_student_primary_candidates())
        # Keep multi_design_preview locked only when the visual layout also supports it.
        multi_prob = float(probs.get("multi_design_preview") or 0.0)
        if image_mode == "multi_design_preview" or regions >= 4 or "multi_design_preview" in (pred.get("tags") or []):
            scores["multi_design_preview"] = max(scores.get("multi_design_preview", 0.0), min(0.96, max(0.72, multi_prob)))
            learned_tags.append("multi_design_preview")
        for label, prob in sorted(probs.items(), key=lambda kv: float(kv[1]), reverse=True):
            label = normalize_tag(label)
            p = float(prob)
            if not label or label == "multi_design_preview":
                continue
            if label in IMGS_LABELS or label in primary_labels:
                old = float(scores.get(label, 0.0))
                # Blend, do not blindly overwrite. This keeps the explainable reader and
                # future user corrections stronger than pseudo-trained seed rows.
                learned = (old * (1.0 - blend)) + (p * blend)
                scores[label] = max(old, min(0.98, learned))
            if p >= 0.46 and label not in learned_tags:
                learned_tags.append(label)
        sorted_scores = sorted(scores.items(), key=lambda kv: float(kv[1]), reverse=True)
        if not sorted_scores:
            return analysis
        best_label, best_score = sorted_scores[0]
        if "multi_design_preview" in scores and (image_mode == "multi_design_preview" or regions >= 4):
            best_label = "multi_design_preview"
            best_score = float(scores.get("multi_design_preview") or best_score)
        secondary = [label for label, score in sorted_scores if label != best_label and score >= 0.26][:8]
        base_tags = list(pred.get("tags") or []) + learned_tags
        image_mode_final = "multi_design_preview" if best_label == "multi_design_preview" or "multi_design_preview" in base_tags else image_mode
        tags = ordered_unique_tags(
            base_tags,
            scores=scores,
            primary=best_label,
            image_mode=image_mode_final,
            limit=18,
            keep_engine_tags=True,
        )
        pred.update({
            "predicted_type": best_label if float(best_score) >= 0.28 else pred.get("predicted_type", "unknown_review"),
            "confidence": int(round(min(0.98, max(0.15, float(best_score))) * 100)),
            "secondary_types": secondary,
            "scores": {k: round(float(v), 4) for k, v in scores.items()},
            "tags": tags,
            "search_groups": candidate_search_groups(best_label, secondary),
            "student_model_used": True,
            "student_model_version": model.get("version"),
            "student_model_path": str(student_model_path(app_root)) if student_model_path is not None else "",
            "student_label_probabilities": {k: round(float(v), 4) for k, v in sorted(probs.items(), key=lambda kv: float(kv[1]), reverse=True)[:14]},
            "image_mode": image_mode_final,
        })
        pred["reason"] = explain_prediction(features, pred, thinker)
        pred.setdefault("reason", [])
        pred["reason"] = list(pred.get("reason") or []) + [
            "v4.9 AI-student model used real saved local weights trained from the uploaded image corpus and local corrections; filenames are not used as labels."
        ]
        analysis = dict(analysis)
        analysis["prediction"] = pred
        analysis["student_model"] = {
            "used": True,
            "version": model.get("version"),
            "created_at": model.get("created_at"),
            "training_summary": model.get("training_summary") or {},
        }
        return analysis
    except Exception as exc:
        analysis = dict(analysis)
        pred = dict(analysis.get("prediction") or {})
        pred.setdefault("student_model_warning", str(exc)[:180])
        analysis["prediction"] = pred
        return analysis



def train_turbothinker_ultrabrain_model(
    app_root: Path,
    epochs: int = 260,
    include_seed_bank: bool = True,
    include_user_corrections: bool = True,
) -> Dict[str, Any]:
    """Train the v5.0 local UltraBrain ensemble and save its model.

    UltraBrain is the bigger recognition brain requested for v4.9+ / v5: it
    combines trainable weights, visual prototypes, k-nearest visual memory, and
    embroidery tag co-occurrence. It remains local-only and filename-free.
    """
    ensure_training_dirs(app_root)
    if _train_ultrabrain_model is None:
        raise RuntimeError("TurboThinker UltraBrain trainer is unavailable in this build.")
    seed_bank: Dict[str, Any] = {}
    if include_seed_bank:
        seed_bank = load_seed_training_bank(app_root)
        region_bank = load_ultrabrain_region_bank(app_root)
        if region_bank.get("rows"):
            seed_bank = dict(seed_bank or {})
            seed_bank["rows"] = list(seed_bank.get("rows") or []) + list(region_bank.get("rows") or [])
            seed_bank["ultrabrain_region_summary"] = region_bank.get("summary") or {}
    corrections: Dict[str, Any] = {}
    if include_user_corrections:
        corrections = load_corrections(app_root)
    report = _train_ultrabrain_model(
        app_root=app_root,
        seed_bank=seed_bank,
        corrections=corrections,
        epochs=int(epochs),
        extra_labels=list(TAG_CATALOG.get("all_tags") or []) + list(STUDENT_OUTPUT_LABELS or []),
    )
    return report


def load_turbothinker_ultrabrain_summary(app_root: Path) -> Dict[str, Any]:
    if ultrabrain_summary is None:
        return {"exists": False, "error": "TurboThinker UltraBrain module unavailable"}
    return ultrabrain_summary(app_root)


def apply_ultrabrain_memory(app_root: Path, analysis: Dict[str, Any], blend: float = 0.72) -> Dict[str, Any]:
    """Blend v5.0 UltraBrain ensemble scores into an analysis prediction.

    This sits above rule reading and v4.9 student weights. It never blindly
    overwrites user corrections; it improves automatic guesses by combining
    local model heads, prototypes, nearest-neighbor visual memory, and tag graph.
    """
    try:
        if load_ultrabrain_model is None or predict_ultrabrain_vector is None:
            return analysis
        model = load_ultrabrain_model(app_root)
        if not model:
            return analysis
        pred = dict(analysis.get("prediction") or {})
        features = analysis.get("features") or {}
        thinker = analysis.get("turbothinker") or {}
        qv = _feature_vector(features)
        base_scores = {str(k): float(v) for k, v in (pred.get("scores") or {}).items()}
        ultra = predict_ultrabrain_vector(model, qv, base_scores=base_scores)
        ultra_scores = {str(k): float(v) for k, v in (ultra.get("scores") or {}).items()}
        if not ultra_scores:
            return analysis
        scores = dict(base_scores)
        for label, score in ultra_scores.items():
            label = normalize_tag(label)
            if not label:
                continue
            old = float(scores.get(label, 0.0))
            scores[label] = max(old, min(0.995, old * (1.0 - blend) + score * blend))
        regions = int(features.get("estimated_region_count") or thinker.get("estimated_region_count") or 1)
        image_mode = str(thinker.get("image_mode") or pred.get("image_mode") or "")
        # Multi-preview stays first only when the whole-image layout supports it.
        if image_mode == "multi_design_preview" or regions >= 4 or "multi_design_preview" in (pred.get("tags") or []):
            scores["multi_design_preview"] = max(float(scores.get("multi_design_preview", 0.0)), 0.74)
        sorted_scores = sorted(scores.items(), key=lambda kv: float(kv[1]), reverse=True)
        best_label, best_score = sorted_scores[0]
        if "multi_design_preview" in scores and (image_mode == "multi_design_preview" or regions >= 4):
            best_label = "multi_design_preview"
            best_score = scores.get("multi_design_preview", best_score)
        secondary = [label for label, score in sorted_scores if label != best_label and float(score) >= 0.28][:10]
        ultra_tags = [label for label, score in sorted(ultra_scores.items(), key=lambda kv: kv[1], reverse=True) if score >= 0.38][:12]
        image_mode_final = "multi_design_preview" if best_label == "multi_design_preview" or "multi_design_preview" in ultra_tags else image_mode
        tags = ordered_unique_tags(
            list(pred.get("tags") or []) + ultra_tags,
            scores=scores,
            primary=best_label,
            image_mode=image_mode_final,
            limit=22,
            keep_engine_tags=True,
        )
        pred.update({
            "predicted_type": best_label if float(best_score) >= 0.30 else pred.get("predicted_type", "unknown_review"),
            "confidence": int(round(min(0.99, max(0.15, float(best_score))) * 100)),
            "secondary_types": secondary,
            "scores": {k: round(float(v), 4) for k, v in scores.items()},
            "tags": tags,
            "search_groups": candidate_search_groups(best_label, secondary),
            "ultrabrain_used": True,
            "ultrabrain_version": model.get("version"),
            "ultrabrain_model_path": str(ultrabrain_model_path(app_root)) if ultrabrain_model_path is not None else "",
            "ultrabrain_label_probabilities": {k: round(float(v), 4) for k, v in sorted(ultra_scores.items(), key=lambda kv: kv[1], reverse=True)[:18]},
            "ultrabrain_neighbors": ultra.get("neighbors") or [],
            "image_mode": image_mode_final,
        })
        pred["reason"] = explain_prediction(features, pred, thinker)
        pred["reason"] = list(pred.get("reason") or []) + list(ultra.get("reason") or []) + [
            "v5.0 UltraBrain used local ensemble recognition: trainable weights + prototypes + nearest visual memory + tag graph; filenames are not used as labels."
        ]
        analysis = dict(analysis)
        analysis["prediction"] = pred
        analysis["ultrabrain"] = {
            "used": True,
            "version": model.get("version"),
            "created_at": model.get("created_at"),
            "training_summary": model.get("training_summary") or {},
            "neighbors_used": len(ultra.get("neighbors") or []),
        }
        return analysis
    except Exception as exc:
        analysis = dict(analysis)
        pred = dict(analysis.get("prediction") or {})
        pred.setdefault("ultrabrain_warning", str(exc)[:180])
        analysis["prediction"] = pred
        return analysis


def train_turbothinker_superbrain_model(
    app_root: Path,
    include_seed_bank: bool = True,
    include_user_corrections: bool = True,
    augmentation_multiplier: int = 4,
) -> Dict[str, Any]:
    """Train the v5.1 local SuperBrain and save a larger local model.

    SuperBrain is the bigger recognition layer requested after v5.0. It builds
    multi-cortex feature weights, label capsules, larger KNN memory, and failure
    diagnosis. It remains local-only and does not use filenames as labels.
    """
    ensure_training_dirs(app_root)
    if _train_superbrain_model is None:
        raise RuntimeError("TurboThinker SuperBrain trainer is unavailable in this build.")
    seed_bank: Dict[str, Any] = {}
    if include_seed_bank:
        seed_bank = load_seed_training_bank(app_root)
        region_bank = load_ultrabrain_region_bank(app_root)
        if region_bank.get("rows"):
            seed_bank = dict(seed_bank or {})
            seed_bank["rows"] = list(seed_bank.get("rows") or []) + list(region_bank.get("rows") or [])
            seed_bank["ultrabrain_region_summary"] = region_bank.get("summary") or {}
    corrections: Dict[str, Any] = {}
    if include_user_corrections:
        corrections = load_corrections(app_root)
    return _train_superbrain_model(
        app_root=app_root,
        seed_bank=seed_bank,
        corrections=corrections,
        extra_labels=list(TAG_CATALOG.get("all_tags") or []) + list(ULTRABRAIN_OUTPUT_LABELS or []) + list(STUDENT_OUTPUT_LABELS or []),
        target_multiplier=int(augmentation_multiplier),
        max_memory_rows=5000,
    )


def load_turbothinker_superbrain_summary(app_root: Path) -> Dict[str, Any]:
    if superbrain_summary is None:
        return {"exists": False, "error": "TurboThinker SuperBrain module unavailable"}
    return superbrain_summary(app_root)


def apply_superbrain_memory(app_root: Path, analysis: Dict[str, Any], blend: float = 0.78) -> Dict[str, Any]:
    """Blend v5.1 SuperBrain scores into an analysis prediction.

    This is intentionally applied after rule reader, v4.9 Student, and v5.0
    UltraBrain. It favors local teacher corrections, then visual memory/capsules,
    while keeping multi-preview first-tag logic safe.
    """
    try:
        if load_superbrain_model is None or predict_superbrain_vector is None:
            return analysis
        model = load_superbrain_model(app_root)
        if not model:
            return analysis
        pred = dict(analysis.get("prediction") or {})
        features = analysis.get("features") or {}
        thinker = analysis.get("turbothinker") or {}
        qv = _feature_vector(features)
        base_scores = {str(k): float(v) for k, v in (pred.get("scores") or {}).items()}
        super_out = predict_superbrain_vector(model, qv, base_scores=base_scores, k=36)
        super_scores = {str(k): float(v) for k, v in (super_out.get("scores") or {}).items()}
        if not super_scores:
            return analysis
        scores = dict(base_scores)
        for label, score in super_scores.items():
            label = str(label)
            if not label:
                continue
            old = float(scores.get(label, 0.0))
            scores[label] = max(old, min(0.997, old * (1.0 - blend) + score * blend))
        regions = int(features.get("estimated_region_count") or thinker.get("estimated_region_count") or 1)
        image_mode = str(thinker.get("image_mode") or pred.get("image_mode") or "")
        if image_mode == "multi_design_preview" or regions >= 4 or "multi_design_preview" in (pred.get("tags") or []):
            scores["multi_design_preview"] = max(float(scores.get("multi_design_preview", 0.0)), 0.78)
        sorted_scores = sorted(scores.items(), key=lambda kv: float(kv[1]), reverse=True)
        best_label, best_score = sorted_scores[0]
        if "multi_design_preview" in scores and (image_mode == "multi_design_preview" or regions >= 4):
            best_label = "multi_design_preview"
            best_score = scores.get("multi_design_preview", best_score)
        secondary = [label for label, score in sorted_scores if label != best_label and float(score) >= 0.30][:12]
        super_tags = [label for label, score in sorted(super_scores.items(), key=lambda kv: kv[1], reverse=True) if score >= 0.36][:16]
        image_mode_final = "multi_design_preview" if best_label == "multi_design_preview" or "multi_design_preview" in super_tags else image_mode
        tags = ordered_unique_tags(
            list(pred.get("tags") or []) + super_tags,
            scores=scores,
            primary=best_label,
            image_mode=image_mode_final,
            limit=26,
            keep_engine_tags=True,
        )
        pred.update({
            "predicted_type": best_label if float(best_score) >= 0.30 else pred.get("predicted_type", "unknown_review"),
            "confidence": int(round(min(0.995, max(0.12, float(best_score))) * 100)),
            "secondary_types": secondary,
            "scores": {k: round(float(v), 4) for k, v in scores.items()},
            "tags": tags,
            "search_groups": candidate_search_groups(best_label, secondary),
            "superbrain_used": True,
            "superbrain_version": model.get("version"),
            "superbrain_model_path": str(superbrain_model_path(app_root)) if superbrain_model_path is not None else "",
            "superbrain_label_probabilities": {k: round(float(v), 4) for k, v in sorted(super_scores.items(), key=lambda kv: float(kv[1]), reverse=True)[:22]},
            "superbrain_neighbors": super_out.get("neighbors") or [],
            "superbrain_failure_notes": super_out.get("failure_notes") or [],
            "image_mode": image_mode_final,
        })
        pred["reason"] = explain_prediction(features, pred, thinker)
        pred["reason"] = list(pred.get("reason") or []) + list(super_out.get("reason") or []) + [
            "v5.1 SuperBrain used a larger local multi-cortex model with teacher-correction priority, capsules, KNN memory, and failure diagnosis; filenames are not used as labels."
        ]
        analysis = dict(analysis)
        analysis["prediction"] = pred
        analysis["superbrain"] = {
            "used": True,
            "version": model.get("version"),
            "created_at": model.get("created_at"),
            "training_summary": model.get("training_summary") or {},
            "neighbors_used": len(super_out.get("neighbors") or []),
            "failure_notes": super_out.get("failure_notes") or [],
        }
        return analysis
    except Exception as exc:
        analysis = dict(analysis)
        pred = dict(analysis.get("prediction") or {})
        pred.setdefault("superbrain_warning", str(exc)[:180])
        analysis["prediction"] = pred
        return analysis

def apply_seed_training_memory(app_root: Path, analysis: Dict[str, Any], max_rows: int = 1200) -> Dict[str, Any]:
    """Use the visual seed bank as a gentle nearest-neighbor stabilizer.

    User corrections remain stronger than this auto seed memory; this only nudges
    scores when the query is visually close to many seed examples.
    """
    try:
        bank = load_seed_training_bank(app_root)
        rows = list(bank.get("rows") or [])[-max_rows:]
        if not rows:
            return analysis
        pred = dict(analysis.get("prediction") or {})
        features = analysis.get("features") or {}
        qv = _feature_vector(features)
        scores = dict(pred.get("scores") or {})
        matches: List[Dict[str, Any]] = []
        for row in rows:
            label = str(row.get("predicted_type") or "")
            if label not in IMGS_LABELS:
                continue
            vec = row.get("feature_vector") or []
            if not vec:
                continue
            dist = _vector_distance(qv, [float(v) for v in vec])
            sim = max(0.0, 1.0 - dist)
            if sim >= 0.82:
                boost = min(0.08, (sim - 0.80) * 0.20)
                scores[label] = float(scores.get(label, 0.0)) + boost
                matches.append({"sample_id": row.get("sample_id"), "predicted_type": label, "distance": round(dist, 4), "similarity": round(sim, 4)})
        if not matches:
            return analysis
        sorted_scores = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        best_label, best_score = sorted_scores[0]
        secondary = [label for label, score in sorted_scores[1:7] if score >= 0.24 and label != best_label]
        pred.update({
            "predicted_type": best_label if best_score >= 0.28 else "unknown_review",
            "confidence": int(round(min(0.98, max(0.15, best_score)) * 100)),
            "secondary_types": secondary,
            "scores": {k: round(float(v), 4) for k, v in scores.items()},
            "tags": _tags_from_features(features, best_label, secondary),
            "search_groups": candidate_search_groups(best_label, secondary),
            "learned_from_seed_bank": True,
            "nearest_seed_rows": sorted(matches, key=lambda m: m["distance"])[:5],
        })
        pred["reason"] = explain_prediction(features, pred, analysis.get("turbothinker") or {})
        analysis = dict(analysis)
        analysis["prediction"] = pred
        return analysis
    except Exception:
        return analysis


def analyze_selector_area(img: Image.Image, source_name: str = "selector_crop", box: Optional[Tuple[int, int, int, int]] = None) -> Dict[str, Any]:
    rgb = _to_rgb(img)
    crop_box = None
    if box:
        w, h = rgb.size
        x0, y0, x1, y1 = [int(v) for v in box]
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(w, max(x0 + 1, x1)), min(h, max(y0 + 1, y1))
        rgb = rgb.crop((x0, y0, x1, y1))
        crop_box = [x0, y0, x1, y1]
    analysis = analyze_image_for_training(rgb, source_name)
    f = analysis.get("features") or {}
    pred = analysis.get("prediction") or {}
    tags: List[str] = []
    reasons: List[str] = []
    density = float(f.get("ink_density") or 0.0)
    edge = float(f.get("edge_strength") or 0.0)
    net = float(f.get("net_score") or 0.0)
    scattered = float(f.get("scattered_score") or 0.0)
    comps = int(f.get("component_count") or 0)
    aspect = float(f.get("aspect") or 1.0)
    coverage = float(f.get("ink_coverage") or 0.0)
    if density > 0.17:
        tags.append("heavy_work")
        reasons.append(f"heavy_work because embroidery foreground density is high ({density:.3f}).")
    if net > 0.34:
        tags.append("net_work")
        reasons.append(f"net_work because repeated row/column line peaks and edge patterns are strong (net score {net:.2f}).")
    if edge > max(0.11, density * 1.45):
        tags.extend(["cut_work", "heavy_outline"] if density < 0.17 else ["heavy_outline"])
        reasons.append(f"heavy_outline/cut_work because edge strength ({edge:.2f}) is high compared with density.")
    if scattered > 0.38 or comps >= 24:
        tags.extend(["flowers", "butti"])
        reasons.append(f"flowers/butti because many separated components are present ({comps}).")
    if (scattered > 0.30 or comps >= 16) and aspect > 1.25:
        tags.append("flower_border")
        reasons.append("flower_border because repeated separated components are spread along a wide/curved panel.")
    if aspect > 1.75:
        tags.extend(["border", "hand_lines"])
        reasons.append("border/hand_lines because the selected crop is a wide horizontal strip.")
    elif aspect < 0.72:
        tags.extend(["full_hand", "hand_design"])
        reasons.append("full_hand/hand_design because the selected crop is tall and panel-like.")
    if coverage > 0.42 and density > 0.11:
        tags.append("all_over_design")
        reasons.append(f"all_over_design because useful stitches cover a broad area ({coverage:.2f}).")
    if not tags:
        tags.append(str(pred.get("predicted_type") or "unknown_review"))
        reasons.extend((pred.get("reason") or [])[:2])
    selector_primary = str(pred.get("predicted_type") or "")
    if selector_primary == "multi_design_preview":
        selector_primary = ""
    tags = ordered_unique_tags(tags, scores=pred.get("scores") or {}, primary=selector_primary, image_mode="", limit=12, keep_engine_tags=False)
    tags = [t for t in tags if t != "multi_design_preview"] or ["unknown_review"]
    return {
        "crop_box": crop_box,
        "source_name": source_name,
        "analysis": analysis,
        "selector_tags": tags,
        "selector_reasons": reasons[:8],
        "created_at": utc_now(),
    }


def record_selector_area_training(
    app_root: Path,
    parent_sample_id: str,
    source_name: str,
    selector_result: Dict[str, Any],
    crop_image_path: Optional[str] = None,
    final_tags: Optional[Iterable[str]] = None,
    notes: str = "",
) -> Dict[str, Any]:
    paths = ensure_training_dirs(app_root)
    box = selector_result.get("crop_box") or []
    raw = f"{parent_sample_id}|{source_name}|{box}|{time.time()}".encode("utf-8")
    area_id = hashlib.sha256(raw).hexdigest()[:18]
    final = ordered_unique_tags(list(final_tags or []) + list(selector_result.get("selector_tags") or []), limit=18, keep_engine_tags=False)
    record = {
        "area_id": area_id,
        "parent_sample_id": parent_sample_id,
        "source_name": source_name,
        "crop_box": box,
        "crop_image_path": crop_image_path,
        "selector_tags": selector_result.get("selector_tags") or [],
        "final_tags": final,
        "notes": notes,
        "features": ((selector_result.get("analysis") or {}).get("features") or {}),
        "reason": selector_result.get("selector_reasons") or [],
        "created_at": utc_now(),
    }
    log_path = training_root(app_root) / "selector_training.json"
    data = _read_json(log_path, {"version": IMGS_TRAINING_VERSION, "areas": []})
    areas = list(data.get("areas") or [])
    areas.append(record)
    data["areas"] = areas[-2500:]
    _write_json(log_path, data)
    _write_json(paths["crops"] / f"{area_id}.json", record)
    return record

def summarize_training(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    counts: Dict[str, int] = {label: 0 for label in IMGS_LABELS}
    trained = 0
    for item in items:
        train = item.get("imgs_training") or {}
        label = str(train.get("predicted_type") or "unknown_review")
        if label not in counts:
            label = "unknown_review"
        counts[label] += 1
        if train.get("status") == "trained":
            trained += 1
    return {
        "trained": trained,
        "total": len(items),
        "counts": {k: v for k, v in counts.items() if v},
        "engine": IMGS_TRAINING_VERSION,
        "turbothinker_engine": TURBOTHINKER_ENGINE_VERSION,
        "warning": IMGS_TRAINING_WARNING,
    }


def load_cached_fingerprint(path_value: Any) -> Optional[Dict[str, Any]]:
    try:
        if not path_value:
            return None
        path = Path(str(path_value))
        data = _read_json(path, None)
        return data if isinstance(data, dict) else None
    except Exception:
        return None

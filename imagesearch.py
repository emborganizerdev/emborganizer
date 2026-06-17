"""
imagesearch.py
EMBORGANIZER Image Searcher similarity core.

v0.8.4 introduces IMGS Engine: first-stage heavy verification for the
Image Searcher. TURBOEMB creates the preview; IMGS verifies it.

IMGS Engine goals:
- one best file, not a confusing result list
- parallel file-level scoring from saved TURBOEMB preview fingerprints
- deeper shape/edge/block/center/contour verification
- strong false-positive guards for sparse embroidery designs
- pure local CPU operation: no external API, no paid model, no GPU
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, List, Any, Tuple, Iterable

from PIL import Image, ImageOps, ImageFilter, ImageStat

IMGS_ENGINE_NAME = "IMGS Engine"
IMGS_ENGINE_VERSION = "IMGS v0.8.4 First Stage Accuracy Engine"
IMAGE_SEARCH_VERSION = "emborganizer-imgs-v0.8.4-first-stage-heavy-verification"

# 4x4 merged rectangles are strong for embroidery motifs.
BLOCK_GRID = 4
# 8x8 micro regions catch partial matches without making the JSON too large.
MICRO_GRID = 8
BLOCK_AREAS = {1, 2, 3, 4, 8, 16}

# These weights were tuned for stitch-preview style images: shape matters more than color.
BLOCK_WEIGHTS = {
    "1": 0.12,
    "2": 0.14,
    "3": 0.10,
    "4": 0.18,
    "8": 0.18,
    "16": 0.18,
}


def _clamp01(v: float) -> float:
    if v < 0:
        return 0.0
    if v > 1:
        return 1.0
    return float(v)


def _to_rgb(img: Image.Image) -> Image.Image:
    if img.mode in ("RGBA", "LA"):
        bg = Image.new("RGB", img.size, "white")
        rgba = img.convert("RGBA")
        bg.paste(rgba, mask=rgba.split()[-1])
        return bg
    return img.convert("RGB")


def _background_aware_bbox(img: Image.Image) -> Tuple[int, int, int, int] | None:
    """Find non-background bounds quickly and robustly.

    The generated previews usually have white/light backgrounds, but uploaded query
    images may be screenshots, photos, or transparent PNGs. This detects both dark
    stitches and colorful thread against a mostly light background.
    """
    img = _to_rgb(img)
    w, h = img.size
    if w <= 2 or h <= 2:
        return None

    # Scan a limited-size copy for speed, then scale bbox back up.
    scan_max = 560
    scale = min(1.0, scan_max / max(w, h))
    if scale < 1.0:
        small = img.resize((max(2, int(w * scale)), max(2, int(h * scale))), Image.Resampling.BILINEAR)
    else:
        small = img
    sw, sh = small.size
    gray = ImageOps.grayscale(small)
    gpix = gray.load()
    spix = small.load()

    xs: List[int] = []
    ys: List[int] = []
    # Step 1 is accurate enough on the small scan image.
    for y in range(sh):
        for x in range(sw):
            r, g, b = spix[x, y]
            lum = gpix[x, y]
            spread = max(r, g, b) - min(r, g, b)
            # Dark/colored/non-gray pixels are considered design ink.
            if lum < 242 or spread > 22:
                xs.append(x)
                ys.append(y)

    if not xs or not ys:
        return None

    left_s, right_s = min(xs), max(xs)
    top_s, bottom_s = min(ys), max(ys)
    if right_s <= left_s or bottom_s <= top_s:
        return None

    inv = 1.0 / scale
    pad = max(8, int(min(w, h) * 0.055))
    left = max(0, int(left_s * inv) - pad)
    top = max(0, int(top_s * inv) - pad)
    right = min(w, int((right_s + 1) * inv) + pad)
    bottom = min(h, int((bottom_s + 1) * inv) + pad)
    if right <= left or bottom <= top:
        return None
    return left, top, right, bottom


def _crop_background(img: Image.Image) -> Image.Image:
    bbox = _background_aware_bbox(img)
    return _to_rgb(img).crop(bbox) if bbox else _to_rgb(img)


def normalize_image(img: Image.Image, size: int = 384, crop: bool = True) -> Image.Image:
    if crop:
        img = _crop_background(img)
    img = _to_rgb(img)
    canvas = Image.new("RGB", (size, size), "white")
    # Leave a small margin so near-border stitches compare consistently.
    margin = max(8, int(size * 0.035))
    img.thumbnail((size - margin * 2, size - margin * 2), Image.Resampling.LANCZOS)
    canvas.paste(img, ((size - img.width) // 2, (size - img.height) // 2))
    return canvas


def _hash_bits(values: Iterable[float], threshold: float) -> str:
    return "".join("1" if v > threshold else "0" for v in values)


def _average_hash(img: Image.Image, n: int = 32) -> str:
    gray = ImageOps.grayscale(img.resize((n, n), Image.Resampling.BILINEAR))
    vals = list(gray.getdata())
    avg = sum(vals) / max(1, len(vals))
    return _hash_bits(vals, avg)


def _difference_hash(img: Image.Image, n: int = 32) -> str:
    gray = ImageOps.grayscale(img.resize((n + 1, n), Image.Resampling.BILINEAR))
    vals = list(gray.getdata())
    bits = []
    stride = n + 1
    for y in range(n):
        base = y * stride
        for x in range(n):
            bits.append("1" if vals[base + x] > vals[base + x + 1] else "0")
    return "".join(bits)


def _edge_hash(img: Image.Image, n: int = 32) -> str:
    edges = ImageOps.grayscale(img).filter(ImageFilter.FIND_EDGES).resize((n, n), Image.Resampling.BILINEAR)
    vals = list(edges.getdata())
    avg = sum(vals) / max(1, len(vals))
    return _hash_bits(vals, avg)


def _ink_grid(img: Image.Image, grid: int = 16) -> List[float]:
    """Fast silhouette density grid.

    Uses one resize to grid x grid instead of cropping every cell, so it is quick
    for hundreds of comparisons.
    """
    gray = ImageOps.grayscale(img.resize((grid, grid), Image.Resampling.BILINEAR))
    vals = list(gray.getdata())
    return [round((255.0 - v) / 255.0, 6) for v in vals]


def _edge_grid_fast(img: Image.Image, grid: int = 16) -> List[float]:
    edges = ImageOps.grayscale(img).filter(ImageFilter.FIND_EDGES).resize((grid, grid), Image.Resampling.BILINEAR)
    vals = list(edges.getdata())
    return [round(v / 255.0, 6) for v in vals]


def _edge_grid(img: Image.Image, grid: int = 8) -> List[float]:
    return _edge_grid_fast(img, grid)


def _bits_from_ink_values(vals: Iterable[float], threshold: float = 0.08) -> str:
    return "".join("1" if float(v) > threshold else "0" for v in vals)


def _mask_bits(img: Image.Image, n: int = 32) -> str:
    return _bits_from_ink_values(_ink_grid(img, n), 0.065)


def _edge_bits(img: Image.Image, n: int = 32) -> str:
    return _bits_from_ink_values(_edge_grid_fast(img, n), 0.045)


def _projection_profile(img: Image.Image, bins: int = 48) -> List[float]:
    gray = ImageOps.grayscale(img.resize((bins, bins), Image.Resampling.BILINEAR))
    pix = list(gray.getdata())
    rows: List[float] = []
    cols: List[float] = []
    denom = 255.0 * bins
    for y in range(bins):
        rows.append(round(sum((255 - pix[y * bins + x]) for x in range(bins)) / denom, 6))
    for x in range(bins):
        cols.append(round(sum((255 - pix[y * bins + x]) for y in range(bins)) / denom, 6))
    return rows + cols


def _radial_profile(img: Image.Image, bins: int = 32, angles: int = 24) -> List[float]:
    gray = ImageOps.grayscale(img.resize((160, 160), Image.Resampling.BILINEAR))
    pix = gray.load()
    cx = cy = 80
    max_r = 78
    result: List[float] = []
    # Fewer rays than old versions: almost same accuracy, much faster.
    step = max(2, max_r // max(1, bins))
    for a in range(angles):
        theta = (2.0 * math.pi * a) / angles
        samples = []
        ct = math.cos(theta)
        st = math.sin(theta)
        for r in range(4, max_r, step):
            x = int(cx + ct * r)
            y = int(cy + st * r)
            if 0 <= x < 160 and 0 <= y < 160:
                samples.append((255 - pix[x, y]) / 255.0)
        result.append(round(sum(samples) / len(samples), 6) if samples else 0.0)
    return result


def _color_histogram(img: Image.Image, colors: int = 24, size: int = 64) -> List[float]:
    small = img.resize((size, size), Image.Resampling.BILINEAR).quantize(colors=colors).convert("RGB")
    hist = small.histogram()
    total = sum(hist) or 1
    return [round(v / total, 8) for v in hist]


def _shape_moments(img: Image.Image, size: int = 64) -> List[float]:
    """Compact silhouette features: density, centroid, spread, covariance, symmetry."""
    gray = ImageOps.grayscale(img.resize((size, size), Image.Resampling.BILINEAR))
    vals = list(gray.getdata())
    mass = 0.0
    sx = sy = 0.0
    for y in range(size):
        base = y * size
        for x in range(size):
            ink = (255.0 - vals[base + x]) / 255.0
            # suppress very light noise
            if ink < 0.035:
                continue
            mass += ink
            sx += x * ink
            sy += y * ink
    if mass <= 1e-6:
        return [0.0] * 12
    cx = sx / mass
    cy = sy / mass
    varx = vary = cov = 0.0
    minx = miny = size
    maxx = maxy = 0
    left_mass = right_mass = top_mass = bottom_mass = 0.0
    mirror_diff_h = mirror_diff_v = 0.0
    for y in range(size):
        base = y * size
        for x in range(size):
            ink = (255.0 - vals[base + x]) / 255.0
            if ink < 0.035:
                ink = 0.0
            if ink:
                dx = x - cx
                dy = y - cy
                varx += dx * dx * ink
                vary += dy * dy * ink
                cov += dx * dy * ink
                if x < minx: minx = x
                if x > maxx: maxx = x
                if y < miny: miny = y
                if y > maxy: maxy = y
                if x < cx: left_mass += ink
                else: right_mass += ink
                if y < cy: top_mass += ink
                else: bottom_mass += ink
    # Symmetry checks on small grid.
    for y in range(size):
        for x in range(size // 2):
            a = (255.0 - vals[y * size + x]) / 255.0
            b = (255.0 - vals[y * size + (size - 1 - x)]) / 255.0
            mirror_diff_h += abs(a - b)
    for y in range(size // 2):
        for x in range(size):
            a = (255.0 - vals[y * size + x]) / 255.0
            b = (255.0 - vals[(size - 1 - y) * size + x]) / 255.0
            mirror_diff_v += abs(a - b)
    varx /= mass
    vary /= mass
    cov /= mass
    bbox_w = max(1, maxx - minx + 1)
    bbox_h = max(1, maxy - miny + 1)
    return [
        round(_clamp01(mass / (size * size)), 6),
        round(cx / max(1, size - 1), 6),
        round(cy / max(1, size - 1), 6),
        round(_clamp01(varx / (size * size)), 6),
        round(_clamp01(vary / (size * size)), 6),
        round(max(-1.0, min(1.0, cov / (size * size))), 6),
        round(_clamp01(bbox_w / size), 6),
        round(_clamp01(bbox_h / size), 6),
        round(_clamp01(bbox_w / max(1, bbox_h) / 4.0), 6),
        round(abs(left_mass - right_mass) / max(1e-6, mass), 6),
        round(abs(top_mass - bottom_mass) / max(1e-6, mass), 6),
        round(_clamp01((mirror_diff_h + mirror_diff_v) / (size * size)), 6),
    ]


def _center_focus_grid(img: Image.Image, grid: int = 14) -> List[float]:
    """Center-weighted fingerprint for embroidery motifs.

    A lot of embroidery designs share empty borders. The useful identity is often
    in the middle object/flower/logo. This extracts only the center crop so the
    engine verifies that the core of the design truly matches.
    """
    w, h = img.size
    crop_margin = max(1, int(min(w, h) * 0.20))
    crop = img.crop((crop_margin, crop_margin, w - crop_margin, h - crop_margin))
    return _ink_grid(crop, grid) + _edge_grid_fast(crop, grid)


def _ring_sector_profile(img: Image.Image, rings: int = 6, sectors: int = 16, size: int = 128) -> List[float]:
    """Radial density profile: verifies outer/inner layout and symmetry.

    This catches cases where two designs have similar total ink but the actual
    design mass is placed differently around the center.
    """
    gray = ImageOps.grayscale(img.resize((size, size), Image.Resampling.BILINEAR))
    vals = list(gray.getdata())
    cx = cy = (size - 1) / 2.0
    max_r = max(1.0, math.sqrt(cx * cx + cy * cy))
    sums = [[0.0 for _ in range(sectors)] for _ in range(rings)]
    counts = [[0 for _ in range(sectors)] for _ in range(rings)]
    for y in range(size):
        base = y * size
        dy = y - cy
        for x in range(size):
            ink = (255.0 - vals[base + x]) / 255.0
            if ink < 0.025:
                continue
            dx = x - cx
            r_idx = min(rings - 1, int((math.sqrt(dx * dx + dy * dy) / max_r) * rings))
            theta = (math.atan2(dy, dx) + math.pi) / (2.0 * math.pi)
            s_idx = min(sectors - 1, int(theta * sectors))
            sums[r_idx][s_idx] += ink
            counts[r_idx][s_idx] += 1
    out: List[float] = []
    for r in range(rings):
        for c in range(sectors):
            out.append(round(sums[r][c] / max(1, counts[r][c]), 6))
    return out


def _contour_signature(img: Image.Image, angles: int = 48, size: int = 128) -> List[float]:
    """Outer-shape signature from the center to the first/last ink on each ray."""
    gray = ImageOps.grayscale(img.resize((size, size), Image.Resampling.BILINEAR))
    pix = gray.load()
    cx = cy = (size - 1) / 2.0
    max_r = size * 0.70
    result: List[float] = []
    for a in range(angles):
        theta = (2.0 * math.pi * a) / angles
        ct, st = math.cos(theta), math.sin(theta)
        first = None
        last = 0.0
        # march outward along the ray
        for step in range(1, int(max_r)):
            x = int(round(cx + ct * step))
            y = int(round(cy + st * step))
            if not (0 <= x < size and 0 <= y < size):
                break
            ink = (255 - pix[x, y]) / 255.0
            if ink > 0.055:
                if first is None:
                    first = step / max_r
                last = step / max_r
        # Store outer distance; add a small first-ink hint to separate hollow shapes.
        inner = first if first is not None else 0.0
        result.append(round((last * 0.72) + (inner * 0.28), 6))
    return result


def _imgs_detail_fingerprint(norm: Image.Image) -> Dict[str, Any]:
    """Extra IMGS verification vectors added on top of the old search fingerprint."""
    return {
        "imgs_ink_grid_20": _ink_grid(norm, 20),
        "imgs_edge_grid_20": _edge_grid_fast(norm, 20),
        "imgs_center_focus": _center_focus_grid(norm, 14),
        "imgs_ring_sector": _ring_sector_profile(norm, 6, 16, 128),
        "imgs_contour": _contour_signature(norm, 48, 128),
    }


def _global_fingerprint(norm: Image.Image) -> Dict[str, Any]:
    ink16 = _ink_grid(norm, 16)
    edge16 = _edge_grid_fast(norm, 16)
    ink8 = _ink_grid(norm, 8)
    edge8 = _edge_grid_fast(norm, 8)
    projection = _projection_profile(norm, 48)
    radial = _radial_profile(norm, 32, 24)
    moments = _shape_moments(norm, 64)
    # fast_vec is the first-pass vector. It is intentionally compact and JSON-friendly.
    fast_vec = ink16 + edge16 + projection + radial + moments
    coarse_vec = ink8 + edge8 + _projection_profile(norm, 24) + moments
    detail = _imgs_detail_fingerprint(norm)
    base = {
        "ahash": _average_hash(norm, 32),
        "dhash": _difference_hash(norm, 32),
        "ehash": _edge_hash(norm, 32),
        "edge_grid": edge8,
        "ink_grid_16": ink16,
        "edge_grid_16": edge16,
        "mask_bits_32": _mask_bits(norm, 32),
        "edge_bits_32": _edge_bits(norm, 32),
        "projection": projection,
        "radial": radial,
        "moments": moments,
        "hist": _color_histogram(norm, 24, 64),
        "fast_vec": [round(v, 6) for v in fast_vec],
        "coarse_vec": [round(v, 6) for v in coarse_vec],
    }
    base.update(detail)
    return base


def _region_fingerprint(img: Image.Image, area: int, bbox: Tuple[int, int, int, int]) -> Dict[str, Any]:
    # Region search uses a smaller image and compact features for speed.
    norm = normalize_image(img, 160, crop=True)
    ink8 = _ink_grid(norm, 8)
    edge8 = _edge_grid_fast(norm, 8)
    projection = _projection_profile(norm, 16)
    moments = _shape_moments(norm, 32)
    vec = ink8 + edge8 + projection + moments
    return {
        "area": int(area),
        "bbox": list(bbox),
        "dhash": _difference_hash(norm, 12),
        "ehash": _edge_hash(norm, 12),
        "mask_bits": _mask_bits(norm, 16),
        "edge_bits": _edge_bits(norm, 16),
        "vec": [round(v, 6) for v in vec],
        "moments": moments,
    }


def _micro_fingerprint(img: Image.Image, bbox: Tuple[int, int, int, int]) -> Dict[str, Any]:
    # Extremely compact, because 64x64 comparisons are used a lot.
    norm = normalize_image(img, 96, crop=True)
    vec = _ink_grid(norm, 6) + _edge_grid_fast(norm, 6) + _shape_moments(norm, 24)
    return {"area": 1, "bbox": list(bbox), "mask_bits": _mask_bits(norm, 12), "edge_bits": _edge_bits(norm, 12), "vec": [round(v, 6) for v in vec]}


def _block_region_specs(grid: int = BLOCK_GRID) -> List[Tuple[int, int, int, int, int]]:
    specs: List[Tuple[int, int, int, int, int]] = []
    for h in range(1, grid + 1):
        for w in range(1, grid + 1):
            area = h * w
            if area not in BLOCK_AREAS:
                continue
            for y in range(0, grid - h + 1):
                for x in range(0, grid - w + 1):
                    specs.append((x, y, w, h, area))
    # Larger merged regions early help detect whole motifs; small parts still remain.
    specs.sort(key=lambda s: (s[4], s[1], s[0], s[3], s[2]))
    return specs


def _block_fingerprints(norm: Image.Image) -> Dict[str, List[Dict[str, Any]]]:
    size = norm.size[0]
    cell = size // BLOCK_GRID
    groups: Dict[str, List[Dict[str, Any]]] = {str(a): [] for a in sorted(BLOCK_AREAS)}
    for x, y, w, h, area in _block_region_specs(BLOCK_GRID):
        left = x * cell
        top = y * cell
        right = size if x + w == BLOCK_GRID else (x + w) * cell
        bottom = size if y + h == BLOCK_GRID else (y + h) * cell
        crop = norm.crop((left, top, right, bottom))
        groups[str(area)].append(_region_fingerprint(crop, area, (x, y, w, h)))
    return groups


def _micro_block_fingerprints(norm: Image.Image) -> List[Dict[str, Any]]:
    size = norm.size[0]
    cell = size // MICRO_GRID
    micros: List[Dict[str, Any]] = []
    for y in range(MICRO_GRID):
        for x in range(MICRO_GRID):
            left = x * cell
            top = y * cell
            right = size if x + 1 == MICRO_GRID else (x + 1) * cell
            bottom = size if y + 1 == MICRO_GRID else (y + 1) * cell
            crop = norm.crop((left, top, right, bottom))
            micros.append(_micro_fingerprint(crop, (x, y, 1, 1)))
    return micros


def create_fingerprint_from_image(img: Image.Image) -> Dict[str, Any]:
    norm = normalize_image(img, 384, crop=True)
    fp = _global_fingerprint(norm)
    fp.update({
        "version": IMAGE_SEARCH_VERSION,
        "algorithm": "IMGS v0.8.4 heavy verification: fast vector + silhouette + merged blocks + center/contour/ring checks",
        "block_grid": BLOCK_GRID,
        "micro_grid": MICRO_GRID,
        "block_areas": sorted(BLOCK_AREAS),
        "blocks": _block_fingerprints(norm),
        "micro_blocks": _micro_block_fingerprints(norm),
    })
    return fp


def create_fingerprint_from_path(path: str | Path) -> Dict[str, Any]:
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img)
        return create_fingerprint_from_image(img)


def _hamming(a: str, b: str) -> float:
    if not a or not b:
        return 1.0
    n = min(len(a), len(b))
    if n == 0:
        return 1.0
    diff = sum(1 for i in range(n) if a[i] != b[i])
    diff += abs(len(a) - len(b))
    return diff / max(len(a), len(b))


def _jaccard_bits(a: str, b: str) -> float:
    """Jaccard distance for foreground bits. Better than hamming for sparse embroidery outlines."""
    if not a or not b:
        return 1.0
    n = min(len(a), len(b))
    inter = union = 0
    for i in range(n):
        av = a[i] == "1"
        bv = b[i] == "1"
        if av or bv:
            union += 1
            if av and bv:
                inter += 1
    if union == 0:
        return 0.0
    return 1.0 - (inter / union)


def _l1(a: List[float], b: List[float]) -> float:
    if not a or not b:
        return 1.0
    n = min(len(a), len(b))
    if n == 0:
        return 1.0
    # Manual loop is faster than creating temporary lists.
    total = 0.0
    for i in range(n):
        total += abs(float(a[i]) - float(b[i]))
    return min(1.0, total / n)


def _hist_l1(a: List[float], b: List[float]) -> float:
    if not a or not b:
        return 1.0
    n = min(len(a), len(b))
    if n == 0:
        return 1.0
    total = 0.0
    for i in range(n):
        total += abs(float(a[i]) - float(b[i]))
    return min(1.0, total / 2.0)


def _vector_score(a: List[float], b: List[float]) -> float:
    return max(0.0, min(100.0, 100.0 * (1.0 - _l1(a, b))))


def _feature_distance(query: Dict[str, Any], target: Dict[str, Any]) -> float:
    # New fast path: use compact vectors and then add shape-aware stabilizers.
    qfast = query.get("fast_vec") or []
    tfast = target.get("fast_vec") or []
    if qfast and tfast:
        fast = _l1(qfast, tfast)
        coarse = _l1(query.get("coarse_vec", []), target.get("coarse_vec", []))
        dh = _hamming(query.get("dhash", ""), target.get("dhash", ""))
        eh = _hamming(query.get("ehash", ""), target.get("ehash", ""))
        ink = _l1(query.get("ink_grid_16", []), target.get("ink_grid_16", []))
        edge = _l1(query.get("edge_grid_16", []), target.get("edge_grid_16", []))
        mom = _l1(query.get("moments", []), target.get("moments", []))
        ch = _hist_l1(query.get("hist", []), target.get("hist", []))
        mask = _jaccard_bits(query.get("mask_bits_32", ""), target.get("mask_bits_32", ""))
        edge_bits = _jaccard_bits(query.get("edge_bits_32", ""), target.get("edge_bits_32", ""))
        return (
            fast * 0.18 +
            coarse * 0.07 +
            dh * 0.05 +
            eh * 0.07 +
            ink * 0.07 +
            edge * 0.08 +
            mom * 0.06 +
            ch * 0.02 +
            mask * 0.24 +
            edge_bits * 0.16
        )

    # Backward-compatible path for older fingerprints.
    ah = _hamming(query.get("ahash", ""), target.get("ahash", ""))
    dh = _hamming(query.get("dhash", ""), target.get("dhash", ""))
    eh = _hamming(query.get("ehash", ""), target.get("ehash", ""))
    eg = _l1(query.get("edge_grid", []), target.get("edge_grid", []))
    pp = _l1(query.get("projection", []), target.get("projection", []))
    rp = _l1(query.get("radial", []), target.get("radial", []))
    ch = _hist_l1(query.get("hist", []), target.get("hist", []))
    return ah * 0.06 + dh * 0.18 + eh * 0.23 + eg * 0.18 + pp * 0.17 + rp * 0.13 + ch * 0.05


def _feature_score(query: Dict[str, Any], target: Dict[str, Any]) -> float:
    return max(0.0, min(100.0, 100.0 * (1.0 - _feature_distance(query, target))))


def _legacy_parts(query: Dict[str, Any], target: Dict[str, Any]) -> Dict[str, float]:
    ah = _hamming(query.get("ahash", ""), target.get("ahash", ""))
    dh = _hamming(query.get("dhash", ""), target.get("dhash", ""))
    eh = _hamming(query.get("ehash", ""), target.get("ehash", ""))
    eg = _l1(query.get("edge_grid_16", query.get("edge_grid", [])), target.get("edge_grid_16", target.get("edge_grid", [])))
    pp = _l1(query.get("projection", []), target.get("projection", []))
    rp = _l1(query.get("radial", []), target.get("radial", []))
    ch = _hist_l1(query.get("hist", []), target.get("hist", []))
    mom = _l1(query.get("moments", []), target.get("moments", []))
    mask = _jaccard_bits(query.get("mask_bits_32", ""), target.get("mask_bits_32", ""))
    edge_bits = _jaccard_bits(query.get("edge_bits_32", ""), target.get("edge_bits_32", ""))
    return {
        "shape_hash": round((1 - ((dh + eh) / 2)) * 100, 2),
        "edge_layout": round((1 - eg) * 100, 2),
        "projection": round((1 - pp) * 100, 2),
        "radial": round((1 - rp) * 100, 2),
        "moments": round((1 - mom) * 100, 2),
        "mask_overlap": round((1 - mask) * 100, 2),
        "edge_overlap": round((1 - edge_bits) * 100, 2),
        "color": round((1 - ch) * 100, 2),
        "ahash": round((1 - ah) * 100, 2),
    }


def _region_distance(q: Dict[str, Any], t: Dict[str, Any]) -> float:
    qv = q.get("vec") or []
    tv = t.get("vec") or []
    if qv and tv:
        base = _l1(qv, tv)
        # Hashes stabilize local edge direction when present.
        dh = _hamming(q.get("dhash", ""), t.get("dhash", "")) if q.get("dhash") and t.get("dhash") else base
        eh = _hamming(q.get("ehash", ""), t.get("ehash", "")) if q.get("ehash") and t.get("ehash") else base
        mask = _jaccard_bits(q.get("mask_bits", ""), t.get("mask_bits", "")) if q.get("mask_bits") and t.get("mask_bits") else base
        edge_bits = _jaccard_bits(q.get("edge_bits", ""), t.get("edge_bits", "")) if q.get("edge_bits") and t.get("edge_bits") else base
        return base * 0.34 + dh * 0.06 + eh * 0.10 + mask * 0.30 + edge_bits * 0.20
    return _feature_distance(q, t)


def _region_ink_density(region: Dict[str, Any]) -> float:
    moments = region.get("moments") or []
    if moments:
        try:
            return float(moments[0])
        except Exception:
            pass
    vec = region.get("vec") or []
    if not vec:
        return 0.0
    # First part of vec is usually an ink grid. Average only the first half-ish.
    n = min(len(vec), 64)
    return sum(float(v) for v in vec[:n]) / max(1, n)


def _best_region_score(query_regions: List[Dict[str, Any]], target_regions: List[Dict[str, Any]], keep_ratio: float = 0.42) -> Tuple[float, Dict[str, Any]]:
    if not query_regions or not target_regions:
        return 0.0, {}

    # Ignore mostly empty cells. This is critical for embroidery previews because
    # otherwise blank/white regions match perfectly and create false positives.
    q_filtered = [r for r in query_regions if _region_ink_density(r) >= 0.012]
    t_filtered = [r for r in target_regions if _region_ink_density(r) >= 0.012]
    if q_filtered and t_filtered:
        query_regions = q_filtered
        target_regions = t_filtered
    elif not q_filtered or not t_filtered:
        return 0.0, {}

    best_scores: List[float] = []
    best_pair = {"score": 0.0, "query_bbox": None, "target_bbox": None}
    for q in query_regions:
        best_dist = 1.0
        best_target = None
        for t in target_regions:
            dist = _region_distance(q, t)
            if dist < best_dist:
                best_dist = dist
                best_target = t
        score = max(0.0, min(100.0, 100.0 * (1.0 - best_dist)))
        best_scores.append(score)
        if score > best_pair["score"]:
            best_pair = {
                "score": round(score, 2),
                "query_bbox": q.get("bbox"),
                "target_bbox": best_target.get("bbox") if best_target else None,
            }

    best_scores.sort(reverse=True)
    keep = max(1, int(math.ceil(len(best_scores) * keep_ratio)))
    return round(sum(best_scores[:keep]) / keep, 2), best_pair


def _micro_score(query: Dict[str, Any], target: Dict[str, Any], global_score: float) -> Tuple[float, Dict[str, Any]]:
    qmicro = query.get("micro_blocks") or []
    tmicro = target.get("micro_blocks") or []
    if not qmicro or not tmicro:
        return 0.0, {}
    score, pair = _best_region_score(qmicro, tmicro, keep_ratio=0.18)
    # Anti-false-positive guard: a tiny block should not dominate if the global design is unrelated.
    if global_score < 42 and score > 72:
        score = 42 + (score - 42) * 240
    return round(score, 2), pair


def _block_compare_score(query: Dict[str, Any], target: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
    global_score = _feature_score(query, target)
    qblocks = query.get("blocks") or {}
    tblocks = target.get("blocks") or {}
    parts = _legacy_parts(query, target)

    if not qblocks or not tblocks:
        return round(global_score, 2), {
            "mode": "fast-global-backcompat",
            "block_scores": {},
            "best_blocks": {},
            "global_score": round(global_score, 2),
            "micro_score": 0.0,
            "parts": parts,
        }

    block_scores: Dict[str, float] = {}
    best_pairs: Dict[str, Any] = {}
    weighted = 0.0
    total_weight = 0.0

    for area_key, weight in BLOCK_WEIGHTS.items():
        score, pair = _best_region_score(qblocks.get(area_key, []), tblocks.get(area_key, []), keep_ratio=0.45)
        if score <= 0:
            continue
        block_scores[f"{area_key}-block"] = score
        best_pairs[f"{area_key}-block"] = pair
        weighted += score * weight
        total_weight += weight

    block_part = (weighted / total_weight) if total_weight else global_score
    micro, micro_pair = _micro_score(query, target, global_score)
    if micro > 0:
        block_scores["64-micro-block"] = micro
        best_pairs["64-micro-block"] = micro_pair

    # Confidence balancing:
    # - Full layout prevents random parts from winning.
    # - Merged blocks catch same motif shifted/cropped differently.
    # - Micro score helps partial query images.
    if global_score >= 72:
        final = global_score * 0.46 + block_part * 0.38 + micro * 0.16
    elif global_score >= 52:
        final = global_score * 0.38 + block_part * 0.42 + micro * 0.20
    else:
        final = global_score * 0.45 + block_part * 0.40 + micro * 0.15

    # If both full image and merged blocks agree, boost the result.
    agreement = min(global_score, block_part)
    if agreement > 70:
        final += (agreement - 70) * 0.10
    # If only micro is high, avoid overconfidence.
    if micro > 82 and global_score < 45 and block_part < 62:
        final = min(final, 68.0)

    # Strong false-positive guard for sparse outline designs. Hamming/L1 grids can
    # look deceptively high when most of the image is blank. Jaccard foreground
    # overlap catches that and caps unrelated shapes.
    mask_overlap = float(parts.get("mask_overlap", 0.0) or 0.0)
    edge_overlap = float(parts.get("edge_overlap", 0.0) or 0.0)
    if mask_overlap < 20 and edge_overlap < 45:
        final = min(final, 60.0)
    elif mask_overlap < 35 and edge_overlap < 55:
        final = min(final, 70.0)

    return round(max(0.0, min(100.0, final)), 2), {
        "mode": "v0.7.8-fast-global-merged-block-micro",
        "block_scores": {k: round(v, 2) for k, v in block_scores.items()},
        "best_blocks": best_pairs,
        "global_score": round(global_score, 2),
        "block_part": round(block_part, 2),
        "micro_score": round(micro, 2),
        "parts": parts,
    }


def _score_from_vectors(query: Dict[str, Any], target: Dict[str, Any], key: str, default: float) -> float:
    qv = query.get(key) or []
    tv = target.get(key) or []
    if not qv or not tv:
        return float(default)
    return round(_vector_score(qv, tv), 2)


def _imgs_verification_parts(query: Dict[str, Any], target: Dict[str, Any], base_score: float, details: Dict[str, Any]) -> Dict[str, float]:
    parts = dict(details.get("parts") or {})
    parts["imgs_shape_grid"] = _score_from_vectors(query, target, "imgs_ink_grid_20", base_score)
    parts["imgs_edge_grid"] = _score_from_vectors(query, target, "imgs_edge_grid_20", base_score)
    parts["imgs_center_focus"] = _score_from_vectors(query, target, "imgs_center_focus", base_score)
    parts["imgs_ring_layout"] = _score_from_vectors(query, target, "imgs_ring_sector", base_score)
    parts["imgs_contour"] = _score_from_vectors(query, target, "imgs_contour", base_score)
    # Keep old terms normalized when available.
    for key in ("mask_overlap", "edge_overlap", "projection", "moments", "radial", "color"):
        try:
            parts[key] = round(float(parts.get(key, base_score)), 2)
        except Exception:
            parts[key] = round(float(base_score), 2)
    return parts


def _imgs_final_score(base_score: float, details: Dict[str, Any], parts: Dict[str, float]) -> Tuple[float, Dict[str, Any]]:
    """First-stage IMGS verifier.

    This intentionally requires multiple layers to agree. A design cannot win only
    because one small block looks similar.
    """
    block = float(details.get("block_part") or base_score)
    micro = float(details.get("micro_score") or 0.0)
    if micro <= 0:
        micro = base_score
    shape = float(parts.get("imgs_shape_grid", base_score))
    edge = float(parts.get("imgs_edge_grid", base_score))
    center = float(parts.get("imgs_center_focus", base_score))
    ring = float(parts.get("imgs_ring_layout", base_score))
    contour = float(parts.get("imgs_contour", base_score))
    mask = float(parts.get("mask_overlap", base_score))
    edge_overlap = float(parts.get("edge_overlap", edge))
    moments = float(parts.get("moments", base_score))
    projection = float(parts.get("projection", base_score))
    color = float(parts.get("color", base_score))

    final = (
        base_score * 0.20 +
        shape * 0.16 +
        edge * 0.16 +
        center * 0.12 +
        contour * 0.11 +
        ring * 0.08 +
        mask * 0.07 +
        edge_overlap * 0.05 +
        block * 0.03 +
        micro * 0.01 +
        color * 0.01
    )

    # Agreement boost: only when several independent truths are strong.
    agreement_core = min(shape, edge, center, contour, mask)
    if agreement_core >= 78 and base_score >= 70:
        final += min(4.5, (agreement_core - 78) * 0.12)

    # False-positive guards. Sparse embroidery previews can match on blank space;
    # require real foreground/edge agreement before high confidence is allowed.
    if mask < 22:
        final = min(final, 58.0)
    elif mask < 32:
        # Foreground overlap is the strongest anti-false-positive truth.
        # Blank-space similarity should never become a verified match.
        final = min(final, 64.0)
    elif mask < 45 and edge_overlap < 62:
        final = min(final, 72.0)
    elif min(shape, edge, center) < 48 and final > 74:
        final = 74.0

    # If the old block/micro path is high but IMGS structure disagrees, cap it.
    structural = (shape * 0.30 + edge * 0.25 + center * 0.20 + contour * 0.15 + ring * 0.10)
    if base_score > structural + 20:
        final = min(final, structural + 12)

    verification = {
        "base_layout": round(base_score, 2),
        "shape_grid": round(shape, 2),
        "edge_grid": round(edge, 2),
        "center_focus": round(center, 2),
        "contour": round(contour, 2),
        "ring_layout": round(ring, 2),
        "mask_overlap": round(mask, 2),
        "edge_overlap": round(edge_overlap, 2),
        "block_part": round(block, 2),
        "micro_part": round(micro, 2),
        "color": round(color, 2),
        "agreement_core": round(agreement_core, 2),
        "structural_score": round(structural, 2),
    }
    return round(max(0.0, min(100.0, final)), 2), verification


def compare_fingerprints(query: Dict[str, Any], target: Dict[str, Any]) -> Dict[str, Any]:
    base_score, details = _block_compare_score(query or {}, target or {})
    parts = _imgs_verification_parts(query or {}, target or {}, base_score, details)
    score, verification = _imgs_final_score(base_score, details, parts)
    distance = max(0.0, min(1.0, 1.0 - (score / 100.0)))

    if score >= 92:
        label = "IMGS Exact/Strong Match"
    elif score >= 84:
        label = "IMGS Verified Match"
    elif score >= 72:
        label = "IMGS Similar Match"
    elif score >= 58:
        label = "IMGS Possible Match"
    else:
        label = "IMGS Closest Candidate"

    return {
        "score": round(score, 2),
        "label": label,
        "distance": round(distance, 5),
        "engine": IMGS_ENGINE_VERSION,
        "algorithm": "Image Searcher powered by IMGS Engine v0.8.4: heavy first-stage shape, edge, center, contour, block and foreground verification",
        "verification_layers": 12,
        "parts": parts,
        "verification": verification,
        "block_scores": details.get("block_scores", {}),
        "best_blocks": details.get("best_blocks", {}),
        "global_score": details.get("global_score"),
        "base_score": round(base_score, 2),
        "block_part": details.get("block_part"),
        "micro_score": details.get("micro_score"),
        "mode": "imgs-v0.8.4-first-stage-heavy-verification",
    }

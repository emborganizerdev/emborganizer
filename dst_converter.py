"""
dst_converter.py
EMBORGANIZER v5.4.3 legacy converter restore.

Local-only embroidery converter/reader used by the Streamlit site:
- DST -> PNG/JPG/WEBP previews without needing an external API.
- Uses pyembroidery when available for many formats.
- Falls back to an internal DST reader when pyembroidery is not installed.
- Uses TurboEmb C++ renderer when available, then Python/Pillow fallback.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageOps

try:  # optional, listed in requirements but app still runs without it
    import pyembroidery  # type: ignore
except Exception:  # pragma: no cover
    pyembroidery = None

try:
    from turboemb_engine import render_pattern_with_cpp, ensure_cpp_renderer, TURBOEMB_ENGINE_VERSION
except Exception:  # pragma: no cover
    render_pattern_with_cpp = None
    ensure_cpp_renderer = None
    TURBOEMB_ENGINE_VERSION = "TurboEmb C++ unavailable"

DST_CONVERTER_VERSION = "DST Converter v5.4.3 • Local TurboEmb/C++ + Python fallback"
SUPPORTED_EMB_EXTENSIONS = {".dst", ".pes", ".jef", ".exp", ".vp3", ".xxx", ".u01", ".pec"}
SUPPORTED_OUTPUT_FORMATS = {"PNG", "JPEG", "JPG", "WEBP"}

# Keep these integers aligned with pyembroidery default command IDs when possible.
STITCH = 0
JUMP = 1
TRIM = 2
STOP = 3
END = 4
COLOR_CHANGE = 5
COMMAND_MASK = 0xFF

DEFAULT_PALETTE: List[Tuple[int, int, int]] = [
    (8, 47, 73), (220, 38, 38), (8, 145, 178), (22, 163, 74),
    (245, 158, 11), (124, 58, 237), (219, 39, 119), (15, 23, 42),
    (14, 165, 233), (249, 115, 22), (20, 184, 166), (190, 24, 93),
]


@dataclass
class SimpleThread:
    r: int
    g: int
    b: int

    def get_hex_color(self) -> str:
        return f"#{self.r:02x}{self.g:02x}{self.b:02x}"


class SimplePattern:
    """Tiny pattern object with the attributes TurboEmb needs."""

    def __init__(self, stitches: List[Tuple[float, float, int]], threadlist: Optional[List[Any]] = None, metadata: Optional[Dict[str, Any]] = None):
        self.stitches = stitches
        self.threadlist = threadlist or [SimpleThread(*rgb) for rgb in DEFAULT_PALETTE[:8]]
        self.metadata = metadata or {}


# -----------------------------
# Reading / decoding
# -----------------------------


def _thread_to_rgb(thread: Any) -> Optional[Tuple[int, int, int]]:
    try:
        if hasattr(thread, "get_hex_color"):
            value = thread.get_hex_color()
        elif hasattr(thread, "hex_color"):
            attr = getattr(thread, "hex_color")
            value = attr() if callable(attr) else attr
        elif hasattr(thread, "color"):
            value = getattr(thread, "color")
        else:
            value = thread
        if isinstance(value, int):
            return ((value >> 16) & 255, (value >> 8) & 255, value & 255)
        if isinstance(value, (tuple, list)) and len(value) >= 3:
            return (int(value[0]) & 255, int(value[1]) & 255, int(value[2]) & 255)
        text = str(value or "").strip().lstrip("#")
        if len(text) >= 6:
            return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))
    except Exception:
        return None
    return None


def _palette_from_pattern(pattern: Any) -> List[Tuple[int, int, int]]:
    colors: List[Tuple[int, int, int]] = []
    try:
        threads = list(getattr(pattern, "threadlist", []) or [])
    except Exception:
        threads = []
    for thread in threads[:256]:
        rgb = _thread_to_rgb(thread)
        if rgb is not None and rgb not in colors:
            colors.append(rgb)
    return colors or list(DEFAULT_PALETTE)


def _read_with_pyembroidery(path: Path) -> Optional[Any]:
    if pyembroidery is None:
        return None
    try:
        pattern = pyembroidery.read(str(path))
        stitches = list(getattr(pattern, "stitches", []) or [])
        if len(stitches) >= 2:
            return pattern
    except Exception:
        return None
    return None


def _decode_dst_delta(b0: int, b1: int, b2: int) -> Tuple[int, int]:
    """Decode a 3-byte Tajima DST movement record.

    The fallback reader is intended for local preview/search restoration. It does
    not replace pyembroidery, but it is good enough to render and fingerprint most
    DST catalogs when pyembroidery is missing.
    """
    dx = 0
    dy = 0
    # ±1, ±3, ±9, ±27, ±81 movement bits.
    if b0 & 0x01: dx += 1
    if b0 & 0x02: dx -= 1
    if b0 & 0x04: dy -= 1
    if b0 & 0x08: dy += 1
    if b0 & 0x80: dx += 3
    if b0 & 0x40: dx -= 3
    if b0 & 0x20: dy -= 3
    if b0 & 0x10: dy += 3
    if b1 & 0x01: dx += 9
    if b1 & 0x02: dx -= 9
    if b1 & 0x04: dy -= 9
    if b1 & 0x08: dy += 9
    if b1 & 0x80: dx += 27
    if b1 & 0x40: dx -= 27
    if b1 & 0x20: dy -= 27
    if b1 & 0x10: dy += 27
    if b2 & 0x04: dx += 81
    if b2 & 0x08: dx -= 81
    if b2 & 0x10: dy -= 81
    if b2 & 0x20: dy += 81
    return dx, dy


def _dst_command(b0: int, b1: int, b2: int) -> int:
    if b0 == 0 and b1 == 0 and b2 == 0xF3:
        return END
    # DST command flags are compact; these are robust enough for preview rendering.
    if (b2 & 0xC3) == 0xC3:
        return COLOR_CHANGE
    if (b2 & 0x83) == 0x83 or (b2 & 0x43) == 0x43:
        return JUMP
    return STITCH


def _parse_dst_header(header: bytes) -> Dict[str, Any]:
    text = header.decode("latin-1", errors="ignore")
    result: Dict[str, Any] = {"raw_header": text[:512]}
    for key in ("LA", "ST", "CO", "+X", "-X", "+Y", "-Y", "AX", "AY", "MX", "MY", "PD"):
        pos = text.find(key + ":")
        if pos >= 0:
            result[key] = text[pos + len(key) + 1: pos + len(key) + 18].strip().split("\r")[0]
    return result


def _read_dst_fallback(path: Path) -> SimplePattern:
    data = path.read_bytes()
    if len(data) < 515:
        raise ValueError("DST file is too small to read")
    header = data[:512]
    x = 0
    y = 0
    stitches: List[Tuple[float, float, int]] = []
    color_count = 1
    jumps = 0
    trims = 0
    records = 0
    for i in range(512, len(data) - 2, 3):
        b0, b1, b2 = data[i], data[i + 1], data[i + 2]
        cmd = _dst_command(b0, b1, b2)
        if cmd == END:
            stitches.append((float(x), float(y), END))
            break
        dx, dy = _decode_dst_delta(b0, b1, b2)
        x += dx
        y += dy
        if cmd == COLOR_CHANGE:
            color_count += 1
        elif cmd == JUMP:
            jumps += 1
        # convert occasional long jumps to trim-like resets for cleaner preview
        if cmd == JUMP and (abs(dx) + abs(dy)) > 120:
            trims += 1
            cmd = TRIM
        stitches.append((float(x), float(y), cmd))
        records += 1
    if len(stitches) < 2:
        raise ValueError("No stitches found in DST file")
    metadata = _parse_dst_header(header)
    metadata.update({"reader": "internal_dst_fallback", "records": records, "colors_detected": color_count, "jumps": jumps, "trims": trims})
    return SimplePattern(stitches=stitches, metadata=metadata)


def read_embroidery_pattern(path: Path) -> Tuple[Any, Dict[str, Any]]:
    """Read embroidery file and return a pattern object + reader metadata."""
    path = Path(path)
    ext = path.suffix.lower()
    pattern = _read_with_pyembroidery(path)
    if pattern is not None:
        return pattern, {"reader": "pyembroidery", "format": ext.lstrip("."), "pyembroidery": True}
    if ext == ".dst":
        p = _read_dst_fallback(path)
        return p, {"reader": "internal_dst_fallback", "format": "dst", "pyembroidery": False}
    raise RuntimeError(f"Cannot read {ext or 'file'} without pyembroidery. Install pyembroidery for PES/JEF/EXP/VP3/etc.")


# -----------------------------
# Statistics / reader
# -----------------------------


def _command_name(cmd: int) -> str:
    c = int(cmd) & COMMAND_MASK
    if c == STITCH:
        return "stitch"
    if c == JUMP:
        return "jump"
    if c == TRIM:
        return "trim"
    if c == COLOR_CHANGE:
        return "color_change"
    if c == STOP:
        return "stop"
    if c == END:
        return "end"
    return "other"


def pattern_stats(pattern: Any, source_name: str = "design") -> Dict[str, Any]:
    pts: List[Tuple[float, float, int]] = []
    for raw in list(getattr(pattern, "stitches", []) or []):
        if len(raw) < 3:
            continue
        try:
            pts.append((float(raw[0]), float(raw[1]), int(raw[2]) & COMMAND_MASK))
        except Exception:
            continue
    counts: Dict[str, int] = {}
    xs: List[float] = []
    ys: List[float] = []
    segments = 0
    have_prev = False
    last_x = last_y = 0.0
    max_jump = 0.0
    total_length = 0.0
    color_changes = 0
    for x, y, cmd in pts:
        name = _command_name(cmd)
        counts[name] = counts.get(name, 0) + 1
        if cmd == STITCH:
            xs.append(x)
            ys.append(y)
            if have_prev:
                dist = math.hypot(x - last_x, y - last_y)
                total_length += dist
                segments += 1
            have_prev = True
            last_x, last_y = x, y
        else:
            if cmd in {JUMP, TRIM} and have_prev:
                max_jump = max(max_jump, math.hypot(x - last_x, y - last_y))
            if cmd in {COLOR_CHANGE, STOP}:
                color_changes += 1
            have_prev = False
            last_x, last_y = x, y
    if xs and ys:
        minx, maxx = min(xs), max(xs)
        miny, maxy = min(ys), max(ys)
    else:
        minx = miny = maxx = maxy = 0.0
    width = maxx - minx
    height = maxy - miny
    palette = _palette_from_pattern(pattern)
    return {
        "source_name": source_name,
        "points": len(pts),
        "stitches": counts.get("stitch", 0),
        "jumps": counts.get("jump", 0),
        "trims": counts.get("trim", 0),
        "color_changes": max(color_changes, counts.get("color_change", 0)),
        "segments": segments,
        "bounds": {"min_x": round(minx, 2), "min_y": round(miny, 2), "max_x": round(maxx, 2), "max_y": round(maxy, 2), "width": round(width, 2), "height": round(height, 2)},
        "estimated_thread_colors": len(palette),
        "estimated_length_units": round(total_length, 2),
        "max_jump_units": round(max_jump, 2),
        "density_score": round((segments / max(1.0, (width * height) / 1000.0)), 3) if width and height else 0,
        "palette_preview": ["#%02x%02x%02x" % rgb for rgb in palette[:16]],
    }


def read_design_file(path: Path) -> Dict[str, Any]:
    pattern, meta = read_embroidery_pattern(path)
    stats = pattern_stats(pattern, Path(path).name)
    stats.update({"reader": meta, "engine": DST_CONVERTER_VERSION})
    return stats


# -----------------------------
# Rendering
# -----------------------------


def _fit_transform(points: List[Tuple[float, float, int]], size: int, margin_ratio: float = 0.065) -> Tuple[float, float, float, int]:
    xs = [x for x, y, c in points if (int(c) & COMMAND_MASK) == STITCH]
    ys = [y for x, y, c in points if (int(c) & COMMAND_MASK) == STITCH]
    if not xs or not ys:
        xs = [x for x, y, c in points]
        ys = [y for x, y, c in points]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    width = max(1.0, maxx - minx)
    height = max(1.0, maxy - miny)
    margin = max(18, int(size * margin_ratio))
    scale = min((size - margin * 2) / width, (size - margin * 2) / height)
    return minx, miny, scale, margin


def render_pattern_python(
    pattern: Any,
    output_path: Path,
    *,
    size: int = 2048,
    output_format: str = "PNG",
    background: str = "white",
    line_width: int = 2,
    supersample: int = 2,
) -> Dict[str, Any]:
    pts: List[Tuple[float, float, int]] = []
    for raw in list(getattr(pattern, "stitches", []) or []):
        if len(raw) >= 3:
            try:
                pts.append((float(raw[0]), float(raw[1]), int(raw[2]) & COMMAND_MASK))
            except Exception:
                pass
    if len(pts) < 2:
        raise ValueError("No stitches to render")

    ss = max(1, min(int(supersample), 4))
    final_size = max(256, min(int(size), 4096))
    render_size = final_size * ss
    minx, miny, scale, margin = _fit_transform(pts, render_size)
    palette = _palette_from_pattern(pattern)
    img = Image.new("RGB", (render_size, render_size), background)
    draw = ImageDraw.Draw(img)
    have_prev = False
    px = py = 0.0
    color_index = 0
    segments = 0
    drawn = 0
    width = max(1, int(line_width) * ss)
    for x, y, cmd in pts:
        c = int(cmd) & COMMAND_MASK
        if c == STITCH:
            tx = (x - minx) * scale + margin
            ty = (y - miny) * scale + margin
            if have_prev:
                color = palette[color_index % len(palette)]
                draw.line((px, py, tx, ty), fill=color, width=width, joint="curve")
                segments += 1
                drawn += 1
            px, py = tx, ty
            have_prev = True
        elif c in {COLOR_CHANGE, STOP}:
            color_index += 1
            have_prev = False
        else:
            have_prev = False
    if ss > 1:
        img = img.resize((final_size, final_size), Image.Resampling.LANCZOS)
    try:
        img = ImageOps.autocontrast(img)
        img = img.filter(ImageFilter.UnsharpMask(radius=0.6, percent=120, threshold=2))
    except Exception:
        pass
    fmt = (output_format or output_path.suffix.lstrip(".") or "PNG").upper().replace("JPG", "JPEG")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "PNG":
        img.save(output_path, "PNG", compress_level=1, optimize=False)
    elif fmt == "JPEG":
        img.save(output_path, "JPEG", quality=98, optimize=False, progressive=False, subsampling=0)
    else:
        img.save(output_path, "WEBP", quality=98, method=1)
    meta = pattern_stats(pattern, output_path.name)
    meta.update({
        "engine": "TurboEmb_Python_Fallback",
        "output_path": str(output_path),
        "output_format": fmt,
        "output_size": final_size,
        "render_size": render_size,
        "supersample": ss,
        "drawn_segments": drawn,
    })
    return meta


def render_embroidery_file(
    input_path: Path,
    output_path: Path,
    *,
    size: int = 2048,
    output_format: str = "PNG",
    prefer_cpp: bool = True,
) -> Dict[str, Any]:
    pattern, reader = read_embroidery_pattern(Path(input_path))
    fmt = (output_format or output_path.suffix.lstrip(".") or "PNG").upper().replace("JPG", "JPEG")
    if prefer_cpp and render_pattern_with_cpp is not None:
        try:
            ok, meta = render_pattern_with_cpp(pattern, Path(output_path), size=int(size), output_format=fmt, final_output=True)
            if ok and Path(output_path).exists():
                stats = pattern_stats(pattern, Path(input_path).name)
                stats.update(meta or {})
                stats.update({"reader": reader, "output_path": str(output_path), "output_format": fmt, "converter_version": DST_CONVERTER_VERSION})
                return stats
        except Exception:
            pass
    meta = render_pattern_python(pattern, Path(output_path), size=int(size), output_format=fmt, supersample=2)
    meta.update({"reader": reader, "converter_version": DST_CONVERTER_VERSION})
    return meta


def file_sha1(path: Path) -> str:
    h = hashlib.sha1()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_stem(name: str) -> str:
    stem = Path(name).stem or "design"
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in stem)[:90] or "design"


def convert_uploaded_bytes(data: bytes, filename: str, out_dir: Path, *, size: int = 2048, output_format: str = "PNG", prefer_cpp: bool = True) -> Dict[str, Any]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = str(int(time.time() * 1000))
    src_path = out_dir / f"{safe_stem(filename)}_{stamp}{Path(filename).suffix.lower() or '.dst'}"
    src_path.write_bytes(data)
    fmt = (output_format or "PNG").upper().replace("JPG", "JPEG")
    ext = ".jpg" if fmt == "JPEG" else ".webp" if fmt == "WEBP" else ".png"
    out_path = out_dir / f"{safe_stem(filename)}_{stamp}_{int(size)}px{ext}"
    meta = render_embroidery_file(src_path, out_path, size=int(size), output_format=fmt, prefer_cpp=prefer_cpp)
    meta.update({"input_path": str(src_path), "input_name": filename, "input_sha1": file_sha1(src_path), "output_path": str(out_path)})
    meta_path = out_path.with_suffix(out_path.suffix + ".json")
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    meta["metadata_path"] = str(meta_path)
    return meta


def convert_zip_bytes(payload: bytes, zip_name: str, out_dir: Path, *, size: int = 2048, output_format: str = "PNG", limit: int = 500, prefer_cpp: bool = True) -> Dict[str, Any]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    converted: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        names = [n for n in zf.namelist() if not n.endswith("/") and Path(n).suffix.lower() in SUPPORTED_EMB_EXTENSIONS]
        for name in names[: int(limit)]:
            try:
                meta = convert_uploaded_bytes(zf.read(name), Path(name).name, out_dir, size=size, output_format=output_format, prefer_cpp=prefer_cpp)
                meta["source_zip"] = zip_name
                meta["zip_member"] = name
                converted.append(meta)
            except Exception as exc:
                errors.append({"file": name, "error": str(exc)[:240]})
    bundle_path = out_dir / f"converted_{safe_stem(zip_name)}_{int(time.time())}.zip"
    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as outzip:
        for meta in converted:
            for key in ("output_path", "metadata_path"):
                p = Path(str(meta.get(key) or ""))
                if p.exists():
                    outzip.write(p, arcname=p.name)
    return {"zip_name": zip_name, "converted": converted, "errors": errors, "bundle_path": str(bundle_path), "count": len(converted)}


def cpp_status() -> Dict[str, Any]:
    if ensure_cpp_renderer is None:
        return {"available": False, "message": "TurboEmb C++ module not importable"}
    ok, status = ensure_cpp_renderer()
    status["available"] = bool(ok)
    status["engine_version"] = TURBOEMB_ENGINE_VERSION
    return status

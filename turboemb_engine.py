from __future__ import annotations

import json
import math
import os
import shutil
import struct
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageFilter, ImageOps

try:
    import pyembroidery
except Exception:  # pragma: no cover
    pyembroidery = None

TURBOEMB_ENGINE_VERSION = "TurboEmb v3 • Turbo Engine • C++ Turbo + 4K Image Generation"
BASE_DIR = Path(__file__).resolve().parent
CPP_SOURCE = BASE_DIR / "turboemb_cpp_renderer.cpp"
CPP_BINARY_NAME = "turboemb_cpp_renderer.exe" if os.name == "nt" else "turboemb_cpp_renderer"
CPP_BINARY = BASE_DIR / CPP_BINARY_NAME
CACHE_DIR = BASE_DIR / ".turboemb"
CACHE_BINARY = CACHE_DIR / CPP_BINARY_NAME

TURBOEMB_CPP_ENABLED = os.environ.get("TURBOEMB_CPP", "1").lower() not in {"0", "false", "no", "off"}
TURBOEMB_PREVIEW_SUPERSAMPLE = max(1, min(int(os.environ.get("TURBOEMB_SUPERSAMPLE", "3")), 4))
TURBOEMB_SUPERSAMPLE_MAX_SIZE = max(1200, int(os.environ.get("TURBOEMB_SUPERSAMPLE_MAX_SIZE", "5400")))
TURBOEMB_PREVIEW_MAX_LINES = int(os.environ.get("TURBOEMB_MAX_LINES", "900000"))
TURBOEMB_CONVERTER_MAX_LINES = int(os.environ.get("TURBOEMB_CONVERTER_MAX_LINES", "1600000"))
TURBOEMB_WEBP_QUALITY = max(90, min(int(os.environ.get("TURBOEMB_WEBP_QUALITY", "98")), 100))
TURBOEMB_JPG_QUALITY = max(90, min(int(os.environ.get("TURBOEMB_JPG_QUALITY", "98")), 100))
TURBOEMB_4K_ENABLED = os.environ.get("TURBOEMB_4K_ENABLED", "1").lower() not in {"0", "false", "no", "off"}
TURBOEMB_PNG_COMPRESS_LEVEL = max(0, min(int(os.environ.get("TURBOEMB_PNG_COMPRESS_LEVEL", "1")), 9))
TURBOEMB_SHARPEN = os.environ.get("TURBOEMB_SHARPEN", "1").lower() not in {"0", "false", "no", "off"}

_compile_status: Dict[str, Any] = {"checked": False, "available": False, "binary": "", "message": "not checked"}


def _run_status(binary: Path) -> bool:
    try:
        if not binary.exists():
            return False
        if os.name != "nt":
            binary.chmod(binary.stat().st_mode | 0o111)
        proc = subprocess.run([str(binary)], capture_output=True, text=True, timeout=4)
        # The helper exits with usage code 2 when it is runnable without args.
        return proc.returncode in {0, 2}
    except Exception:
        return False


def ensure_cpp_renderer(force: bool = False) -> Tuple[bool, Dict[str, Any]]:
    """Return whether the optional native renderer can be used.

    The source code is shipped with the app. On platforms with g++/clang++, this
    compiles a small executable once and reuses it. If compilation is not allowed
    on Streamlit Cloud or another host, callers should fall back to Python.
    """
    global _compile_status
    if _compile_status.get("checked") and not force:
        return bool(_compile_status.get("available")), dict(_compile_status)

    status: Dict[str, Any] = {"checked": True, "available": False, "binary": "", "message": "C++ renderer disabled"}
    if not TURBOEMB_CPP_ENABLED:
        _compile_status = status
        return False, dict(status)

    for candidate in (CPP_BINARY, CACHE_BINARY):
        if _run_status(candidate):
            status.update({"available": True, "binary": str(candidate), "message": "C++ renderer ready"})
            _compile_status = status
            return True, dict(status)

    if not CPP_SOURCE.exists():
        status["message"] = "C++ source file is missing"
        _compile_status = status
        return False, dict(status)

    compiler = shutil.which(os.environ.get("CXX", "")) if os.environ.get("CXX") else None
    if compiler is None:
        compiler = shutil.which("g++") or shutil.which("clang++")
    if not compiler:
        status["message"] = "No C++ compiler found; Python fallback active"
        _compile_status = status
        return False, dict(status)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cmd = [compiler, "-O3", "-std=c++17", str(CPP_SOURCE), "-o", str(CACHE_BINARY)]
    started = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if proc.returncode == 0 and _run_status(CACHE_BINARY):
            status.update({
                "available": True,
                "binary": str(CACHE_BINARY),
                "message": f"C++ renderer compiled with {Path(compiler).name} in {time.time() - started:.1f}s",
            })
        else:
            err = (proc.stderr or proc.stdout or "compiler returned an error").strip().splitlines()[-1:]
            status["message"] = "C++ compile failed; Python fallback active" + (f": {err[0][:160]}" if err else "")
    except Exception as exc:
        status["message"] = f"C++ compile unavailable; Python fallback active: {exc}"

    _compile_status = status
    return bool(status.get("available")), dict(status)


def cpp_renderer_binary() -> Optional[Path]:
    available, status = ensure_cpp_renderer()
    if not available:
        return None
    return Path(status["binary"])


def command_constants() -> Dict[str, int]:
    if pyembroidery is None:
        return {"STITCH": 0, "JUMP": 1, "TRIM": 2, "STOP": 3, "END": 4, "COLOR_CHANGE": 5, "COMMAND_MASK": 0xFF}
    return {
        "STITCH": int(getattr(pyembroidery, "STITCH", 0)),
        "JUMP": int(getattr(pyembroidery, "JUMP", 1)),
        "TRIM": int(getattr(pyembroidery, "TRIM", 2)),
        "STOP": int(getattr(pyembroidery, "STOP", 3)),
        "END": int(getattr(pyembroidery, "END", 4)),
        "COLOR_CHANGE": int(getattr(pyembroidery, "COLOR_CHANGE", 5)),
        "COMMAND_MASK": int(getattr(pyembroidery, "COMMAND_MASK", 0xFF)),
    }


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


def extract_thread_palette(pattern: Any) -> List[Tuple[int, int, int]]:
    colors: List[Tuple[int, int, int]] = []
    try:
        threads = list(getattr(pattern, "threadlist", []) or [])
    except Exception:
        threads = []
    for thread in threads[:256]:
        rgb = _thread_to_rgb(thread)
        if rgb is not None and rgb not in colors:
            colors.append(rgb)
    return colors


def preview_render_plan(size: int, final_output: bool = False) -> Dict[str, int]:
    output_size = max(256, int(size or 1100))
    ss = int(TURBOEMB_PREVIEW_SUPERSAMPLE)
    if output_size * ss > TURBOEMB_SUPERSAMPLE_MAX_SIZE:
        ss = max(1, TURBOEMB_SUPERSAMPLE_MAX_SIZE // output_size)
    ss = max(1, min(ss, TURBOEMB_PREVIEW_SUPERSAMPLE))
    render_size = output_size * ss
    final_thread_px = 1.10 if final_output else 1.20
    line_width = max(1, int(round(final_thread_px * ss)))
    max_lines = TURBOEMB_CONVERTER_MAX_LINES if final_output else TURBOEMB_PREVIEW_MAX_LINES
    return {
        "output_size": output_size,
        "render_size": render_size,
        "supersample": ss,
        "line_width": line_width,
        "max_lines": max(1000, int(max_lines)),
    }


def _valid_points(pattern: Any) -> List[Tuple[float, float, int]]:
    pts: List[Tuple[float, float, int]] = []
    for stitch in list(getattr(pattern, "stitches", []) or []):
        if len(stitch) < 3:
            continue
        try:
            pts.append((float(stitch[0]), float(stitch[1]), int(stitch[2])))
        except Exception:
            continue
    return pts


def write_raw_pattern_binary(raw_path: Path, pattern: Any, plan: Dict[str, int]) -> int:
    constants = command_constants()
    pts = _valid_points(pattern)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    palette = extract_thread_palette(pattern)
    pack_point = struct.Struct("<ffi").pack
    with raw_path.open("wb") as fh:
        fh.write(b"EBRAW1\0\0")
        fh.write(struct.pack(
            "<iiiiiiiii",
            int(plan["render_size"]), int(plan["line_width"]), int(plan["max_lines"]),
            int(constants["COMMAND_MASK"]), int(constants["STITCH"]), int(constants["JUMP"]),
            int(constants["TRIM"]), int(constants["STOP"]), int(constants["COLOR_CHANGE"]),
        ))
        fh.write(struct.pack("<i", len(palette)))
        for r, g, b in palette:
            fh.write(struct.pack("<iii", int(r), int(g), int(b)))
        fh.write(struct.pack("<i", len(pts)))
        for x, y, cmd in pts:
            fh.write(pack_point(x, y, cmd))
    return len(pts)


def turboemb_postprocess_rgb(img: Image.Image, output_size: int = 0) -> Image.Image:
    rgb = img.convert("RGB")
    if output_size and rgb.size != (int(output_size), int(output_size)):
        rgb = rgb.resize((int(output_size), int(output_size)), Image.Resampling.LANCZOS)
    try:
        rgb = ImageOps.autocontrast(rgb, cutoff=0)
    except Exception:
        pass
    if TURBOEMB_SHARPEN:
        try:
            rgb = rgb.filter(ImageFilter.UnsharpMask(radius=0.75, percent=125, threshold=2))
        except Exception:
            pass
    return rgb


def save_turbo_image(ppm_path: Path, output_path: Path, plan: Dict[str, int], output_format: str = "WEBP") -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fmt = (output_format or "WEBP").upper().replace("JPG", "JPEG")
    with Image.open(ppm_path) as img:
        rgb = turboemb_postprocess_rgb(img, int(plan.get("output_size") or img.width))
        if fmt == "PNG":
            rgb.save(output_path, "PNG", compress_level=TURBOEMB_PNG_COMPRESS_LEVEL, optimize=False)
        elif fmt == "JPEG":
            rgb.save(output_path, "JPEG", quality=TURBOEMB_JPG_QUALITY, optimize=False, progressive=False, subsampling=0)
        else:
            rgb.save(output_path, "WEBP", quality=TURBOEMB_WEBP_QUALITY, method=1)


def render_pattern_with_cpp(pattern: Any, output_path: Path, size: int = 1100, output_format: str = "WEBP", final_output: bool = False) -> Tuple[bool, Dict[str, Any]]:
    binary = cpp_renderer_binary()
    if binary is None or pattern is None:
        return False, {"engine": "python_fallback", "cpp_available": False}
    plan = preview_render_plan(int(size), final_output=final_output)
    stamp = f"{os.getpid()}_{int(time.time() * 1000)}"
    raw_path = output_path.with_suffix(f".{stamp}.ebraw")
    ppm_path = output_path.with_suffix(f".{stamp}.ppm")
    meta_path = output_path.with_suffix(f".{stamp}.meta.json")
    try:
        n = write_raw_pattern_binary(raw_path, pattern, plan)
        if n < 2:
            return False, {"engine": "turboemb_cpp", "error": "Not enough stitches"}
        proc = subprocess.run([str(binary), "--raw", str(raw_path), str(ppm_path), str(meta_path)], capture_output=True, text=True, timeout=90)
        if proc.returncode != 0 or not ppm_path.exists():
            return False, {"engine": "turboemb_cpp", "error": (proc.stderr or proc.stdout or "C++ renderer failed")[:240]}
        save_turbo_image(ppm_path, output_path, plan, output_format)
        meta: Dict[str, Any] = {}
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                meta = {}
        meta.update({
            "engine": "TurboEmb_v3_CPP_Raw",
            "engine_label": TURBOEMB_ENGINE_VERSION,
            "supports_4k": bool(TURBOEMB_4K_ENABLED),
            "cpp_available": True,
            "supersample": plan["supersample"],
            "render_size": plan["render_size"],
            "output_size": plan["output_size"],
            "max_lines": plan["max_lines"],
            "sharp_emb": True,
        })
        return output_path.exists(), meta
    except Exception as exc:
        return False, {"engine": "turboemb_cpp", "error": str(exc)[:240]}
    finally:
        for tmp in (raw_path, ppm_path, meta_path):
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass

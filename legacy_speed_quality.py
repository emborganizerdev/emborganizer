"""Adaptive speed/quality profiles for EMBORGANIZER v0.8.5 / TURBOEMB.

Keep this small and separate so upload/render tuning can be debugged without
reading the large FastAPI app file. TURBOEMB accuracy settings live in app.py because they are renderer-facing. v0.8.5 adds Desktop Turbo Pro for CPU-heavy desktops.
"""

import os
from typing import Dict


def _int_env(name: str, default: int, low: int, high: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except Exception:
        value = default
    return max(low, min(high, value))


def server_caps() -> Dict:
    cpu = os.cpu_count() or 2
    cpu_target_percent = _int_env("DESKTOP_TURBO_PRO_CPU_TARGET", 50, 20, 90)
    turbo_pro_render = max(1, int(round(cpu * (cpu_target_percent / 100.0))))
    return {
        "cpu_count": cpu,
        "desktop_turbo_pro_cpu_target": cpu_target_percent,
        "desktop_turbo_pro_render_workers": turbo_pro_render,
        "max_upload_parallel": _int_env("EMB_MAX_UPLOAD_PARALLEL", min(12, max(2, cpu * 2)), 1, 24),
        "max_convert_parallel": _int_env("EMB_MAX_CONVERT_PARALLEL", min(8, max(1, cpu)), 1, 16),
        "max_import_upload_parallel": _int_env("EMB_MAX_IMPORT_UPLOAD_PARALLEL", min(12, max(2, cpu * 2)), 1, 24),
        "quality_jpg": _int_env("EMB_JPG_QUALITY", 98, 80, 100),
        "quality_webp": _int_env("EMB_WEBP_QUALITY", 98, 80, 100),
        "png_compress_level": _int_env("EMB_PNG_COMPRESS_LEVEL", 0, 0, 6),
        "cache_enabled": os.environ.get("EMB_CONVERT_CACHE", "1").lower() not in {"0", "false", "no", "off"},
    }


def presets() -> Dict[str, Dict]:
    caps = server_caps()
    return {
        "mobile_safe": {
            "label": "Mobile Safe",
            "upload_parallel": min(2, caps["max_upload_parallel"]),
            "convert_parallel": min(1, caps["max_convert_parallel"]),
            "import_upload_parallel": min(2, caps["max_import_upload_parallel"]),
            "default_image_size": 2200,
            "folder_upload_mode": "direct_parallel",
            "quality": "high",
        },
        "balanced": {
            "label": "Balanced",
            "upload_parallel": min(4, caps["max_upload_parallel"]),
            "convert_parallel": min(2, caps["max_convert_parallel"]),
            "import_upload_parallel": min(4, caps["max_import_upload_parallel"]),
            "default_image_size": 2400,
            "folder_upload_mode": "direct_parallel",
            "quality": "high",
        },
        "desktop_turbo": {
            "label": "Desktop Turbo",
            "upload_parallel": min(8, caps["max_upload_parallel"]),
            "convert_parallel": min(4, caps["max_convert_parallel"]),
            "import_upload_parallel": min(8, caps["max_import_upload_parallel"]),
            "default_image_size": 3200,
            "folder_upload_mode": "direct_parallel",
            "quality": "best",
            "cpu_target": "normal",
        },
        "desktop_turbo_pro": {
            "label": "Desktop Turbo Pro",
            "upload_parallel": min(12, caps["max_upload_parallel"]),
            "convert_parallel": min(max(4, caps["desktop_turbo_pro_render_workers"]), caps["max_convert_parallel"]),
            "import_upload_parallel": min(12, caps["max_import_upload_parallel"]),
            "default_image_size": 3600,
            "folder_upload_mode": "direct_parallel",
            "quality": "best",
            "cpu_target_percent": caps["desktop_turbo_pro_cpu_target"],
            "note": "Targets about the configured CPU pressure by raising worker count, while respecting server caps.",
        },
    }


def clamp_client_settings(upload_parallel: int = 1, convert_parallel: int = 1, import_upload_parallel: int = 1) -> Dict:
    caps = server_caps()
    def clean(value, cap):
        try:
            value = int(value)
        except Exception:
            value = 1
        return max(1, min(value, cap))
    return {
        "upload_parallel": clean(upload_parallel, caps["max_upload_parallel"]),
        "convert_parallel": clean(convert_parallel, caps["max_convert_parallel"]),
        "import_upload_parallel": clean(import_upload_parallel, caps["max_import_upload_parallel"]),
    }

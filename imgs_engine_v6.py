"""
IMGS Engine v6 bridge.

This module separates the Streamlit GUI from the IMGS/TurboThinker training engine.
The UI imports from this bridge, while the heavy training logic remains in
imgs_training.py. That makes future engine upgrades easier without cluttering the
main dashboard code.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from imgs_training import *  # re-export the existing local engine API

IMGS_ENGINE_BRIDGE_VERSION = "IMGS Engine v6.0 bridge"


def build_conversion_record(count: int, output_format: str, seconds: float, destination: str = "image") -> Dict[str, Any]:
    """Small shared record for GUI timers and future engine telemetry."""
    safe_seconds = max(0.001, float(seconds))
    return {
        "version": IMGS_ENGINE_BRIDGE_VERSION,
        "count": int(count),
        "output_format": str(output_format).upper(),
        "seconds": round(safe_seconds, 3),
        "rate_per_second": round(int(count) / safe_seconds, 3) if count else 0.0,
        "destination": destination,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

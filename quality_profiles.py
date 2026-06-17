from __future__ import annotations

from collections import OrderedDict
from typing import Any, Dict

import streamlit as st

QUALITY_PROFILES: "OrderedDict[str, Dict[str, Any]]" = OrderedDict([
    ("720p fast", {"size": 720, "label": "720p", "note": "Fast previews and small downloads"}),
    ("1080p sharp", {"size": 1080, "label": "1080p", "note": "Best default for clean catalog images"}),
    ("2K product", {"size": 2160, "label": "2K", "note": "Sharper product/listing images"}),
    ("4K ultra", {"size": 4096, "label": "4K", "note": "TurboEmb v3 maximum quality for product/listing images"}),
    ("Custom", {"size": 1080, "label": "Custom", "note": "Choose your own square size"}),
])

SHARPNESS_PROFILES: "OrderedDict[str, Dict[str, Any]]" = OrderedDict([
    ("Clean", {"percent": 90, "radius": 0.6, "threshold": 3}),
    ("Sharp", {"percent": 130, "radius": 0.75, "threshold": 2}),
    ("Extra sharp", {"percent": 165, "radius": 0.9, "threshold": 1}),
])


def quality_size(profile: str, custom_size: int | None = None) -> int:
    if profile == "Custom" and custom_size:
        return int(custom_size)
    return int(QUALITY_PROFILES.get(profile, QUALITY_PROFILES["1080p sharp"])["size"])


def image_quality_selector(*, key_prefix: str, default: str = "1080p sharp", max_size: int = 4096, show_sharpness: bool = True) -> Dict[str, Any]:
    options = list(QUALITY_PROFILES.keys())
    default_index = options.index(default) if default in options else options.index("1080p sharp")
    col1, col2, col3 = st.columns(3)
    with col1:
        profile = st.selectbox("Image quality", options, index=default_index, key=f"{key_prefix}_quality_profile")
    with col2:
        base_size = quality_size(profile)
        if profile == "Custom":
            custom_size = st.number_input("Custom square size", min_value=512, max_value=max_size, value=1080, step=64, key=f"{key_prefix}_custom_size")
            size = int(custom_size)
        else:
            size = st.number_input("Square image size", min_value=512, max_value=max_size, value=base_size, step=64, key=f"{key_prefix}_image_size")
    with col3:
        if show_sharpness:
            sharpness = st.selectbox("Sharpness", list(SHARPNESS_PROFILES.keys()), index=1, key=f"{key_prefix}_sharpness")
        else:
            sharpness = "Sharp"
    note = QUALITY_PROFILES.get(profile, {}).get("note", "")
    st.caption(f"Selected: {profile} · {int(size)} × {int(size)} px · {sharpness}. {note}")
    if profile == "4K ultra":
        st.caption("Turbo Engine v4.6: 4K output is highest quality and may take longer on large stitch files.")
    return {"profile": profile, "size": int(size), "sharpness": sharpness, "sharpness_settings": SHARPNESS_PROFILES.get(sharpness, SHARPNESS_PROFILES["Sharp"])}

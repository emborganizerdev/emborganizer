"""Local launcher for the Streamlit EMBORGANIZER app.

Use:
    python app.py

On Streamlit Cloud, set the entry point to streamlit_app.py.
"""
from __future__ import annotations

import os
import subprocess
import sys


if __name__ == "__main__":
    port = os.environ.get("PORT", "8501")
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "streamlit_app.py",
        "--server.address",
        "0.0.0.0",
        "--server.port",
        str(port),
    ]
    raise SystemExit(subprocess.call(cmd))

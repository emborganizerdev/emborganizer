from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from turbothinker_superbrain import train_superbrain_model  # noqa: E402


def read_json(path: Path, default):
    if path.exists():
        return json.loads(path.read_text(encoding='utf-8'))
    return default


def main() -> int:
    seed_path = ROOT / 'imgs_training' / 'seed_training' / 'seed_visual_bank.json'
    corrections_path = ROOT / 'imgs_training' / 'corrections.json'
    seed_bank = read_json(seed_path, {})
    corrections = read_json(corrections_path, {})
    report = train_superbrain_model(ROOT, seed_bank, corrections, target_multiplier=5, max_memory_rows=5000)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

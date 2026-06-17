from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from turbothinker_model_store import load_json_model, storage_summary  # noqa: E402

MAX_BRAIN_PART_BYTES = 25_000_000


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'imgs_training' / 'models' / 'turbothinker_superbrain_v5_3_model.json'
    model = load_json_model(path, {})
    print(json.dumps(storage_summary(path), indent=2))
    if not model:
        print('ERROR: model did not load')
        return 2
    print('Loaded model:', model.get('version'))
    print('Labels:', len(model.get('output_labels') or []))
    print('Memory rows:', len(model.get('memory_rows') or []))
    summary = storage_summary(path)
    if int(summary.get('max_shard_bytes') or 0) >= MAX_BRAIN_PART_BYTES:
        print('ERROR: a brain part is >= 25 MB')
        return 3
    print('Brain-part size check: OK, every brain part is under 25 MB')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

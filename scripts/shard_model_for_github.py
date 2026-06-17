from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from turbothinker_model_store import save_json_model  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print('Usage: python scripts/shard_model_for_github.py path/to/model.json [shard_bytes]')
        return 2
    path = Path(sys.argv[1])
    shard_bytes = int(sys.argv[2]) if len(sys.argv) > 2 else 24_000_000
    data = json.loads(path.read_text(encoding='utf-8'))
    report = save_json_model(path, data, shard_size=shard_bytes, force_shards=True)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

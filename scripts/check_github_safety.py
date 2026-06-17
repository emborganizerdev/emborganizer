from __future__ import annotations

import sys
from pathlib import Path

MAX_NORMAL_GITHUB_FILE = 100 * 1024 * 1024
WARN_FILE = 25_000_000
IGNORE_DIR_PARTS = {'.git', '__pycache__', '.venv', 'venv'}


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('.')
    files = [p for p in root.rglob('*') if p.is_file() and not any(part in IGNORE_DIR_PARTS for part in p.parts)]
    too_big = []
    brain_parts_too_big = []
    warnings = []
    total = 0
    for p in files:
        size = p.stat().st_size
        total += size
        rel = p.relative_to(root)
        if size >= MAX_NORMAL_GITHUB_FILE:
            too_big.append((size, rel))
        elif size >= WARN_FILE:
            warnings.append((size, rel))
        if p.suffix == '.brainpart' and size >= 25_000_000:
            brain_parts_too_big.append((size, rel))
    print(f'Files checked: {len(files)}')
    print(f'Total bytes: {total:,}')
    print(f'Max file bytes: {max((p.stat().st_size for p in files), default=0):,}')
    if warnings:
        print('\nWarnings >= 25 MB:')
        for size, rel in sorted(warnings, reverse=True):
            print(f'  {size:,}  {rel}')
    if brain_parts_too_big:
        print('\nERROR: brain-part files must be under 25,000,000 bytes:')
        for size, rel in sorted(brain_parts_too_big, reverse=True):
            print(f'  {size:,}  {rel}')
        return 2
    if too_big:
        print('\nERROR: files >= 100 MB GitHub normal limit:')
        for size, rel in sorted(too_big, reverse=True):
            print(f'  {size:,}  {rel}')
        return 2
    print('GitHub safety: OK. No normal-Git file is over 100 MB and every .brainpart is under 25 MB.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

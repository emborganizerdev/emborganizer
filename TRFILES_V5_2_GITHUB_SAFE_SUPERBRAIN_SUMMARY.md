# EMBORGANIZER v5.3 TurboThinker SuperBrain GitHub-Safe Rebuild

## Main result

This build keeps the v5.1 SuperBrain training power but changes storage so the project can be uploaded to GitHub more safely.

## GitHub-safe changes

- Large monolithic SuperBrain model removed.
- New model path: `imgs_training/models/turbothinker_superbrain_v5_3_model.json`.
- The model path is a small redirect JSON.
- Real model data is split into shard files under: `imgs_training/models/shards/turbothinker_superbrain_v5_3_model/`.
- Shard count: `47`.
- Target shard size: about 24 MB.
- No file in this package is close to GitHub's 100 MB normal Git hard limit.

## Package stats

- Files in package: `112`
- Total unpacked bytes: `29239048`
- Largest single file bytes: `3355815`
- SuperBrain memory rows: `5,000`
- Output labels: `34`
- Cortex features: `454`
- Local-only: yes
- API use: no
- Filename/title label learning: no

## New support files

- `.gitignore`
- `.gitattributes`
- `turbothinker_model_store.py`
- `scripts/check_github_safety.py`
- `scripts/verify_model_shards.py`
- `scripts/shard_model_for_github.py`
- `scripts/train_superbrain_local.py`
- `docs/GITHUB_SAFE_USAGE.md`
- `docs/LOCAL_TRAINING_WORKFLOW.md`
- `.github/workflows/basic_check.yml`

## How to verify

```bash
python scripts/check_github_safety.py .
python scripts/verify_model_shards.py
```

## Important note

Keep raw image ZIPs, full embroidery libraries, generated previews, and caches out of GitHub. This build includes the trained sharded brain, not the original 403 MB TR image ZIP.

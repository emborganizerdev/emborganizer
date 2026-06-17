# EMBORGANIZER v5.3 GitHub-safe usage

This build is prepared so the project can be uploaded to GitHub without hitting normal GitHub file limits.

## What changed

- The large SuperBrain model is split into under-25MB `.brainpart` files.
- The normal model path is now a tiny redirect JSON.
- `turbothinker_model_store.py` automatically loads the brain parts and reconstructs the model in memory.
- `.gitignore` keeps raw image ZIPs, embroidery libraries, cache folders, and generated outputs local.
- `scripts/check_github_safety.py` checks for files that are too large for normal GitHub.

## Recommended GitHub contents

Commit:

- Python source files
- Streamlit app files
- tag catalog
- brain-part model files under `imgs_training/models/shards/`
- docs and scripts

Do not commit:

- raw `trfiles zip.zip`
- your full embroidery library
- generated previews and cache
- very large binary model formats unless you intentionally use Git LFS

## Verify before push

```bash
python scripts/check_github_safety.py .
python scripts/verify_model_shards.py
```

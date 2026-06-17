# EMBORGANIZER v5.3 TurboThinker SuperBrain 24MB Brain-Parts Replacement

This build replaces the old v5.2 SuperBrain shard layout with a cleaner v5.3 brain-part layout.

## What changed

- Old SuperBrain pointer removed: `turbothinker_superbrain_v5_2_model.json`.
- Old tiny shard folder removed: `imgs_training/models/shards/turbothinker_superbrain_v5_2_model/`.
- New SuperBrain pointer: `imgs_training/models/turbothinker_superbrain_v5_3_model.json`.
- New brain-part folder: `imgs_training/models/shards/turbothinker_superbrain_v5_3_model/`.
- Brain part extension: `.brainpart`.
- Target brain-part size: 24,000,000 bytes.
- Hard check: every `.brainpart` must stay under 25,000,000 bytes.

## Current trained brain storage

```json
{
  "exists": true,
  "storage": "json_brainparts",
  "model_path": "/mnt/data/emb_v53_24mb/imgs_training/models/turbothinker_superbrain_v5_3_model.json",
  "manifest": "shards/turbothinker_superbrain_v5_3_model/manifest.json",
  "total_bytes": 23063127,
  "shard_count": 1,
  "max_shard_bytes": 23063127
}
```

## Recognition brain kept from v5.2

- 454 cortex-expanded visual features.
- 34 output labels.
- 5,000 visual memory rows.
- Teacher correction priority.
- Failure diagnosis.
- TurboThinker GUI.
- Local-only, no API.
- Filename/title is not used as the label.

## GitHub rule for this build

Commit the code and the `.brainpart` files only when every brain part is below 25 MB. Keep raw image ZIPs, embroidery libraries, generated previews, and caches local.

Verify anytime:

```bash
python scripts/verify_model_shards.py
python scripts/check_github_safety.py .
```

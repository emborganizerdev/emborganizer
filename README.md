# EMBORGANIZER v6.0 — Super Dashboard + Folder Import

Local-only embroidery organizer, DST renderer, searcher, IMGS trainer, and library manager for Shiva Shanth.

## What changed in v6

- Added a **super dashboard / command center** with launch buttons to the main GUI pages.
- Added **Folder import (DST files)** through browser upload/drag-select. No typed local folder path is shown.
- Kept clean **DST/PES/JEF/etc. file upload** and **DST ZIP batch** import.
- Removed visible legacy image import options: image files, image ZIP, scan image folder.
- Removed the visible high-res/4K image reader page.
- Cleaned the converter UI: raw JSON detail blocks are replaced with friendly cards and chips.
- Added a conversion timer record: `X designs converted to PNG/JPG/WEBP in Y seconds`.
- Added `imgs_engine_v6.py` as a separate IMGS engine bridge so the Streamlit GUI stays cleaner.

## Main flow

1. Open the v6 dashboard.
2. Choose **Import** to add folder-selected DST/PES/JEF/etc. designs to the searchable library.
3. Choose **Convert** to create PNG/JPG/WEBP outputs and see the record timer.
4. Choose **Search**, **Teacher GUI**, or **IMGS Engine** for matching, corrections, and training.

## Run locally

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Or:

```bash
python app.py
```

Everything is local. No API is required for the core import, convert, search, and training flow.

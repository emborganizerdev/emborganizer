# TRFILES v5.4.3 Full Site Alive Summary

## Build name

`EMBORGANIZER v5.4.3 Full Site Alive + DST to PNG + Google Drive/Gmail + C++ 4K Reader`

## Why this version was created

The user said the previous rebuild lost the total site. This version restores the main legacy feature groups and keeps the newer TurboThinker/IMGS features alive.

## Added/restored

- DST to PNG Converter page
- 4K Design Reader page
- Maximum Library Manager page
- Google Drive page
- Gmail Sign In page
- Existing Import Library, Image Searcher, TurboThinker GUI, Interactive Searcher, IMGS Training BETA, Teach/Train, Library Cache, Brain Parts, Settings retained
- More loading animations and stepper indicators

## New modules

- `dst_converter.py`
  - pyembroidery reader when available
  - built-in DST fallback reader
  - TurboEmb C++ renderer integration
  - Python/Pillow fallback renderer
  - single file and ZIP batch conversion

- `library_manager.py`
  - summary, filters, exports, backups, duplicate checks, missing-file cleanup, and bulk relabel support

- `drive_gmail_bridge.py`
  - local Google OAuth config
  - public Drive link/file download
  - authenticated Drive browser helpers
  - Gmail profile and recent header helper

## Safety

- No external AI/API required for recognition or training.
- Google OAuth is optional and user-provided.
- `local_config/` and `downloads/` added to `.gitignore`.
- Raw embroidery files remain gitignored.

## Compile check

`python -m compileall -q .` completed successfully in the build folder.

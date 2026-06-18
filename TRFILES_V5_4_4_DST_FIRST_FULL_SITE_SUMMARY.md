# EMBORGANIZER v5.4.4 DST-First Full Site Summary

Build goal: restore full site behavior with DST files as the primary source, keep old source alive, and make TurboThinker identification meaningful.

## Added

- DST/PES/JEF/etc. import page as the main import mode.
- ZIP import for stitch files.
- Local folder scan for DST/stitch files.
- Legacy image import remains available.
- Search by DST file or by image.
- Meaningful design summary for stitch files: stitches, colors, bounds, density, reader, engine, work guess, neck guess, tags.
- Teacher-rule identification breakdown: shape first, work type second, motif/part third.
- Fixed numeric feature bugs in the local visual feature reader.
- Legacy v0.8.5 helper source files preserved as legacy_* modules.

## Important rules

- File names are record names only, not labels.
- DST is rendered first, then TurboThinker reads the rendered design visually.
- Cut work = irregular/scallop inside border that gives cut-work after stitching/cutting.
- Net work = drop/back-drop net/jali/vertical-line work.
- Rangoli = kolam/geometric loop-dot pattern.
- Normal work = smooth/regular embroidery without cut/net/rangoli identity.

## Testing

- Python compile check passed for project modules.
- GitHub safety check should be run before pushing if new local data is added.

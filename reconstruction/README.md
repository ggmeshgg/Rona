# Rona facsimile reconstruction

This directory is for rebuilding the book from the scan as a clean digital facsimile rather than merely sharpening page images.

The first prototype reconstructs PDF pages 70 and 83. It normalizes both scan batches to the canonical 410.4 × 580.32 pt page size measured from the later 300-DPI pages, redraws text/rules/page furniture as vectors, preserves the source line breaks and justified widths, and reuses only cleaned crops of the original illustrations.

Run locally with:

```bash
python .github/scripts/reconstruct_pages.py "Deutsch nach der Naturmethode kap. 1-36.pdf" --output reconstruction/output
```

The generated output contains individual SVG/PDF/PNG facsimiles, source-vs-reconstruction comparisons, a combined two-page PDF, and a JSON manifest.

This is intentionally an engine-independent reconstruction layer. Once the page/font measurements stabilize, the structured page specifications can be moved to LuaLaTeX/Typst without redoing OCR, illustration extraction, or geometry analysis.

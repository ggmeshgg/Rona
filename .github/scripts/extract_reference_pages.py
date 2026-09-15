#!/usr/bin/env python3
"""Extract representative PDF pages and record their scan/page geometry.

The output is intended for facsimile reconstruction analysis: it preserves the
source page as a one-page PDF, renders it at a fixed physical DPI, and records
PDF boxes plus raster-image placements so pages from different scan batches can
be compared without normalizing them destructively.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF
from PIL import Image, ImageDraw


def rect_dict(rect: fitz.Rect) -> dict[str, float]:
    return {
        "x0": round(rect.x0, 4),
        "y0": round(rect.y0, 4),
        "x1": round(rect.x1, 4),
        "y1": round(rect.y1, 4),
        "width": round(rect.width, 4),
        "height": round(rect.height, 4),
    }


def matrix_list(matrix: fitz.Matrix) -> list[float]:
    return [round(float(v), 6) for v in matrix]


def image_info(page: fitz.Page) -> list[dict[str, Any]]:
    images: list[dict[str, Any]] = []
    seen: set[tuple[int, float, float, float, float]] = set()

    for item in page.get_images(full=True):
        xref = int(item[0])
        smask = int(item[1])
        width_px = int(item[2])
        height_px = int(item[3])
        bpc = int(item[4])
        colorspace = item[5]
        name = item[7] if len(item) > 7 else None
        image_filter = item[8] if len(item) > 8 else None

        placements = page.get_image_rects(xref, transform=True)
        if not placements:
            images.append(
                {
                    "xref": xref,
                    "smask": smask,
                    "pixel_width": width_px,
                    "pixel_height": height_px,
                    "bits_per_component": bpc,
                    "colorspace": colorspace,
                    "name": name,
                    "filter": image_filter,
                    "placements": [],
                }
            )
            continue

        placement_rows = []
        for rect, transform in placements:
            key = (xref, rect.x0, rect.y0, rect.x1, rect.y1)
            if key in seen:
                continue
            seen.add(key)

            placed_w_in = rect.width / 72.0 if rect.width else 0.0
            placed_h_in = rect.height / 72.0 if rect.height else 0.0
            dpi_x = width_px / placed_w_in if placed_w_in else None
            dpi_y = height_px / placed_h_in if placed_h_in else None

            placement_rows.append(
                {
                    "rect_pt": rect_dict(rect),
                    "transform": matrix_list(transform),
                    "effective_dpi_x": round(dpi_x, 2) if dpi_x else None,
                    "effective_dpi_y": round(dpi_y, 2) if dpi_y else None,
                }
            )

        images.append(
            {
                "xref": xref,
                "smask": smask,
                "pixel_width": width_px,
                "pixel_height": height_px,
                "bits_per_component": bpc,
                "colorspace": colorspace,
                "name": name,
                "filter": image_filter,
                "placements": placement_rows,
            }
        )

    return images


def make_comparison(render_paths: list[tuple[int, Path]], output: Path) -> None:
    """Put pages side-by-side at identical DPI, so physical-size differences remain visible."""
    opened = [(page_no, Image.open(path).convert("RGB")) for page_no, path in render_paths]
    pad = 40
    label_h = 34
    gap = 60
    width = sum(im.width for _, im in opened) + gap * (len(opened) - 1) + pad * 2
    height = max(im.height for _, im in opened) + label_h + pad * 2
    canvas = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(canvas)

    x = pad
    for page_no, im in opened:
        draw.text((x, pad), f"PDF page {page_no} — fixed 300 DPI", fill="black")
        canvas.paste(im, (x, pad + label_h))
        x += im.width + gap

    canvas.save(output, optimize=True)
    for _, im in opened:
        im.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--pages", default="70,83", help="1-based PDF page numbers, comma-separated")
    parser.add_argument("--output", type=Path, default=Path("analysis/reference"))
    parser.add_argument("--dpi", type=int, default=300)
    args = parser.parse_args()

    pages = [int(p.strip()) for p in args.pages.split(",") if p.strip()]
    out = args.output
    pages_dir = out / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(args.pdf)
    summary: dict[str, Any] = {
        "source_pdf": str(args.pdf),
        "pdf_page_count": doc.page_count,
        "render_dpi": args.dpi,
        "pages": [],
    }
    rendered: list[tuple[int, Path]] = []

    for page_no in pages:
        if page_no < 1 or page_no > doc.page_count:
            raise SystemExit(f"Page {page_no} is outside PDF range 1..{doc.page_count}")

        idx = page_no - 1
        page = doc.load_page(idx)
        stem = f"p{page_no:03d}"

        # Keep an exact one-page PDF cut from the source.
        cut = fitz.open()
        cut.insert_pdf(doc, from_page=idx, to_page=idx)
        cut_path = pages_dir / f"{stem}.pdf"
        cut.save(cut_path, garbage=4, deflate=True)
        cut.close()

        # Render at one fixed physical DPI; do not resize pages to a common pixel box.
        pix = page.get_pixmap(dpi=args.dpi, alpha=False)
        png_path = pages_dir / f"{stem}-{args.dpi}dpi.png"
        pix.save(png_path)
        rendered.append((page_no, png_path))

        page_row = {
            "pdf_page_number": page_no,
            "pdf_page_index": idx,
            "rotation_degrees": page.rotation,
            "mediabox_pt": rect_dict(page.mediabox),
            "cropbox_pt": rect_dict(page.cropbox),
            "page_rect_pt": rect_dict(page.rect),
            "page_size_inches": {
                "width": round(page.rect.width / 72.0, 4),
                "height": round(page.rect.height / 72.0, 4),
            },
            "rendered_pixels": {"width": pix.width, "height": pix.height},
            "embedded_images": image_info(page),
            "outputs": {
                "cut_pdf": str(cut_path),
                "render_png": str(png_path),
            },
        }
        summary["pages"].append(page_row)

    summary_path = out / "geometry.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    comparison_path = out / "comparison-300dpi.png"
    make_comparison(rendered, comparison_path)

    md = [
        "# Representative page extraction",
        "",
        f"Source: `{args.pdf}`",
        f"PDF pages: {doc.page_count}",
        f"Rendered at: {args.dpi} DPI (same physical scale; no page-size normalization)",
        "",
        "| PDF page | Page size (pt) | Page size (in) | Rendered px | Embedded images |",
        "|---:|---:|---:|---:|---:|",
    ]
    for row in summary["pages"]:
        r = row["page_rect_pt"]
        ins = row["page_size_inches"]
        px = row["rendered_pixels"]
        md.append(
            f"| {row['pdf_page_number']} | {r['width']} × {r['height']} | "
            f"{ins['width']} × {ins['height']} | {px['width']} × {px['height']} | "
            f"{len(row['embedded_images'])} |"
        )
    md += [
        "",
        "See `geometry.json` for MediaBox/CropBox, raster dimensions, placements, transforms, and effective DPI.",
        "The side-by-side PNG intentionally keeps both pages at the same DPI, so a physical-size mismatch is visible rather than hidden by resizing.",
        "",
    ]
    (out / "README.md").write_text("\n".join(md), encoding="utf-8")
    doc.close()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Reconstruct representative book pages as clean facsimiles.

This is deliberately a hybrid reconstruction rather than a scan filter:
- page geometry, rules, headings and body copy are redrawn as vectors;
- original line breaks and justified line widths are preserved;
- illustrations are cropped from the source scan, background-cleaned, and
  placed back at their measured coordinates;
- broken early scan batches are normalized to the canonical 410.4 x 580.32 pt
  page size measured from the later 300-DPI pages.

Pages 70 and 83 are the first hand-verified page specifications.  The code is
structured so more page specs can be added without changing the renderer.
"""

from __future__ import annotations

import argparse
import base64
import html
import io
import json
from pathlib import Path

import cairosvg
import fitz
from PIL import Image, ImageFilter, ImageOps, ImageDraw

PAGE_W = 410.4
PAGE_H = 580.32
CANONICAL_PX = (1710, 2418)
FONT_FAMILY = "C059, Century Schoolbook, DejaVu Serif"


def render_page(doc: fitz.Document, page_no: int, dpi: int = 300) -> Image.Image:
    page = doc.load_page(page_no - 1)
    pix = page.get_pixmap(dpi=dpi, alpha=False)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples).convert("L")


def clean_crop_data_uri(image: Image.Image, box: tuple[int, int, int, int]) -> str:
    crop = image.crop(box).convert("L")
    crop = ImageOps.autocontrast(crop, cutoff=(0.2, 0.5))
    crop = crop.filter(ImageFilter.UnsharpMask(radius=1.0, percent=150, threshold=4))
    px = crop.load()
    rgba = Image.new("RGBA", crop.size, (0, 0, 0, 0))
    out = rgba.load()
    for y in range(crop.height):
        for x in range(crop.width):
            gray = px[x, y]
            level = max(0.0, min(1.0, (245.0 - gray) / 125.0))
            alpha = int((level ** 0.85) * 255.0)
            out[x, y] = (0, 0, 0, alpha)
    buf = io.BytesIO()
    rgba.save(buf, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def text_svg(
    x: float,
    y: float,
    text: str,
    *,
    size: float = 9.0,
    weight: int = 700,
    anchor: str = "start",
    family: str = FONT_FAMILY,
    text_length: float | None = None,
    length_adjust: str = "spacing",
    decoration: str | None = None,
) -> str:
    attrs = [
        f'x="{x:.3f}"',
        f'y="{y:.3f}"',
        f'font-family="{html.escape(family)}"',
        f'font-size="{size:.3f}"',
        f'font-weight="{weight}"',
        f'text-anchor="{anchor}"',
        'fill="#000000"',
    ]
    if text_length is not None:
        attrs += [f'textLength="{text_length:.3f}"', f'lengthAdjust="{length_adjust}"']
    if decoration:
        attrs.append(f'text-decoration="{decoration}"')
    return f'<text {" ".join(attrs)}>{html.escape(text)}</text>'


def image_svg(source: Image.Image, box: tuple[int, int, int, int], sx: float, sy: float) -> str:
    uri = clean_crop_data_uri(source, box)
    x0, y0, x1, y1 = box
    return (
        f'<image x="{x0 * sx:.3f}" y="{y0 * sy:.3f}" '
        f'width="{(x1 - x0) * sx:.3f}" height="{(y1 - y0) * sy:.3f}" '
        f'xlink:href="{uri}"/>'
    )


def svg_document(parts: list[str]) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{PAGE_W}pt" height="{PAGE_H}pt" viewBox="0 0 {PAGE_W} {PAGE_H}">'
        '<rect width="100%" height="100%" fill="white"/>'
        + "".join(parts)
        + "</svg>"
    )


def page_70(source: Image.Image) -> str:
    sx, sy = PAGE_W / source.width, PAGE_H / source.height
    lines = [
        ("In Deutschland nehmen die meisten Menschen drei", True),
        ("Hauptmahlzeiten ein. Auch in anderen Ländern nehmen", True),
        ("die Menschen meist drei Hauptmahlzeiten ein. Die", True),
        ("erste Mahlzeit des Tages nennen wir Frühstück. Viele", True),
        ("Menschen trinken Kaffee oder Tee und essen Brot und", True),
        ("Butter zum Frühstück. Manche nehmen auch Marmelade", True),
        ("oder Honig oder Aufschnitt (Schinken, Wurst und", True),
        ("so weiter). Marmelade wird aus Obst gemacht. Die Kin-", True),
        ("der trinken Milch oder Kakao zum Frühstück und essen", True),
        ("Brot mit Butter und Marmelade; manche Kinder essen", True),
        ("auch Cornflakes.", False),
        ("Die nächste Hauptmahlzeit ist das Mittagessen um", True),
        ("zwölf oder ein Uhr. Frau Müller und die Kinder essen", True),
        ("zu Mittag, wenn die Kinder von der Schule nach Hause", True),
        ("kommen. Herr Müller kommt erst um halb fünf Uhr nach", True),
        ("Hause. Er hat aber eine Stunde Mittagspause und isst", True),
        ("zu Mittag in der Kantine an seinem Arbeitsplatz. Das", True),
        ("Mittagessen ist die grösste Mahlzeit des Tages. Die", True),
        ("meisten Menschen essen Fleisch, Kartoffeln und", True),
        ("Gemüse zu Mittag. Das Fleisch der Kühe ist Rindfleisch.", True),
        ("Die Karotte ist ein Gemüse. Spinat ist ein Gemüse.", False),
    ]
    p: list[str] = []
    p.append(f'<line x1="{62*sx:.3f}" y1="{52*sy:.3f}" x2="{913*sx:.3f}" y2="{52*sy:.3f}" stroke="black" stroke-width="1"/>')
    p.append(f'<line x1="{282*sx:.3f}" y1="{88*sy:.3f}" x2="{282*sx:.3f}" y2="{1247*sy:.3f}" stroke="black" stroke-width="1"/>')
    p.append(f'<line x1="{62*sx:.3f}" y1="{91*sy:.3f}" x2="{641*sx:.3f}" y2="{91*sy:.3f}" stroke="black" stroke-width="1"/>')
    p.append(text_svg(63*sx, 88*sy, "Kapitel Zwölf (12)", size=8.8))
    p.append(text_svg(912*sx, 88*sy, "Zwölftes (12.) Kapitel", size=8.8, anchor="end"))
    p.append(text_svg(585*sx, 170*sy, "MAHLZEITEN", size=9.6, anchor="middle"))

    x = 290 * sx
    width = (875 - 290) * sx
    y0 = 264 * sy
    leading = 48 * sy
    for i, (line, justified) in enumerate(lines):
        p.append(text_svg(x, y0 + i * leading, line, text_length=width if justified else None))

    p.append(image_svg(source, (62, 165, 210, 275), sx, sy))
    p.append(text_svg(63*sx, 301*sy, "Brot", size=7.4))
    p.append(image_svg(source, (66, 450, 225, 540), sx, sy))
    p.append(text_svg(88*sx, 557*sy, "Schinken", size=7.2))
    p.append(image_svg(source, (92, 648, 198, 736), sx, sy))
    p.append(text_svg(88*sx, 758*sy, "Wurst", size=7.2))

    yy = 816
    for dy, label in [(0,"ich esse"),(23,"du"),(42,"er"),(61,"sie"),(80,"es")]:
        p.append(text_svg(61*sx, (yy+dy)*sy, label, size=6.8))
    p.append(text_svg(110*sx, (yy+61)*sy, "}", size=25, weight=400, anchor="middle", family="DejaVu Serif"))
    p.append(text_svg(136*sx, (yy+61)*sy, "isst", size=6.8))
    for dy, label in [(105,"wir essen"),(128,"ihr esst"),(151,"sie essen")]:
        p.append(text_svg(61*sx, (yy+dy)*sy, label, size=6.8))

    p.append(text_svg(62*sx, 1150*sy, "Rind = Kuh", size=7.1))
    p.append(image_svg(source, (138, 1146, 225, 1284), sx, sy))
    p.append(text_svg(62*sx, 1242*sy, "Karotte", size=7.1))
    p.append(text_svg(86*sx, 1305*sy, "69", size=8.0))
    return svg_document(p)


def page_83(source: Image.Image) -> str:
    sx, sy = PAGE_W / source.width, PAGE_H / source.height
    lines = [
        ("Ja, aber die Stühle im Speisezimmer sind nicht so", True),
        ("gross wie die im Wohnzimmer. Steht auch ein Tisch", True),
        ("im Speisezimmer? Ja, die Familie nimmt ihre Mahlzeiten", True),
        ("an einem grossen Tisch im Speisezimmer ein.", False),
        ("Jedes Zimmer in Herrn Müllers Haus hat vier Wände,", True),
        ("eine Decke und einen Fussboden. Auch die Küche hat", True),
        ("vier Wände, eine Decke und einen Fussboden. An der", True),
        ("Decke hängt eine Lampe. Die Lampe gibt Licht am", True),
        ("Abend, so dass man lesen kann. Am Tag ist es hell,", True),
        ("aber am Abend ist es dunkel. Man kann nicht lesen,", True),
        ("wenn es dunkel ist. Herrn Müllers Haus hat zwei", True),
        ("Gärten, einen vor dem Haus und einen hinter dem", True),
        ("Haus. Wenn wir durch den Vorgarten gehen, kommen", True),
        ("wir zuerst in die Diele. In der Diele hängt man", True),
        ("Hut und Mantel auf.", False),
        ("Das Speisezimmer, das Wohnzimmer, die Küche und die", True),
        ("Diele liegen alle im Erdgeschoss. Im ersten Stock", True),
        ("des Hauses sind drei Schlafzimmer. Herr und Frau", True),
        ("Müller schlafen in einem Schlafzimmer. Hans schläft", True),
        ("in einem anderen Schlafzimmer, und Lotte und das", True),
        ("Baby schlafen im dritten Schlafzimmer.", False),
        ("In welchem Stock ist das Speisezimmer? Das", True),
        ("Speisezimmer ist im Erdgeschoss. In welchem Stock", True),
        ("liegt das Schlafzimmer von Lotte und dem Baby? Es", True),
    ]
    p: list[str] = []
    p.append('<line x1="30.3" y1="43.1" x2="386.6" y2="43.1" stroke="black" stroke-width="1"/>')
    p.append('<line x1="287.3" y1="43.1" x2="287.3" y2="547.0" stroke="black" stroke-width="1"/>')
    p.append(text_svg(386.6, 40.1, "Vierzehntes (14.) Kapitel", size=9.2, anchor="end"))

    x, width, y0, leading = 30.5, 252.0, 56.55, 20.64
    squeeze = {2, 4, 5, 12, 15}
    for i, (line, justified) in enumerate(lines):
        p.append(text_svg(
            x, y0 + i*leading, line,
            text_length=width if justified else None,
            length_adjust="spacingAndGlyphs" if i in squeeze else "spacing",
        ))

    p.append(text_svg(293.0, 77.0, "die; die Stühle", size=7.9))
    p.append(image_svg(source, (1325, 450, 1620, 790), sx, sy))
    p.append(text_svg(325.5, 106.0, "Decke", size=8.2))
    p.append(text_svg(316.8, 196.6, "Fussboden", size=8.0))
    p.append(image_svg(source, (1340, 900, 1585, 1070), sx, sy))
    p.append(text_svg(293.0, 245.5, "Lampe", size=8.0))
    p.append(text_svg(293.0, 267.0, "hell ↔ dunkel", size=8.0))
    p.append(text_svg(293.0, 286.5, "Das Licht der", size=7.7))
    p.append(text_svg(293.0, 300.5, "Lampe macht das", size=7.7))
    p.append(text_svg(293.0, 314.5, "Zimmer hell.", size=7.7))
    p.append('<line x1="309.3" y1="288.0" x2="325.9" y2="288.0" stroke="black" stroke-width="0.55"/>')
    p.append('<line x1="319.3" y1="316.0" x2="334.7" y2="316.0" stroke="black" stroke-width="0.55"/>')
    p.append(text_svg(293.0, 336.5, "vor ↔ hinter", size=8.0))
    p.append(image_svg(source, (1360, 1515, 1505, 1610), sx, sy))
    p.append(text_svg(293.0, 378.0, "Hut", size=8.0))
    p.append(image_svg(source, (1335, 1660, 1605, 2035), sx, sy))
    p.append(text_svg(293.0, 434.0, "Mantel", size=8.0))
    p.append(text_svg(365.5, 565.5, "83", size=8.5))
    return svg_document(p)


def write_page(svg: str, output_dir: Path, stem: str) -> tuple[Path, Path, Path]:
    svg_path = output_dir / f"{stem}.svg"
    png_path = output_dir / f"{stem}.png"
    pdf_path = output_dir / f"{stem}.pdf"
    svg_path.write_text(svg, encoding="utf-8")
    cairosvg.svg2png(bytestring=svg.encode("utf-8"), write_to=str(png_path), output_width=CANONICAL_PX[0], output_height=CANONICAL_PX[1])
    cairosvg.svg2pdf(bytestring=svg.encode("utf-8"), write_to=str(pdf_path))
    return svg_path, png_path, pdf_path


def comparison(source: Image.Image, reconstructed_png: Path, output: Path) -> None:
    src = source.convert("RGB").resize(CANONICAL_PX, Image.Resampling.LANCZOS)
    recon = Image.open(reconstructed_png).convert("RGB")
    gap = 40
    canvas = Image.new("RGB", (src.width + recon.width + gap, src.height), "white")
    canvas.paste(src, (0, 0))
    canvas.paste(recon, (src.width + gap, 0))
    draw = ImageDraw.Draw(canvas)
    draw.text((25, 20), "source scan (normalized)", fill="black")
    draw.text((src.width + gap + 25, 20), "reconstructed facsimile", fill="black")
    canvas.save(output, optimize=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--output", type=Path, default=Path("reconstruction/output"))
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(args.pdf)
    source70 = render_page(doc, 70)
    source83 = render_page(doc, 83)

    outputs = {}
    for page_no, source, builder in [(70, source70, page_70), (83, source83, page_83)]:
        stem = f"p{page_no:03d}-reconstructed"
        svg_path, png_path, pdf_path = write_page(builder(source), args.output, stem)
        compare_path = args.output / f"p{page_no:03d}-comparison.png"
        comparison(source, png_path, compare_path)
        outputs[str(page_no)] = {
            "svg": str(svg_path),
            "png": str(png_path),
            "pdf": str(pdf_path),
            "comparison": str(compare_path),
            "source_render_px": list(source.size),
        }

    combined = fitz.open()
    for page_no in (70, 83):
        one = fitz.open(outputs[str(page_no)]["pdf"])
        combined.insert_pdf(one)
        one.close()
    combined_path = args.output / "reconstructed-pages-70-83.pdf"
    combined.save(combined_path, garbage=4, deflate=True)
    combined.close()

    manifest = {
        "canonical_page_pt": [PAGE_W, PAGE_H],
        "canonical_render_px": list(CANONICAL_PX),
        "renderer": "SVG + CairoSVG; C059/Schoolbook-style vector type; restored source line art",
        "pages": outputs,
        "combined_pdf": str(combined_path),
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (args.output / "README.md").write_text(
        "# Reconstructed facsimile prototype\n\n"
        "Pages 70 and 83 are reconstructed at the canonical 410.4 × 580.32 pt page size. "
        "Body text, rules, headers, page numbers, and sidebar labels are newly rendered vectors. "
        "Only the original line drawings are retained as cleaned raster fragments.\n\n"
        "The comparison PNGs show the normalized source on the left and reconstruction on the right.\n",
        encoding="utf-8",
    )
    doc.close()


if __name__ == "__main__":
    main()

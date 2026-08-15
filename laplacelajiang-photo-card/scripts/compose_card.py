"""Compose a selected editorial photo card using catalog-driven layouts and exact text."""

from __future__ import annotations

import argparse
import hashlib
import json
import textwrap
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


DEFAULT_SIZE = (1200, 1600)


def parse_size(value: str) -> tuple[int, int]:
    if "x" in value.lower():
        width, height = value.lower().split("x", 1)
        result = int(width), int(height)
    elif ":" in value:
        rw, rh = (float(part) for part in value.split(":", 1))
        if rw <= 0 or rh <= 0:
            raise ValueError("ratio values must be greater than zero")
        result = DEFAULT_SIZE[0], round(DEFAULT_SIZE[0] * rh / rw)
    else:
        raise ValueError("size must be WIDTHxHEIGHT or WIDTH:HEIGHT")
    if min(result) < 256:
        raise ValueError("both dimensions must be at least 256 pixels")
    return result


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def font_or_default(size: int, bold: bool = False):
    candidates = [
        Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def fit_cover(
    image: Image.Image, size: tuple[int, int], centering=(0.5, 0.5)
) -> Image.Image:
    return ImageOps.fit(
        image.convert("RGB"), size, method=Image.Resampling.LANCZOS, centering=centering
    )


def find_item(catalog: dict, preset: str) -> dict:
    for item in catalog["native_presets"] + catalog["reference_result_presets"]:
        if item["id"] == preset:
            return item
    raise ValueError(f"preset is not registered: {preset}")


def text_overlay(
    size: tuple[int, int],
    title: str,
    subtitle: str,
    microcopy: str,
    ink: str,
    paper: str,
) -> Image.Image:
    width, height = size
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    margin = round(width * 0.05)
    title_font = font_or_default(max(34, width // 17), bold=True)
    subtitle_font = font_or_default(max(20, width // 33))
    micro_font = font_or_default(max(15, width // 58))
    y = margin
    title_lines = textwrap.wrap(title, width=max(10, width // 58))[:2] or [""]
    for line in title_lines:
        draw.text((margin, y), line, font=title_font, fill=ink)
        y += draw.textbbox((0, 0), line, font=title_font)[3] + 6
    if subtitle:
        y += 4
        draw.text((margin, y), subtitle, font=subtitle_font, fill=ink)
        y += draw.textbbox((0, 0), subtitle, font=subtitle_font)[3] + 10
    if microcopy:
        for line in textwrap.wrap(microcopy, width=max(28, width // 13))[:3]:
            draw.text((margin, y), line, font=micro_font, fill=ink)
            y += draw.textbbox((0, 0), line, font=micro_font)[3] + 4
    return layer


def layout_split(
    canvas: Image.Image, photo: Image.Image, panel: Image.Image, theme: dict, top: int
) -> tuple[Image.Image, Image.Image]:
    width, height = canvas.size
    margin, gap = round(width * 0.05), round(width * 0.025)
    content_h = height - top - round(height * 0.11)
    column_w = (width - 2 * margin - gap) // 2
    photo_layer = fit_cover(photo, (column_w, content_h))
    panel_layer = fit_cover(panel, (column_w, content_h))
    canvas.paste(photo_layer, (margin, top))
    canvas.paste(panel_layer, (margin + column_w + gap, top))
    draw = ImageDraw.Draw(canvas)
    for x in (margin, margin + column_w + gap):
        draw.rectangle(
            (x, top, x + column_w, top + content_h), outline=theme["ink"], width=3
        )
    return photo_layer, panel_layer


def layout_stacked(
    canvas: Image.Image, photo: Image.Image, panel: Image.Image, theme: dict, top: int
) -> tuple[Image.Image, Image.Image]:
    width, height = canvas.size
    margin, gap = round(width * 0.05), round(height * 0.025)
    content_w = width - 2 * margin
    content_h = height - top - round(height * 0.07)
    photo_h = round(content_h * 0.61)
    panel_h = content_h - photo_h - gap
    photo_layer = fit_cover(photo, (content_w, photo_h))
    panel_layer = fit_cover(panel, (content_w, panel_h))
    canvas.paste(photo_layer, (margin, top))
    canvas.paste(panel_layer, (margin, top + photo_h + gap))
    return photo_layer, panel_layer


def layout_board(
    canvas: Image.Image, photo: Image.Image, panel: Image.Image, theme: dict, top: int
) -> tuple[Image.Image, Image.Image]:
    width, height = canvas.size
    margin, gap = round(width * 0.05), round(width * 0.025)
    content_h = height - top - round(height * 0.06)
    main_w = round((width - 2 * margin - gap) * 0.64)
    side_w = width - 2 * margin - gap - main_w
    photo_layer = fit_cover(photo, (main_w, content_h))
    panel_layer = fit_cover(panel, (side_w, content_h))
    canvas.paste(photo_layer, (margin, top))
    canvas.paste(panel_layer, (margin + main_w + gap, top))
    draw = ImageDraw.Draw(canvas)
    marker = theme["accent"]
    for fraction in (0.22, 0.49, 0.76):
        y = top + round(content_h * fraction)
        draw.line((margin + main_w + gap, y, width - margin, y), fill=marker, width=2)
    return photo_layer, panel_layer


def layout_full_bleed(
    canvas: Image.Image, photo: Image.Image, panel: Image.Image, theme: dict, top: int
) -> tuple[Image.Image, Image.Image]:
    width, height = canvas.size
    photo_layer = fit_cover(photo, (width, height))
    panel_layer = fit_cover(panel, (width, height))
    blended = Image.blend(photo_layer, panel_layer, 0.58)
    canvas.paste(blended, (0, 0))
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle((0, 0, width, round(height * 0.22)), fill=(244, 240, 232, 218))
    canvas.paste(overlay.convert("RGB"), (0, 0), overlay)
    return photo_layer, panel_layer


LAYOUTS = {
    "split": layout_split,
    "stacked": layout_stacked,
    "board": layout_board,
    "full-bleed": layout_full_bleed,
}


def compose(args: argparse.Namespace) -> dict:
    catalog_path = args.catalog.resolve()
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    selection = json.loads(args.selection_lock.read_text(encoding="utf-8"))
    if selection["catalog_sha256"] != sha256(catalog_path):
        raise SystemExit("selection lock does not match the current catalog")
    locked_items = selection.get("items") or [
        {"preset": selection["primary_preset"]}
    ]
    if args.preset:
        matches = [entry for entry in locked_items if entry["preset"] == args.preset]
        if not matches:
            raise SystemExit(f"preset is not in the selected collection: {args.preset}")
        preset = args.preset
    elif len(locked_items) == 1:
        preset = locked_items[0]["preset"]
    else:
        raise SystemExit("--preset is required for a multi-artwork collection")
    item = find_item(catalog, preset)
    width, height = parse_size(args.size)
    output_dir = args.output_dir.resolve()
    final_dir, layers_dir = output_dir / "final", output_dir / "layers"
    final_dir.mkdir(parents=True, exist_ok=True)
    layers_dir.mkdir(parents=True, exist_ok=True)
    if not args.photo.is_file():
        raise SystemExit(f"photo does not exist: {args.photo}")
    if not args.panel.is_file():
        raise SystemExit(f"panel does not exist: {args.panel}")
    try:
        with Image.open(args.photo) as image:
            photo = ImageOps.exif_transpose(image).convert("RGB")
        with Image.open(args.panel) as image:
            panel = ImageOps.exif_transpose(image).convert("RGB")
    except Exception as exc:
        raise SystemExit(f"cannot read photo or panel image: {exc}") from exc
    theme = item["theme"]
    canvas = Image.new("RGB", (width, height), theme["paper"])
    top = round(height * 0.23)
    photo_layer, panel_layer = LAYOUTS[item["layout"]](canvas, photo, panel, theme, top)
    overlay = text_overlay(
        (width, height),
        args.title,
        args.subtitle,
        args.microcopy,
        theme["ink"],
        theme["paper"],
    )
    canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")
    canvas.save(final_dir / "editorial-card.png", optimize=True)
    canvas.save(final_dir / "editorial-card.jpg", quality=94, optimize=True)
    photo_layer.save(layers_dir / "photo-primary.png")
    panel_layer.save(layers_dir / "design-panel.png")
    overlay.save(layers_dir / "text-overlay.png")
    metadata = {
        "skill": "laplacelajiang-photo-card",
        "schema_version": 2,
        "stage": "rendering",
        "primary_preset": preset,
        "blend_presets": selection.get("blend_presets", []),
        "layout": item["layout"],
        "width": width,
        "height": height,
        "ratio": f"{width}:{height}",
        "language": args.language,
        "title": args.title,
        "subtitle": args.subtitle,
        "microcopy": args.microcopy,
        "source_ids": [Path(args.photo).name, Path(args.panel).name],
        "catalog_sha256": sha256(catalog_path),
        "custom_reference": args.custom_reference,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return metadata


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--photo", type=Path, required=True)
    parser.add_argument("--panel", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--selection-lock", type=Path, required=True)
    parser.add_argument("--preset")
    parser.add_argument("--title", default="EDITORIAL STUDY")
    parser.add_argument("--subtitle", default="")
    parser.add_argument("--microcopy", default="")
    parser.add_argument("--size", default="1200x1600")
    parser.add_argument("--ratio", default="3:4")
    parser.add_argument("--language", default="zh-CN")
    parser.add_argument("--custom-reference", action="store_true")
    return parser


if __name__ == "__main__":
    compose(build_parser().parse_args())

"""Build a grouped, labeled thumbnail gallery from the integrated preset catalog."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


def font(size: int, bold: bool = False):
    candidates = [
        Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def parse_item(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise ValueError(f"item must use STYLE=IMAGE, got: {value}")
    label, path = value.split("=", 1)
    if not label or not path:
        raise ValueError(f"item must use STYLE=IMAGE, got: {value}")
    return label, Path(path)


def load_catalog(path: Path, preview_dir: Path) -> list[dict]:
    catalog = json.loads(path.read_text(encoding="utf-8"))
    result = []
    for group_key, group_label in (
        ("native_presets", "NATIVE PRESETS / 自建风格"),
        ("reference_result_presets", "REFERENCE RESULTS / 参考结果"),
    ):
        for item in catalog[group_key]:
            source = item.get("source_project") or ""
            result.append(
                {
                    "id": item["id"],
                    "label": item["label"],
                    "group": group_label,
                    "source": source.rstrip("/").split("/")[-1]
                    if source
                    else "LaplaceLajiang",
                    "path": preview_dir / f"{item['id']}.png",
                }
            )
    return result


def draw_fitted(
    draw: ImageDraw.ImageDraw,
    text: str,
    box: tuple[int, int, int, int],
    bold: bool = False,
    start: int = 24,
) -> None:
    x0, y0, x1, y1 = box
    for size in range(start, 11, -1):
        candidate = font(size, bold=bold)
        width = draw.textbbox((0, 0), text, font=candidate)[2]
        if width <= x1 - x0:
            draw.text((x0, y0), text, font=candidate, fill="#1E1D1B")
            return
    draw.text((x0, y0), text[:48], font=font(11, bold=bold), fill="#1E1D1B")


def make_sheet(
    items: list[dict], output: Path, columns: int, thumb_width: int, thumb_height: int
) -> None:
    if not items:
        raise ValueError("at least one item is required")
    gap = 28
    header_height = 132
    group_height = 56
    label_height = 94
    width = columns * thumb_width + (columns + 1) * gap
    groups: list[tuple[str, list[dict]]] = []
    for item in items:
        if not groups or groups[-1][0] != item["group"]:
            groups.append((item["group"], []))
        groups[-1][1].append(item)
    height = header_height + gap
    for _, group_items in groups:
        rows = (len(group_items) + columns - 1) // columns
        height += group_height + rows * (thumb_height + label_height + gap)
    height += gap
    sheet = Image.new("RGB", (width, height), "#F4F0E8")
    draw = ImageDraw.Draw(sheet)
    draw.text(
        (gap, 26),
        "LAPLACELAJIANG STYLE GALLERY",
        font=font(34, bold=True),
        fill="#1E1D1B",
    )
    draw.text(
        (gap, 76),
        f"{len(items)} directions · choose before high-resolution generation / 仅供选型",
        font=font(17),
        fill="#5D5A53",
    )

    y_cursor = header_height
    global_index = 1
    for group_name, group_items in groups:
        draw.rectangle(
            (gap, y_cursor, width - gap, y_cursor + group_height - 8), fill="#24231F"
        )
        draw.text(
            (gap + 18, y_cursor + 11),
            group_name,
            font=font(22, bold=True),
            fill="#F4F0E8",
        )
        y_cursor += group_height
        for local_index, item in enumerate(group_items):
            row, column = divmod(local_index, columns)
            x = gap + column * (thumb_width + gap)
            y = y_cursor + row * (thumb_height + label_height + gap)
            if not item["path"].is_file():
                raise FileNotFoundError(item["path"])
            with Image.open(item["path"]) as opened:
                preview = opened.convert("RGB")
                thumb = ImageOps.fit(
                    preview,
                    (thumb_width, thumb_height),
                    method=Image.Resampling.LANCZOS,
                )
            sheet.paste(thumb, (x, y))
            draw.rectangle(
                (x, y, x + thumb_width, y + thumb_height), outline="#1E1D1B", width=2
            )
            index_text = f"{global_index:02d}"
            draw.rounded_rectangle(
                (x + 12, y + 12, x + 62, y + 48), radius=8, fill="#F4F0E8"
            )
            draw.text(
                (x + 22, y + 18), index_text, font=font(17, bold=True), fill="#1E1D1B"
            )
            draw_fitted(
                draw,
                item["label"],
                (x, y + thumb_height + 12, x + thumb_width, y + thumb_height + 42),
                bold=True,
                start=20,
            )
            source = f"source: {item['source']}"
            draw.text((x, y + thumb_height + 50), source, font=font(14), fill="#6C685F")
            global_index += 1
        rows = (len(group_items) + columns - 1) // columns
        y_cursor += rows * (thumb_height + label_height + gap)

    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, optimize=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--preview-dir", type=Path)
    parser.add_argument(
        "--item",
        action="append",
        help="Legacy STYLE=IMAGE input; repeat for every preset",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--columns", type=int, default=3)
    parser.add_argument("--thumb-width", type=int, default=360)
    parser.add_argument("--thumb-height", type=int, default=480)
    args = parser.parse_args()
    if args.columns < 1:
        raise SystemExit("--columns must be at least 1")
    if args.catalog or args.preview_dir:
        if not args.catalog or not args.preview_dir:
            raise SystemExit("--catalog and --preview-dir must be used together")
        items = load_catalog(args.catalog, args.preview_dir)
    else:
        if not args.item:
            raise SystemExit("use --catalog/--preview-dir or at least one --item")
        items = [
            {
                "id": label,
                "label": label,
                "group": "STYLE PRESETS",
                "source": "custom",
                "path": path,
            }
            for label, path in (parse_item(value) for value in args.item)
        ]
    make_sheet(items, args.output, args.columns, args.thumb_width, args.thumb_height)
    print(f"PASS: wrote {len(items)}-style gallery to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

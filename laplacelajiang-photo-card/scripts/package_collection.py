"""Package selected artworks into a verified take-home collection."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import zipfile
from datetime import datetime, timezone
from html import escape
from pathlib import Path

from PIL import Image, ImageOps


XHS_SIZE = (1800, 2400)
XHS_PAPER = (239, 232, 219)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def selected_items(lock: dict) -> list[dict]:
    return lock.get("items") or [
        {
            "preset": lock["primary_preset"],
            "number": lock.get("primary_number", 1),
            "blend_presets": lock.get("blend_presets", []),
        }
    ]


def artwork_dir(take_home: Path, entry: dict) -> Path:
    return take_home / f"{entry['number']:02d}-{entry['preset']}"


def inspect_image(path: Path) -> dict:
    if not path.is_file():
        raise SystemExit(f"selected artwork is not ready: {path}")
    with Image.open(path) as image:
        image.verify()
    with Image.open(path) as image:
        width, height = image.size
        mode = image.mode
    return {
        "path": path,
        "sha256": sha256(path),
        "width": width,
        "height": height,
        "mode": mode,
        "bytes": path.stat().st_size,
    }


def build_xhs_variant(master: Path, target: Path) -> None:
    with Image.open(master) as opened:
        source = ImageOps.exif_transpose(opened).convert("RGB")
        fitted = ImageOps.contain(source, (1640, 2240), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", XHS_SIZE, XHS_PAPER)
        x = (XHS_SIZE[0] - fitted.width) // 2
        y = (XHS_SIZE[1] - fitted.height) // 2
        canvas.paste(fitted, (x, y))
        canvas.save(target, "JPEG", quality=95, optimize=True, progressive=True)


def normalize_outputs(root: Path) -> dict[str, dict]:
    final_dir = root / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    legacy_png = final_dir / "editorial-card.png"
    legacy_jpg = final_dir / "editorial-card.jpg"
    master = final_dir / "master.png"
    xhs = final_dir / "xhs-3x4.jpg"

    if not master.is_file():
        if not legacy_png.is_file():
            raise SystemExit(f"high-resolution master is missing: {master}")
        shutil.copy2(legacy_png, master)
    if not xhs.is_file():
        build_xhs_variant(master, xhs)

    outputs = {
        "master": inspect_image(master),
        "xhs_3x4": inspect_image(xhs),
    }
    if legacy_png.is_file():
        outputs["legacy_png"] = inspect_image(legacy_png)
    if legacy_jpg.is_file():
        outputs["legacy_jpg"] = inspect_image(legacy_jpg)
    return outputs


def write_artwork_documents(
    root: Path,
    entry: dict,
    catalog_item: dict,
    metadata: dict,
    outputs: dict[str, dict],
) -> tuple[Path, Path, Path]:
    label_path = root / "展签.md"
    label_path.write_text(
        "\n".join(
            [
                f"# #{entry['number']:02d} {catalog_item['label']}",
                "",
                f"- 风格：{catalog_item['label']}",
                f"- 版式：{catalog_item['layout']}",
                f"- 标题：{metadata.get('title') or '未设置'}",
                f"- 副标题：{metadata.get('subtitle') or '未设置'}",
                "- 母版：`final/master.png`",
                "- 小红书 3:4 版：`final/xhs-3x4.jpg`",
                "",
                "本展签随作品交付，用于记录本次装裱信息；不替代原图版权证明。",
            ]
        ),
        encoding="utf-8",
    )

    generation_path = root / "generation-record.json"
    save(
        generation_path,
        {
            "schema_version": 1,
            "generated_at": metadata.get("generated_at"),
            "packaged_at": now(),
            "preset": entry["preset"],
            "number": entry["number"],
            "layout": catalog_item["layout"],
            "source_ids": metadata.get("source_ids", []),
            "catalog_sha256": metadata.get("catalog_sha256"),
            "outputs": {
                key: {
                    field: value[field]
                    for field in ("sha256", "width", "height", "mode", "bytes")
                }
                for key, value in outputs.items()
            },
        },
    )

    qa_path = root / "qa-record.json"
    master = outputs["master"]
    xhs = outputs["xhs_3x4"]
    checks = {
        "master_readable": True,
        "master_minimum_long_edge_1600": max(
            master["width"], master["height"]
        )
        >= 1600,
        "xhs_readable": True,
        "xhs_exact_3x4_1800x2400": (
            xhs["width"], xhs["height"]
        )
        == XHS_SIZE,
        "metadata_preset_matches": metadata.get("primary_preset")
        == entry["preset"],
    }
    save(
        qa_path,
        {
            "schema_version": 1,
            "checked_at": now(),
            "automated_checks": checks,
            "automated_result": "PASS" if all(checks.values()) else "FAIL",
            "manual_visual_review": "see delivery-level qa-report.md",
        },
    )
    if not all(checks.values()):
        failed = [key for key, value in checks.items() if not value]
        raise SystemExit(
            f"artwork package quality gate failed for {entry['preset']}: {failed}"
        )
    return label_path, generation_path, qa_path


def relative_output(delivery: Path, details: dict) -> dict:
    return {
        key: details[key]
        for key in ("sha256", "width", "height", "mode", "bytes")
    } | {"path": details["path"].relative_to(delivery).as_posix()}


def package(delivery: Path) -> tuple[Path, Path]:
    delivery = delivery.resolve()
    lock = load(delivery / "selection.lock.json")
    catalog = load(delivery / "catalog.snapshot.json")
    by_id = {
        item["id"]: item
        for item in catalog["native_presets"]
        + catalog["reference_result_presets"]
    }
    entries = selected_items(lock)
    take_home = delivery / "take-home"
    take_home.mkdir(parents=True, exist_ok=True)
    packaged = []
    for entry in entries:
        preset = entry["preset"]
        if preset not in by_id:
            raise SystemExit(f"selected preset is not registered: {preset}")
        root = artwork_dir(take_home, entry)
        metadata_path = root / "metadata.json"
        if not metadata_path.is_file():
            raise SystemExit(f"selected artwork metadata is missing: {metadata_path}")
        metadata = load(metadata_path)
        if metadata.get("primary_preset") != preset:
            raise SystemExit(f"metadata preset mismatch for {preset}")
        outputs = normalize_outputs(root)
        label, generation, qa = write_artwork_documents(
            root, entry, by_id[preset], metadata, outputs
        )
        packaged.append(
            {
                "number": entry["number"],
                "preset": preset,
                "label": by_id[preset]["label"],
                "layout": by_id[preset]["layout"],
                "directory": root.relative_to(delivery).as_posix(),
                "outputs": {
                    key: relative_output(delivery, value)
                    for key, value in outputs.items()
                },
                "documents": {
                    "label": label.relative_to(delivery).as_posix(),
                    "generation_record": generation.relative_to(delivery).as_posix(),
                    "qa_record": qa.relative_to(delivery).as_posix(),
                },
            }
        )

    manifest = {
        "schema_version": 2,
        "collection_id": sha256(delivery / "selection.lock.json")[:12].upper(),
        "artwork_count": len(packaged),
        "delivery_path": str(delivery),
        "take_home_path": str(take_home),
        "packaged_at": now(),
        "artworks": packaged,
    }
    manifest_path = take_home / "collection-manifest.json"
    save(manifest_path, manifest)

    receipt_path = take_home / "取件单.md"
    receipt_lines = [
        "# LaplaceLajiang 展览取件单",
        "",
        f"- 收藏编号：`{manifest['collection_id']}`",
        f"- 带走作品：{len(packaged)} 幅",
        f"- 保存位置：`{take_home}`",
        "",
        "## 作品",
        "",
    ]
    for item in packaged:
        receipt_lines.extend(
            [
                f"### #{item['number']:02d} {item['label']}",
                "",
                f"- 高清母版：`{item['outputs']['master']['path']}`",
                f"- 小红书版：`{item['outputs']['xhs_3x4']['path']}`",
                f"- 母版尺寸：{item['outputs']['master']['width']} × {item['outputs']['master']['height']}",
                f"- 展签：`{item['documents']['label']}`",
                f"- 生成记录：`{item['documents']['generation_record']}`",
                f"- 质检记录：`{item['documents']['qa_record']}`",
                "",
            ]
        )
    receipt_path.write_text("\n".join(receipt_lines), encoding="utf-8")

    html_path = take_home / "index.html"
    html_path.write_text(build_receipt_html(manifest), encoding="utf-8")
    zip_path = take_home / "laplacelajiang-collection.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(manifest_path, "collection-manifest.json")
        archive.write(receipt_path, "取件单.md")
        archive.write(html_path, "index.html")
        for item in packaged:
            root = delivery / item["directory"]
            for relative in (
                "final/master.png",
                "final/xhs-3x4.jpg",
                "展签.md",
                "generation-record.json",
                "qa-record.json",
                "metadata.json",
            ):
                source = root / relative
                archive.write(
                    source,
                    f"{item['number']:02d}-{item['preset']}/{relative}",
                )
    return html_path, zip_path


def build_receipt_html(manifest: dict) -> str:
    cards = []
    for item in manifest["artworks"]:
        root = Path(item["directory"]).relative_to("take-home")
        master = (root / "final" / "master.png").as_posix()
        xhs = (root / "final" / "xhs-3x4.jpg").as_posix()
        cards.append(
            f'''<article><div class="frame"><img src="{escape(master)}" alt="#{item['number']:02d} {escape(item['label'])}"></div><div class="label"><span>#{item['number']:02d}</span><h2>{escape(item['label'])}</h2><p>{item['outputs']['master']['width']} × {item['outputs']['master']['height']}</p><a download href="{escape(master)}">下载高清母版</a><a download href="{escape(xhs)}">下载 3:4 版</a></div></article>'''
        )
    return (
        RECEIPT_HTML.replace("__CARDS__", "\n".join(cards))
        .replace("__COLLECTION_ID__", escape(manifest["collection_id"]))
        .replace("__COUNT__", str(manifest["artwork_count"]))
    )


RECEIPT_HTML = '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>展览取件处 · LaplaceLajiang</title><style>:root{color-scheme:dark;font-family:"Segoe UI","PingFang SC",sans-serif;background:#0a0b0a;color:#ebe7dd}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 50% 0,#33281f,#0a0b0a 42rem)}header{min-height:72vh;display:grid;place-content:center;text-align:center;padding:3rem 1rem;border-bottom:1px solid #35332e}header p{letter-spacing:.25em;color:#d99564;text-transform:uppercase}h1{font-family:Georgia,"Songti SC",serif;font-size:clamp(4rem,13vw,11rem);line-height:.75;letter-spacing:-.08em;margin:.4rem}header small{color:#aaa295}main{max-width:1200px;margin:auto;padding:6rem 1.25rem}article{min-height:80vh;display:grid;grid-template-columns:1.4fr .7fr;align-items:center;gap:7vw;border-bottom:1px solid #35332e;padding:5rem 0}.frame{padding:1rem;background:#382216;border:1rem ridge #25140e;box-shadow:0 2rem 5rem #000}.frame img{display:block;width:100%;max-height:70vh;object-fit:contain;background:#111}.label span{color:#d99564}.label h2{font-family:Georgia,"Songti SC",serif;font-size:clamp(2rem,5vw,4.5rem);line-height:.95;letter-spacing:-.04em}.label p{color:#aaa295}.label a{display:inline-block;margin:.5rem .5rem .5rem 0;padding:.8rem 1rem;border:1px solid #ebe7dd;color:inherit;text-decoration:none}.label a:hover{background:#ebe7dd;color:#111}footer{text-align:center;padding:4rem;color:#aaa295}@media(max-width:760px){article{grid-template-columns:1fr;min-height:0}.label{padding-bottom:3rem}}@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important}}</style></head><body><header><p>Collection ready · __COUNT__ artworks</p><h1>取件处</h1><small>收藏编号 __COLLECTION_ID__ · 高清装裱与包装已完成</small></header><main>__CARDS__</main><footer>LaplaceLajiang Photo Card · 请保存整个 take-home 文件夹或下载 ZIP</footer></body></html>'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("delivery", type=Path)
    args = parser.parse_args()
    html_path, zip_path = package(args.delivery)
    status_path = args.delivery.resolve() / "take-home" / "packing-status.json"
    status = load(status_path) if status_path.is_file() else {"schema_version": 2}
    status.update(
        {
            "schema_version": 2,
            "stage": "ready-for-pickup",
            "progress_percent": 100,
            "updated_at": now(),
            "receipt": "take-home/index.html",
            "archive": "take-home/laplacelajiang-collection.zip",
        }
    )
    for item in status.get("items", []):
        item["status"] = "packaged"
    save(status_path, status)
    print(f"PASS: take-home counter -> {html_path}")
    print(f"PASS: collection package -> {zip_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

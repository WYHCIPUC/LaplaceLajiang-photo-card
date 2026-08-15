"""Build the desktop Three.js exhibition and its optimized local assets."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from PIL import Image, ImageOps


BUILD_VERSION = "4.0.0"
SKILL_DIR = Path(__file__).resolve().parents[1]
RUNTIME_SOURCE = SKILL_DIR / "assets" / "exhibition"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def safe_script_json(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False).replace("<", "\\u003c")


def source_image(delivery: Path, session: dict) -> Path:
    sources = session.get("sources") or []
    if not sources:
        raise SystemExit("session does not contain a source image")
    source = delivery / sources[0]["relative_path"]
    if not source.is_file():
        raise SystemExit(f"source image is missing: {source}")
    return source


def optimize_image(
    source: Path,
    target: Path,
    maximum: tuple[int, int],
    quality: int,
) -> tuple[int, int]:
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
        image.thumbnail(maximum, Image.Resampling.LANCZOS)
        width, height = image.size
        image.save(target, "WEBP", quality=quality, method=6)
    return width, height


def copy_runtime(preview_dir: Path) -> Path:
    if not RUNTIME_SOURCE.is_dir():
        raise SystemExit(f"exhibition runtime is missing: {RUNTIME_SOURCE}")
    target = preview_dir / "exhibition"
    target.mkdir(parents=True, exist_ok=True)
    for name in ("vendor", "textures"):
        shutil.copytree(
            RUNTIME_SOURCE / name,
            target / name,
            dirs_exist_ok=True,
        )
    for name in (
        "gallery.css",
        "gallery-runtime.js",
        "THIRD-PARTY-NOTICES.md",
    ):
        shutil.copy2(RUNTIME_SOURCE / name, target / name)
    return target


def style_name(item: dict) -> str:
    label = item.get("label", item["id"])
    return label.split("/")[-1].strip()


def record_recipe(item: dict, guardrails: list[str]) -> tuple[str, str, str]:
    name = style_name(item)
    kernel = item.get("prompt_kernel", "source-grounded editorial treatment")
    output_form = item.get("output_form", "editorial image")
    layout = item.get("layout", "full-bleed")
    summary = (
        f"以母片事实为底稿，用{name}重组材质、留白、层级与观看节奏；"
        "保持主体身份、空间关系和真实光线，不把风格化变成无依据的改景。"
    )
    basic = (
        f"请将图 1 作为唯一内容母片，转换为“{name}”成品。\n"
        f"视觉媒介：{kernel}。\n"
        f"结果形态：{output_form}；版式倾向：{layout}。\n"
        "保留可识别主体、姿态、地形或建筑轮廓、前后景关系、光线方向与"
        "原图取样色；不新增人物、地标、品牌、故事事实或可读文字。"
    )
    advanced = (
        "保真优先：原图主体与空间结构权重 70%，风格材质权重 30%。\n"
        "构图控制：先锁定主视觉轴和负空间，再安排纸张、笔触、裁片、网点"
        "或抽象层；任何装饰都不得遮挡关键主体。\n"
        "细节控制：边缘干净，纹理尺度一致，避免局部过锐、伪文字、重复器官、"
        "错误透视、无依据测量或文化符号。\n"
        "全局边界：" + "；".join(guardrails)
    )
    return summary, basic, advanced


def prepare_records(
    delivery: Path,
    preview_dir: Path,
    records: list[dict],
    catalog: dict,
) -> list[dict]:
    catalog_items = {
        item["id"]: item
        for item in catalog["native_presets"]
        + catalog["reference_result_presets"]
    }
    guardrails = catalog.get("defaults", {}).get("guardrails", [])
    art_dir = preview_dir / "exhibition" / "assets" / "artworks"
    for record in records:
        preset_id = record["id"]
        source = preview_dir / record["image"]
        if not source.is_file():
            raise SystemExit(f"missing preview image: {source}")
        target = art_dir / f"{preset_id}.webp"
        width, height = optimize_image(source, target, (1280, 1280), 88)
        item = catalog_items[preset_id]
        summary, recipe_basic, recipe_advanced = record_recipe(
            item, guardrails
        )
        record.update(
            {
                "image": target.relative_to(preview_dir).as_posix(),
                "width": width,
                "height": height,
                "group_short": "原生预设"
                if item["kind"] == "native"
                else "项目适配",
                "style_summary": summary,
                "recipe_basic": recipe_basic,
                "recipe_advanced": recipe_advanced,
                "source_display": "LaplaceLajiang 原生预设"
                if item["kind"] == "native"
                else "兼容适配器 · 非外部项目原生输出",
                "source_project": item.get("source_project"),
                "adapter": item.get("adapter"),
            }
        )
    return records


def launcher_text(delivery: Path) -> str:
    entry = SKILL_DIR / "scripts" / "photo_card.py"
    return (
        "@echo off\r\n"
        "setlocal\r\n"
        "chcp 65001 >nul\r\n"
        "set PYTHONUTF8=1\r\n"
        f'python "{entry}" serve "{delivery}" --open\r\n'
        "if errorlevel 1 (\r\n"
        "  echo.\r\n"
        "  echo 展厅启动失败，请先运行产品包中的安装并自检。\r\n"
        "  pause\r\n"
        ")\r\n"
        "endlocal\r\n"
    )


def build_spatial(delivery: Path) -> Path:
    delivery = delivery.resolve()
    preview_dir = delivery / "previews"
    manifest_path = preview_dir / "gallery-manifest.json"
    manifest = load_json(manifest_path)
    session = load_json(delivery / "session.json")
    catalog = load_json(delivery / "catalog.snapshot.json")
    records = manifest["items"]

    runtime_dir = copy_runtime(preview_dir)
    records = prepare_records(delivery, preview_dir, records, catalog)
    mother_source = source_image(delivery, session)
    mother_target = runtime_dir / "assets" / "mother-plate.webp"
    mother_width, mother_height = optimize_image(
        mother_source, mother_target, (1800, 1800), 90
    )

    chapters = [
        {"title": "第一章 · 线与纸", "range": [1, 4]},
        {"title": "第二章 · 记忆层", "range": [5, 8]},
        {"title": "第三章 · 观看结构", "range": [9, 12]},
        {"title": "第四章 · 东方气韵", "range": [13, 16]},
        {"title": "第五章 · 叙事切片", "range": [17, 20]},
        {"title": "第六章 · 远意与留白", "range": [21, 24]},
    ]
    data = {
        "schema_version": 4,
        "build_version": BUILD_VERSION,
        "session_id": session.get("created_at", delivery.name),
        "session_stage": session.get("stage"),
        "desktop_only": True,
        "minimum_viewport": [1366, 768],
        "recommended_viewport": [1920, 1080],
        "offline_runtime": True,
        "service_required_for_selection": True,
        "delivery_path": str(delivery),
        "take_home_path": str((delivery / "take-home").resolve()),
        "archive_path": str(preview_dir.resolve()),
        "mother_plate": {
            "path": "exhibition/assets/mother-plate.webp",
            "width": mother_width,
            "height": mother_height,
        },
        "chapters": chapters,
        "items": records,
    }

    shell = (RUNTIME_SOURCE / "gallery-shell.html").read_text(
        encoding="utf-8"
    )
    document = shell.replace("__BUILD_VERSION__", BUILD_VERSION)
    document = document.replace("__GALLERY_DATA__", safe_script_json(data))
    output = preview_dir / "style-gallery.html"
    output.write_text(document, encoding="utf-8")
    save_json(runtime_dir / "gallery-data.json", data)

    launcher = preview_dir / "打开廿四境展厅.cmd"
    launcher.write_text(launcher_text(delivery), encoding="utf-8-sig")

    manifest.update(
        {
            "schema_version": 4,
            "gallery_contract": "threejs-hybrid+css-fallback+local-state-service",
            "build_version": BUILD_VERSION,
            "desktop_only": True,
            "minimum_viewport": [1366, 768],
            "recommended_viewport": [1920, 1080],
            "offline": True,
            "external_runtime_dependencies": [],
            "local_runtime_dependencies": [
                "Three.js 0.185.1",
                "GSAP 3.15.0",
                "ambientCG CC0 PBR textures",
            ],
            "interaction": {
                "desktop_only": True,
                "camera": "fixed frontal curatorial viewpoint",
                "entry": "wooden vestibule, brass handle, door opening and camera dolly",
                "artwork_switch": "stationary-wall light curtain dissolve",
                "artwork_switch_duration_ms": 850,
                "side_next_button": True,
                "free_walk": False,
                "pointer_lock": False,
                "mobile_touch_layout": False,
                "catalogue": "linen hardback with six four-work page-turn spreads",
                "focus_view": "blurred gallery, left curatorial copy, right uncropped artwork",
                "frame_drag_feedback": True,
                "mother_plate_compare": True,
                "lens_zoom_and_pan": True,
                "recipe_room": True,
                "collection_state_service": "localhost JSON API",
                "packing_progress": "real status file only",
                "quality_tiers": ["low", "balanced", "high"],
                "keyboard": [
                    "ArrowRight",
                    "ArrowLeft",
                    "E",
                    "C",
                    "M",
                    "B",
                    "Escape",
                ],
                "reduced_motion": True,
            },
            "spatial": {
                "layout": "frontal-main-bay-with-receding-side-corridors",
                "camera_movement_after_entry": False,
                "artwork_slot_count": 1,
                "artwork_sequence_count": len(records),
            },
            "visual_theme": {
                "id": "twilight-private-collection-salon",
                "tone": "warm, intimate, refined",
                "materials": [
                    "ivory plaster",
                    "white oak floor",
                    "dark mahogany frame",
                    "aged brass",
                    "linen catalogue",
                    "walnut stand",
                ],
                "lighting": "2700K artwork spots with cool twilight fill",
            },
            "primary": "style-gallery.html",
            "launcher": "打开廿四境展厅.cmd",
            "fallback": "style-gallery-accessible.html",
            "items": records,
        }
    )
    save_json(manifest_path, manifest)
    save_json(
        runtime_dir / "gallery-version.json",
        {
            "build_version": BUILD_VERSION,
            "runtime": "Three.js",
            "state_service": "gallery_server.py",
            "items": len(records),
        },
    )
    return output


if __name__ == "__main__":
    raise SystemExit(
        "build_spatial_exhibition.py is called by build_exhibition_gallery.py"
    )

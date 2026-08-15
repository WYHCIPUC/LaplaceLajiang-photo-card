"""Run a deterministic end-to-end smoke test without external image generation."""

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw


def run(*args: object) -> None:
    command = [sys.executable, *[str(value) for value in args]]
    subprocess.run(command, check=True)


def run_fails(*args: object) -> None:
    command = [sys.executable, *[str(value) for value in args]]
    result = subprocess.run(
        command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    if result.returncode == 0:
        raise RuntimeError(f"command unexpectedly passed: {command}")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_fixture(path: Path, colors: tuple[str, str]) -> None:
    image = Image.new("RGB", (720, 960), colors[0])
    draw = ImageDraw.Draw(image)
    draw.rectangle((80, 90, 640, 870), fill=colors[1])
    draw.ellipse((170, 210, 550, 650), fill="#D08B31")
    image.save(path)


def write_oriented_fixture(path: Path) -> None:
    image = Image.new("RGB", (720, 960), "#D9E2CE")
    image.getexif()[274] = 6
    image.save(path, exif=image.getexif())


def main() -> int:
    skill_dir = Path(__file__).resolve().parents[1]
    scripts = skill_dir / "scripts"
    source_catalog = skill_dir / "references" / "integrated-preset-catalog.json"
    with tempfile.TemporaryDirectory(prefix="laplacelajiang-self-test-") as temporary:
        root = Path(temporary)
        catalog = root / "catalog.json"
        shutil.copy2(source_catalog, catalog)
        source = root / "source.png"
        oriented_source = root / "oriented.jpg"
        panel = root / "panel.png"
        delivery = root / "delivery-v01"
        write_fixture(source, ("#D9E2CE", "#53654B"))
        write_oriented_fixture(oriented_source)
        write_fixture(panel, ("#F2E7CF", "#2A3028"))
        run_fails(
            scripts / "manage_session.py",
            "init",
            root / "duplicate-source",
            "--catalog",
            catalog,
            "--source",
            source,
            "--source",
            source,
        )
        run_fails(
            scripts / "manage_session.py",
            "init",
            root / "invalid-ratio",
            "--catalog",
            catalog,
            "--source",
            source,
            "--ratio",
            "3:0",
        )
        orientation_delivery = root / "orientation-v01"
        run(
            scripts / "manage_session.py",
            "init",
            orientation_delivery,
            "--catalog",
            catalog,
            "--source",
            oriented_source,
        )
        orientation_session = json.loads(
            (orientation_delivery / "session.json").read_text(encoding="utf-8")
        )
        orientation_record = orientation_session["sources"][0]
        if (orientation_record["width"], orientation_record["height"]) != (960, 720):
            raise RuntimeError("EXIF-oriented dimensions were not normalized")
        if not orientation_record["exif_orientation_normalized"]:
            raise RuntimeError("EXIF normalization was not recorded")
        version_root = root / "versioned"
        run(
            scripts / "photo_card.py",
            "start",
            "--source",
            source,
            "--output-root",
            root / "quick-entry",
            "--slug",
            "quick-card",
        )
        run(
            scripts / "photo_card.py",
            "status",
            root / "quick-entry" / "quick-card-v01",
        )
        run(
            scripts / "manage_session.py",
            "new",
            version_root,
            "--slug",
            "photo-card",
            "--catalog",
            catalog,
            "--source",
            source,
        )
        run(
            scripts / "manage_session.py",
            "new",
            version_root,
            "--slug",
            "photo-card",
            "--catalog",
            catalog,
            "--source",
            source,
        )
        if (
            not (version_root / "photo-card-v01" / "session.json").is_file()
            or not (version_root / "photo-card-v02" / "session.json").is_file()
        ):
            raise RuntimeError("automatic version allocation failed")
        run(
            scripts / "manage_session.py",
            "init",
            delivery,
            "--catalog",
            catalog,
            "--source",
            source,
        )
        snapshot_catalog = delivery / "catalog.snapshot.json"
        selection_map = json.loads(
            (delivery / "selection-map.json").read_text(encoding="utf-8")
        )
        if [item["number"] for item in selection_map["presets"]] != list(
            range(1, len(selection_map["presets"]) + 1)
        ):
            raise RuntimeError("selection map is not contiguous")
        if sha256(snapshot_catalog) != selection_map["catalog_sha256"]:
            raise RuntimeError("selection map hash does not match snapshot")
        version_snapshot = version_root / "photo-card-v01" / "catalog.snapshot.json"
        if sha256(version_snapshot) != sha256(catalog):
            raise RuntimeError("versioned session did not freeze the catalog")
        original_catalog_bytes = catalog.read_bytes()
        catalog.write_bytes(original_catalog_bytes + b"\n")
        if sha256(version_snapshot) == sha256(catalog):
            raise RuntimeError("catalog snapshot changed with the source catalog")
        catalog.write_bytes(original_catalog_bytes)
        run(scripts / "manage_session.py", "status", delivery, "--list")
        run(scripts / "manage_session.py", "set-stage", delivery, "--stage", "failed")
        run(scripts / "manage_session.py", "resume", delivery)
        (delivery / "analysis.md").write_text(
            "# Evidence\n\n- green ground → muted paper and spatial block\n",
            encoding="utf-8",
        )
        run(
            scripts / "build_prompt_manifest.py",
            "--catalog",
            snapshot_catalog,
            "--evidence",
            delivery / "analysis.md",
            "--output",
            delivery / "prompts" / "thumbnail-prompts.json",
            "--stage",
            "thumbnail",
        )
        catalog_data = json.loads(snapshot_catalog.read_text(encoding="utf-8"))
        items = (
            catalog_data["native_presets"] + catalog_data["reference_result_presets"]
        )
        for index, item in enumerate(items):
            target = delivery / "previews" / f"{item['id']}.png"
            if index == len(items) - 1:
                run(
                    scripts / "manage_session.py",
                    "mark-preview",
                    delivery,
                    "--preset",
                    item["id"],
                    "--status",
                    "failed",
                    "--reason",
                    "self-test failure placeholder",
                )
            else:
                write_fixture(target, (item["theme"]["paper"], item["theme"]["ink"]))
                run(
                    scripts / "manage_session.py",
                    "mark-preview",
                    delivery,
                    "--preset",
                    item["id"],
                    "--status",
                    "complete",
                )
        run(
            scripts / "photo_card.py",
            "gallery",
            delivery,
            "--columns",
            "3",
            "--thumb-width",
            "180",
            "--thumb-height",
            "240",
        )
        gallery_html = delivery / "previews" / "style-gallery.html"
        gallery_accessible = (
            delivery / "previews" / "style-gallery-accessible.html"
        )
        gallery_manifest = delivery / "previews" / "gallery-manifest.json"
        if (
            not gallery_html.is_file()
            or not gallery_accessible.is_file()
            or not gallery_manifest.is_file()
        ):
            raise AssertionError("immersive gallery artifacts were not generated")
        gallery_data = json.loads(gallery_manifest.read_text(encoding="utf-8"))
        if len(gallery_data["items"]) != len(items):
            raise AssertionError("immersive gallery item count is incorrect")
        gallery_document = gallery_html.read_text(encoding="utf-8")
        for marker in (
            'data-gallery-version="4.0"',
            'id="gallery-canvas"',
            'id="enter-gallery"',
            'id="next-artwork"',
            'id="open-catalog"',
            'id="catalogue-book"',
            'id="page-turn"',
            'id="focus-view"',
            'id="focus-frame"',
            'id="compare-source"',
            'id="toggle-lens"',
            'id="open-mirror"',
            'id="mirror-room"',
            'id="open-collection"',
            'id="packing-progress"',
            'id="quality-select"',
            'exhibition/vendor/gsap.min.js',
            'exhibition/gallery-runtime.js',
        ):
            if marker not in gallery_document:
                raise AssertionError(f"spatial gallery marker is missing: {marker}")
        for marker in ('id="lock-button"', 'id="joystick"', "requestPointerLock"):
            if marker in gallery_document:
                raise AssertionError(f"removed gallery control remains: {marker}")
        if gallery_data.get("spatial", {}).get("layout") != (
            "frontal-main-bay-with-receding-side-corridors"
        ):
            raise AssertionError("spatial gallery uses the wrong architectural layout")
        if gallery_data.get("spatial", {}).get("camera_movement_after_entry") is not False:
            raise AssertionError("gallery camera must remain fixed after entry")
        for capability in (
            "side_next_button",
            "frame_drag_feedback",
            "mother_plate_compare",
            "lens_zoom_and_pan",
            "recipe_room",
        ):
            if gallery_data.get("interaction", {}).get(capability) is not True:
                raise AssertionError(f"gallery capability is missing: {capability}")
        if gallery_data.get("interaction", {}).get("free_walk") is not False:
            raise AssertionError("free walk must remain disabled")
        if gallery_data.get("interaction", {}).get("artwork_switch_duration_ms") != 850:
            raise AssertionError("artwork transition duration is not locked")
        for record in gallery_data["items"]:
            for field in ("curatorial_title", "curatorial_description", "style_note"):
                if not record.get(field):
                    raise AssertionError(f"curatorial field is missing: {field}")
        if len(
            list(
                (
                    delivery
                    / "previews"
                    / "exhibition"
                    / "assets"
                    / "artworks"
                ).glob("*.webp")
            )
        ) != len(items):
            raise AssertionError("optimized spatial artwork count is incorrect")
        run(
            scripts / "validate_delivery.py",
            delivery,
            "--catalog",
            snapshot_catalog,
        )
        consumer_pack = root / "consumer-pack"
        run(
            scripts / "build_consumer_prompt_pack.py",
            "--catalog",
            snapshot_catalog,
            "--preview-dir",
            delivery / "previews",
            "--source-image",
            source,
            "--output",
            consumer_pack,
        )
        consumer_page = root / "镜语廿四式-风格配方馆.html"
        run(
            scripts / "build_single_page_prompt_product.py",
            "--source-pack",
            consumer_pack,
            "--output",
            consumer_page,
        )
        page_document = consumer_page.read_text(encoding="utf-8")
        if page_document.count("data:image/jpeg;base64,") != len(items):
            raise AssertionError("single-page product does not embed all samples")
        for marker in ("镜语廿四式", "购买者本人单人使用"):
            if marker not in page_document:
                raise AssertionError(
                    f"single-page product marker is missing: {marker}"
                )
        run_fails(
            scripts / "manage_session.py",
            "select",
            delivery,
            "--preset",
            str(len(items)),
        )
        run_fails(
            scripts / "manage_session.py",
            "select",
            delivery,
            "--preset",
            "1",
            "--blend",
            "17",
        )
        run(
            scripts / "manage_session.py",
            "select",
            delivery,
            "--preset",
            "#17",
            "--preset",
            "5",
            "--blend",
            "6",
        )
        run(
            scripts / "build_prompt_manifest.py",
            "--catalog",
            snapshot_catalog,
            "--evidence",
            delivery / "analysis.md",
            "--output",
            delivery / "prompts" / "final-prompt.json",
            "--stage",
            "final",
            "--selection-lock",
            delivery / "selection.lock.json",
        )
        run(
            scripts / "manage_session.py", "set-stage", delivery, "--stage", "rendering"
        )
        selected_entries = json.loads(
            (delivery / "selection.lock.json").read_text(encoding="utf-8")
        )["items"]
        for entry in selected_entries:
            artwork_root = (
                delivery
                / "take-home"
                / f"{entry['number']:02d}-{entry['preset']}"
            )
            run(
                scripts / "compose_card.py",
                "--photo",
                source,
                "--panel",
                panel,
                "--output-dir",
                artwork_root,
                "--catalog",
                snapshot_catalog,
                "--selection-lock",
                delivery / "selection.lock.json",
                "--preset",
                entry["preset"],
                "--title",
                "FOREST STUDY",
                "--subtitle",
                "树林观察",
                "--microcopy",
                "A deterministic smoke test",
                "--size",
                "1200x1600",
            )
            run(scripts / "validate_card.py", artwork_root)
        (delivery / "materials.md").write_text(
            "# Materials\n\nSynthetic self-test fixtures.\n", encoding="utf-8"
        )
        (delivery / "qa-report.md").write_text(
            "# QA\n\nmanual_visual_review: PASS\n", encoding="utf-8"
        )
        run(scripts / "photo_card.py", "package", delivery)
        run(scripts / "manage_session.py", "set-stage", delivery, "--stage", "complete")
        run(
            scripts / "validate_delivery.py",
            delivery,
            "--catalog",
            snapshot_catalog,
        )
        smoke_root = root / "layout-smoke"
        for item in items:
            target = smoke_root / item["id"]
            target.mkdir(parents=True)
            lock = {
                "schema_version": 2,
                "primary_preset": item["id"],
                "blend_presets": [],
                "selected_at": "self-test",
                "catalog_sha256": sha256(catalog),
            }
            lock_path = target / "selection.lock.json"
            lock_path.write_text(json.dumps(lock), encoding="utf-8")
            run(
                scripts / "compose_card.py",
                "--photo",
                source,
                "--panel",
                panel,
                "--output-dir",
                target,
                "--catalog",
                catalog,
                "--selection-lock",
                lock_path,
                "--title",
                item["id"],
                "--size",
                "300x400",
            )
            run(scripts / "validate_card.py", target)
        print(
            f"PASS: all {len(items)} presets composed through their registered layouts"
        )
        print("PASS: deterministic end-to-end self-test completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

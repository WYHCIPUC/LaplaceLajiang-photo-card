"""Validate preview-stage or final-stage LaplaceLajiang photo-card deliveries."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from PIL import Image


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_image(
    path: Path, errors: list[str], expected: tuple[int, int] | None = None
) -> None:
    if not path.is_file():
        errors.append(f"missing {path.name}")
        return
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            if expected and image.size != expected:
                errors.append(
                    f"wrong size for {path.name}: {image.size}, expected {expected}"
                )
            if image.mode not in {"RGB", "RGBA"}:
                errors.append(f"unsupported mode for {path.name}: {image.mode}")
    except Exception as exc:
        errors.append(f"cannot open {path.name}: {exc}")


def check_immersive_gallery(
    delivery: Path,
    session: dict,
    preset_ids: list[str],
    current_catalog_hash: str,
    errors: list[str],
) -> None:
    contract = session.get("gallery_contract")
    if not contract:
        return
    version = contract.get("version")
    if version not in {1, 2, 3, 4}:
        errors.append("unsupported gallery contract version")
        return
    html_path = delivery / contract.get("primary", "")
    manifest_path = delivery / contract.get("manifest", "")
    if not html_path.is_file():
        errors.append("missing immersive style-gallery.html")
        return
    if not manifest_path.is_file():
        errors.append("missing gallery-manifest.json")
        return
    try:
        document = html_path.read_text(encoding="utf-8")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest_ids = [item["id"] for item in manifest["items"]]
        if manifest_ids != preset_ids:
            errors.append("immersive gallery order does not match catalog")
        if manifest.get("catalog_sha256") != current_catalog_hash:
            errors.append("immersive gallery catalog hash mismatch")
        if manifest.get("external_runtime_dependencies"):
            errors.append("immersive gallery has external runtime dependencies")
        if version == 4:
            required_markers = (
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
                'exhibition/assets/mother-plate.webp',
            )
            forbidden_markers = (
                'id="lock-button"',
                'id="joystick"',
                "requestPointerLock",
                "startMovementLoop",
                ">自由行走<",
                ">无障碍参观<",
            )
            for marker in forbidden_markers:
                if marker in document:
                    errors.append(
                        f"desktop salon retains removed control: {marker}"
                    )
        elif version == 3:
            required_markers = (
                'data-gallery-version="3"',
                'data-experience="first-person-close-view"',
                'id="camera-yaw"',
                'id="camera-pitch"',
                'id="world"',
                'id="next-button"',
                'id="guide-button"',
                "prefers-reduced-motion",
                "WARM_PRIVATE_GALLERY_THEME",
                "AUTO_CLOSE_VIEW_ENTRY",
                "SIDE_NEXT_NAVIGATION",
                "EXHIBIT_LIST_MODE",
                "FIXED_CLOSE_VIEW_CAROUSEL",
                "NO_FREE_WALK_LOOP",
                "SINGLE_LINE_TITLES",
                "WARM_BLURRED_DETAIL_VIEW",
                "DRAGGABLE_FRAME_DEPTH",
                "ARCHITECTURAL_MATERIAL_SYSTEM_V350",
                'id="art-description"',
                'id="art-style"',
                'id="detail-frame"',
                'id="collection-modal"',
                "fitSingleLineTitle",
                "bindFrameDrag",
                "sizeDetailFrame",
                "beginPacking",
                "focusNextArtwork",
                "focusPreviousArtwork",
                "curatorial_description",
                "<noscript>",
            )
            forbidden_markers = (
                'id="lock-button"',
                'id="joystick"',
                "requestPointerLock",
                "startMovementLoop",
                ">自由行走<",
                ">无障碍参观<",
            )
            for marker in forbidden_markers:
                if marker in document:
                    errors.append(f"close-view gallery retains removed control: {marker}")
        elif version == 2:
            required_markers = (
                'data-gallery-version="2"',
                'data-experience="first-person-3d"',
                'id="camera-yaw"',
                'id="camera-pitch"',
                'id="world"',
                "requestPointerLock",
                "pointerlockchange",
                "touch-action:none",
                "prefers-reduced-motion",
                'href="style-gallery-accessible.html"',
                "WARM_PRIVATE_GALLERY_THEME",
                "CLICK_TO_NEXT_ARTWORK",
                "focusNextArtwork",
                "CIRCULAR_GALLERY_STATIONARY_CAMERA",
                "curatorial_description",
                "startMovementLoop",
                "document.hidden",
                "<noscript>",
            )
        else:
            required_markers = (
                'data-gallery-version="1"',
                "prefers-reduced-motion",
                'aria-live="polite"',
                'href="style-gallery.png"',
            )
        for marker in required_markers:
            if marker not in document:
                errors.append(f"immersive gallery lacks required marker: {marker}")
        for preset_id in preset_ids:
            expected_asset = (
                f"exhibition/assets/artworks/{preset_id}.webp"
                if version == 4
                else (
                    f"exhibition-assets/{preset_id}.webp"
                    if version in {2, 3}
                    else f"{preset_id}.png"
                )
            )
            if expected_asset not in document:
                errors.append(f"immersive gallery omits preview: {preset_id}")
        external_assets = re.findall(
            r'(?:src|href)=["\']https?://', document, flags=re.IGNORECASE
        )
        if external_assets:
            errors.append("immersive gallery loads an external runtime asset")
        if version == 4:
            accessible_path = delivery / contract.get("accessible", "")
            if not accessible_path.is_file():
                errors.append("missing accessible exhibition fallback")
            interaction = manifest.get("interaction", {})
            required_capabilities = {
                "desktop_only": True,
                "camera": "fixed frontal curatorial viewpoint",
                "artwork_switch": "stationary-wall light curtain dissolve",
                "artwork_switch_duration_ms": 850,
                "side_next_button": True,
                "free_walk": False,
                "pointer_lock": False,
                "mobile_touch_layout": False,
                "catalogue": "linen hardback with six four-work page-turn spreads",
                "frame_drag_feedback": True,
                "mother_plate_compare": True,
                "lens_zoom_and_pan": True,
                "recipe_room": True,
                "collection_state_service": "localhost JSON API",
                "packing_progress": "real status file only",
                "reduced_motion": True,
            }
            for key, expected in required_capabilities.items():
                if interaction.get(key) != expected:
                    errors.append(f"desktop gallery lacks capability: {key}")
            if interaction.get("quality_tiers") != ["low", "balanced", "high"]:
                errors.append("desktop gallery lacks three quality tiers")
            spatial = manifest.get("spatial", {})
            if spatial.get("layout") != "frontal-main-bay-with-receding-side-corridors":
                errors.append("desktop gallery uses the wrong architectural layout")
            if spatial.get("camera_movement_after_entry") is not False:
                errors.append("desktop gallery moves the camera after entry")
            if spatial.get("artwork_sequence_count") != len(preset_ids):
                errors.append("desktop gallery artwork sequence count mismatch")
            titles = []
            for item in manifest.get("items", []):
                asset = delivery / "previews" / item.get("image", "")
                if not asset.is_file():
                    errors.append(
                        f"missing optimized exhibition asset: {item['id']}"
                    )
                for field in (
                    "curatorial_title",
                    "curatorial_description",
                    "style_note",
                    "style_summary",
                    "recipe_basic",
                    "recipe_advanced",
                ):
                    if not str(item.get(field, "")).strip():
                        errors.append(f"gallery item lacks {field}: {item['id']}")
                if item.get("curatorial_title") == item.get("label"):
                    errors.append(
                        "gallery item uses the preset label as its title: "
                        f"{item['id']}"
                    )
                titles.append(item.get("curatorial_title"))
            if len(set(titles)) != len(titles):
                errors.append("gallery curatorial titles are not unique")
            theme = manifest.get("visual_theme", {})
            if theme.get("id") != "twilight-private-collection-salon":
                errors.append("desktop gallery does not use the twilight salon theme")
            runtime_root = delivery / "previews" / "exhibition"
            for relative in (
                "gallery-runtime.js",
                "gallery.css",
                "vendor/three.module.min.js",
                "vendor/three.core.min.js",
                "vendor/gsap.min.js",
                "textures/floor-color.jpg",
                "textures/floor-normal.jpg",
                "textures/floor-roughness.jpg",
                "textures/mahogany-color.jpg",
                "textures/plaster-color.jpg",
                "textures/linen-color.jpg",
            ):
                if not (runtime_root / relative).is_file():
                    errors.append(f"missing local exhibition runtime asset: {relative}")
            inspirations = manifest.get("design_inspiration", [])
            mengto = next(
                (
                    item
                    for item in inspirations
                    if item.get("name") == "MengTo Skills"
                ),
                {},
            )
            expected_skills = {
                "build-awwwards-quality-sites",
                "threejs",
                "editorial-portfolio-chapters",
                "optimize-web-animations",
            }
            if not expected_skills.issubset(
                set(mengto.get("skills_applied", []))
            ):
                errors.append(
                    "gallery does not register the required MengTo design skills"
                )
        elif version in {2, 3}:
            accessible_path = delivery / contract.get("accessible", "")
            if not accessible_path.is_file():
                errors.append("missing accessible exhibition fallback")
            interaction = manifest.get("interaction", {})
            required_capabilities = (
                {
                    "camera": "stationary perspective close-view after one entrance dolly",
                    "collision": False,
                    "proximity_interaction": False,
                    "pointer_lock": False,
                    "mobile_touch": False,
                    "default_view": "close front-facing artwork and wall label",
                    "click_to_next": False,
                    "side_next_button": True,
                    "auto_dolly_in": True,
                    "exhibit_list": True,
                    "free_walk": False,
                    "front_accessible_link": False,
                    "single_line_titles": True,
                    "blurred_gallery_detail_view": True,
                    "detail_layout": "left curatorial copy and right enlarged artwork",
                    "artwork_drag_feedback": True,
                    "aspect_matched_detail_frame": True,
                    "collection_bag_review": True,
                    "packing_request": True,
                    "guided_camera_translation": False,
                    "guided_camera_rotation": False,
                    "guided_camera_rotation_step_degrees": 0,
                }
                if version == 3
                else {
                    "camera": "perspective scene camera with position and yaw/pitch",
                    "collision": True,
                    "proximity_interaction": True,
                    "pointer_lock": True,
                    "mobile_touch": True,
                    "default_view": "front-facing artwork",
                    "click_to_next": True,
                    "guided_camera_translation": False,
                    "guided_camera_rotation": False,
                    "guided_camera_rotation_step_degrees": 0,
                }
            )
            for key, expected in required_capabilities.items():
                if interaction.get(key) != expected:
                    errors.append(f"spatial gallery lacks capability: {key}")
            positions = manifest.get("spatial", {}).get("artwork_positions", [])
            if len(positions) != len(preset_ids):
                errors.append("spatial gallery artwork position count mismatch")
            spatial = manifest.get("spatial", {})
            if spatial.get("layout") != "ring":
                errors.append("spatial gallery does not use the circular layout")
            if not isinstance(spatial.get("ring_radius"), (int, float)):
                errors.append("spatial gallery lacks a circular radius")
            if not isinstance(spatial.get("wall_segment_count"), int) or spatial.get(
                "wall_segment_count", 0
            ) < 72:
                errors.append("spatial gallery lacks a continuous circular wall")
            if any(not isinstance(position.get("view_yaw"), (int, float)) for position in positions):
                errors.append("spatial gallery lacks front-facing artwork camera angles")
            titles = []
            for item in manifest.get("items", []):
                asset = delivery / "previews" / item.get("exhibition_image", "")
                if not asset.is_file():
                    errors.append(f"missing optimized exhibition asset: {item['id']}")
                for field in ("curatorial_title", "curatorial_description", "style_note"):
                    if not str(item.get(field, "")).strip():
                        errors.append(f"gallery item lacks {field}: {item['id']}")
                if item.get("curatorial_title") == item.get("label"):
                    errors.append(f"gallery item uses the preset label as its title: {item['id']}")
                titles.append(item.get("curatorial_title"))
            if len(set(titles)) != len(titles):
                errors.append("gallery curatorial titles are not unique")
            if manifest.get("visual_theme", {}).get("id") != "warm-private-gallery":
                errors.append("spatial gallery does not use the warm private-gallery theme")
            inspirations = manifest.get("design_inspiration", [])
            mengto = next((item for item in inspirations if item.get("name") == "MengTo Skills"), {})
            expected_skills = {
                "build-awwwards-quality-sites",
                "threejs",
                "editorial-portfolio-chapters",
                "optimize-web-animations",
            }
            if not expected_skills.issubset(set(mengto.get("skills_applied", []))):
                errors.append("gallery does not register the required MengTo design skills")
    except Exception as exc:
        errors.append(f"cannot validate immersive gallery: {exc}")


def check_rendered_artwork(
    root: Path,
    preset: str,
    stage: str,
    current_catalog_hash: str,
    errors: list[str],
) -> None:
    metadata_path = root / "metadata.json"
    if not metadata_path.is_file():
        errors.append(f"missing {metadata_path.relative_to(root.parent.parent)}")
        return
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        required = {
            "skill",
            "schema_version",
            "stage",
            "primary_preset",
            "blend_presets",
            "layout",
            "width",
            "height",
            "ratio",
            "language",
            "title",
            "subtitle",
            "microcopy",
            "source_ids",
            "catalog_sha256",
            "custom_reference",
            "generated_at",
        }
        missing = sorted(required - set(metadata))
        if missing:
            errors.append(f"missing metadata fields for {preset}: {missing}")
            return
        expected = (metadata["width"], metadata["height"])
        check_image(root / "final" / "editorial-card.png", errors, expected)
        check_image(root / "final" / "editorial-card.jpg", errors, expected)
        if metadata.get("catalog_sha256") != current_catalog_hash:
            errors.append(f"metadata catalog hash mismatch for {preset}")
        if metadata.get("primary_preset") != preset:
            errors.append(f"metadata primary_preset mismatch for {preset}")
        if metadata.get("stage") != "rendering":
            errors.append(f"artwork metadata stage must be rendering for {preset}")
    except Exception as exc:
        errors.append(f"cannot read metadata.json for {preset}: {exc}")
    for relative in (
        "layers/photo-primary.png",
        "layers/design-panel.png",
        "layers/text-overlay.png",
    ):
        check_image(root / relative, errors)


def validate(delivery: Path, catalog_path: Path) -> list[str]:
    errors: list[str] = []
    session_path = delivery / "session.json"
    if not session_path.is_file():
        return ["missing session.json"]
    try:
        session = json.loads(session_path.read_text(encoding="utf-8"))
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"cannot read session or catalog JSON: {exc}"]
    items = catalog["native_presets"] + catalog["reference_result_presets"]
    preset_ids = [item["id"] for item in items]
    current_catalog_hash = sha256(catalog_path)
    snapshot_path = delivery / "catalog.snapshot.json"
    map_path = delivery / "selection-map.json"
    if not snapshot_path.is_file():
        errors.append("missing catalog.snapshot.json")
    elif sha256(snapshot_path) != current_catalog_hash:
        errors.append("catalog argument does not match session snapshot")
    if not map_path.is_file():
        errors.append("missing selection-map.json")
    else:
        try:
            selection_map = json.loads(map_path.read_text(encoding="utf-8"))
            mapped_ids = [item["id"] for item in selection_map["presets"]]
            mapped_numbers = [item["number"] for item in selection_map["presets"]]
            if mapped_ids != preset_ids:
                errors.append("selection map order does not match catalog")
            if mapped_numbers != list(range(1, len(items) + 1)):
                errors.append("selection map numbers are not contiguous")
            if selection_map.get("catalog_sha256") != current_catalog_hash:
                errors.append("selection map catalog hash mismatch")
        except Exception as exc:
            errors.append(f"cannot read selection-map.json: {exc}")
    if session.get("catalog_sha256") != current_catalog_hash:
        errors.append("session catalog hash does not match current catalog")
    if set(session.get("preview_status", {})) != set(preset_ids):
        errors.append("preview_status does not match registered preset IDs")
    for source in session.get("sources", []):
        path = delivery / source["relative_path"]
        if not path.is_file():
            errors.append(f"missing source copy: {source['relative_path']}")
        elif sha256(path) != source["sha256"]:
            errors.append(f"source hash changed: {source['relative_path']}")

    preview_dir = delivery / "previews"
    lock = None
    for preset in preset_ids:
        status = session.get("preview_status", {}).get(preset, {}).get("status")
        if status not in {"pending", "complete", "failed"}:
            errors.append(f"invalid preview status for {preset}: {status}")
        if status in {"complete", "failed"}:
            check_image(preview_dir / f"{preset}.png", errors)
    stage = session.get("stage")
    if stage in {"awaiting-selection", "selected", "rendering", "complete"}:
        pending = [
            preset
            for preset, value in session["preview_status"].items()
            if value["status"] == "pending"
        ]
        if pending:
            errors.append(f"resolved stage still has pending previews: {pending}")
        check_image(preview_dir / "style-gallery.png", errors)
        check_immersive_gallery(
            delivery, session, preset_ids, current_catalog_hash, errors
        )
        if not (delivery / "analysis.md").is_file():
            errors.append("missing analysis.md")
    if (
        stage in {"initialized", "previewing", "awaiting-selection", "selected"}
        and (delivery / "final" / "editorial-card.png").exists()
    ):
        errors.append(f"final image exists too early for stage: {stage}")

    if stage in {"selected", "rendering", "complete"}:
        lock_path = delivery / "selection.lock.json"
        if not lock_path.is_file():
            errors.append("missing selection.lock.json")
        else:
            try:
                lock = json.loads(lock_path.read_text(encoding="utf-8"))
                chosen = [lock["primary_preset"], *lock.get("blend_presets", [])]
                unknown = sorted(set(chosen) - set(preset_ids))
                if unknown:
                    errors.append(f"selection contains unknown presets: {unknown}")
                if lock.get("catalog_sha256") != current_catalog_hash:
                    errors.append("selection lock catalog hash mismatch")
                if len(lock.get("blend_presets", [])) > 1:
                    errors.append("selection contains more than one blend preset")
                if lock.get("primary_number") not in range(1, len(items) + 1):
                    errors.append("selection lock has invalid primary_number")
                elif preset_ids[lock["primary_number"] - 1] != lock.get(
                    "primary_preset"
                ):
                    errors.append("selection number does not match primary preset")
                blend_numbers = lock.get("blend_numbers", [])
                blend_presets = lock.get("blend_presets", [])
                if len(blend_numbers) != len(blend_presets):
                    errors.append("selection blend numbers do not match blend presets")
                else:
                    for number, preset in zip(
                        blend_numbers, blend_presets, strict=True
                    ):
                        if number not in range(1, len(items) + 1):
                            errors.append("selection lock has invalid blend number")
                        elif preset_ids[number - 1] != preset:
                            errors.append(
                                "selection blend number does not match blend preset"
                            )
                collection_items = lock.get("items") or []
                if lock.get("schema_version", 2) >= 3:
                    if not 1 <= len(collection_items) <= 6:
                        errors.append("selection collection must contain 1 to 6 items")
                    collection_ids = [item.get("preset") for item in collection_items]
                    collection_numbers = [item.get("number") for item in collection_items]
                    if len(set(collection_ids)) != len(collection_ids):
                        errors.append("selection collection contains duplicates")
                    for preset, number in zip(
                        collection_ids, collection_numbers, strict=True
                    ):
                        if preset not in preset_ids:
                            errors.append(f"selection collection has unknown preset: {preset}")
                        elif number not in range(1, len(items) + 1):
                            errors.append("selection collection has invalid number")
                        elif preset_ids[number - 1] != preset:
                            errors.append("selection collection number mismatch")
                    if collection_ids and collection_ids[0] != lock.get(
                        "primary_preset"
                    ):
                        errors.append("collection first item does not match primary preset")
            except Exception as exc:
                errors.append(f"cannot read selection.lock.json: {exc}")

    collection_entries = []
    if lock:
        collection_entries = lock.get("items") or [
            {
                "preset": lock.get("primary_preset"),
                "number": lock.get("primary_number", 1),
            }
        ]
    if stage in {"rendering", "complete"} and lock and lock.get("schema_version", 2) >= 3:
        for entry in collection_entries:
            artwork_root = (
                delivery
                / "take-home"
                / f"{entry['number']:02d}-{entry['preset']}"
            )
            check_rendered_artwork(
                artwork_root,
                entry["preset"],
                stage,
                current_catalog_hash,
                errors,
            )
    elif stage in {"rendering", "complete"}:
        metadata_path = delivery / "metadata.json"
        if not metadata_path.is_file():
            errors.append("missing metadata.json")
        else:
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                required = {
                    "skill",
                    "schema_version",
                    "stage",
                    "primary_preset",
                    "blend_presets",
                    "layout",
                    "width",
                    "height",
                    "ratio",
                    "language",
                    "title",
                    "subtitle",
                    "microcopy",
                    "source_ids",
                    "catalog_sha256",
                    "custom_reference",
                    "generated_at",
                }
                missing = sorted(required - set(metadata))
                if missing:
                    errors.append(f"missing metadata fields: {missing}")
                else:
                    expected = (metadata["width"], metadata["height"])
                    check_image(
                        delivery / "final" / "editorial-card.png", errors, expected
                    )
                    check_image(
                        delivery / "final" / "editorial-card.jpg", errors, expected
                    )
                if metadata.get("catalog_sha256") != current_catalog_hash:
                    errors.append("metadata catalog hash mismatch")
                if lock and metadata.get("primary_preset") != lock.get(
                    "primary_preset"
                ):
                    errors.append(
                        "metadata primary_preset does not match selection lock"
                    )
                if lock and metadata.get("blend_presets") != lock.get(
                    "blend_presets", []
                ):
                    errors.append("metadata blend_presets do not match selection lock")
                if metadata.get("stage") != stage:
                    errors.append(
                        f"metadata stage does not match session stage: {metadata.get('stage')} != {stage}"
                    )
            except Exception as exc:
                errors.append(f"cannot read metadata.json: {exc}")
        for relative in (
            "layers/photo-primary.png",
            "layers/design-panel.png",
            "layers/text-overlay.png",
        ):
            check_image(delivery / relative, errors)

    if stage == "complete":
        for relative in ("materials.md", "qa-report.md", "prompts/final-prompt.json"):
            if not (delivery / relative).is_file():
                errors.append(f"missing {relative}")
        qa_path = delivery / "qa-report.md"
        if qa_path.is_file() and "manual_visual_review: PASS" not in qa_path.read_text(
            encoding="utf-8"
        ):
            errors.append("qa-report.md lacks manual_visual_review: PASS")
        if lock and lock.get("schema_version", 2) >= 3:
            for relative in (
                "take-home/index.html",
                "take-home/取件单.md",
                "take-home/collection-manifest.json",
                "take-home/laplacelajiang-collection.zip",
            ):
                if not (delivery / relative).is_file():
                    errors.append(f"missing {relative}")
            collection_manifest = delivery / "take-home" / "collection-manifest.json"
            if collection_manifest.is_file():
                try:
                    packaged = json.loads(
                        collection_manifest.read_text(encoding="utf-8")
                    )
                    if packaged.get("schema_version") != 2:
                        errors.append("take-home collection manifest is not schema v2")
                    if packaged.get("artwork_count") != len(collection_entries):
                        errors.append("take-home collection count mismatch")
                    if [item["preset"] for item in packaged.get("artworks", [])] != [
                        item["preset"] for item in collection_entries
                    ]:
                        errors.append("take-home collection order mismatch")
                    for item in packaged.get("artworks", []):
                        root = delivery / item.get("directory", "")
                        for relative in (
                            "final/master.png",
                            "final/xhs-3x4.jpg",
                            "展签.md",
                            "generation-record.json",
                            "qa-record.json",
                        ):
                            if not (root / relative).is_file():
                                errors.append(
                                    "take-home artwork lacks packaged file: "
                                    f"{item.get('preset')} / {relative}"
                                )
                        check_image(root / "final" / "master.png", errors)
                        check_image(
                            root / "final" / "xhs-3x4.jpg",
                            errors,
                            (1800, 2400),
                        )
                except Exception as exc:
                    errors.append(f"cannot read collection manifest: {exc}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("delivery", type=Path)
    parser.add_argument("--catalog", type=Path, required=True)
    args = parser.parse_args()
    errors = validate(args.delivery.resolve(), args.catalog.resolve())
    if errors:
        print("FAIL")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print(
        "PASS: session state, presets, sources, selection gate, images, metadata and QA are valid"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

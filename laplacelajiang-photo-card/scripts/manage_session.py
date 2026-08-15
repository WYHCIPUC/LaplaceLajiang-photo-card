"""Create and advance a recoverable photo-card generation session."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def gallery_contract() -> dict:
    return {
        "version": 4,
        "primary": "previews/style-gallery.html",
        "accessible": "previews/style-gallery-accessible.html",
        "fallback": "previews/style-gallery.png",
        "manifest": "previews/gallery-manifest.json",
        "launcher": "previews/打开廿四境展厅.cmd",
        "runtime": "previews/exhibition/gallery-runtime.js",
    }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def catalog_items(catalog: dict) -> list[dict]:
    return catalog["native_presets"] + catalog["reference_result_presets"]


def session_catalog_path(delivery: Path, session: dict) -> Path:
    catalog_path = Path(session["catalog_path"])
    if not catalog_path.is_absolute():
        catalog_path = delivery / catalog_path
    catalog_path = catalog_path.resolve()
    snapshot = (delivery / "catalog.snapshot.json").resolve()
    selection_map_path = delivery / "selection-map.json"
    if (
        catalog_path == snapshot
        and catalog_path.is_file()
        and selection_map_path.is_file()
    ):
        return catalog_path

    source_value = session.get("catalog_source_path") or session.get("catalog_path")
    source_path = Path(source_value)
    if not source_path.is_absolute():
        source_path = delivery / source_path
    source_path = source_path.resolve()
    if not source_path.is_file():
        raise SystemExit(
            "session catalog is unavailable; restore catalog.snapshot.json or the "
            f"original catalog at {source_path}"
        )
    source_catalog = load_json(source_path)
    source_items = {item["id"]: item for item in catalog_items(source_catalog)}
    session_ids = list(session.get("preview_status", {}))
    missing = sorted(set(session_ids) - set(source_items))
    if missing:
        raise SystemExit(
            f"cannot migrate session; presets missing from catalog: {missing}"
        )
    migrated = dict(source_catalog)
    migrated["native_presets"] = [
        source_items[preset]
        for preset in session_ids
        if source_items[preset]["kind"] == "native"
    ]
    migrated["reference_result_presets"] = [
        source_items[preset]
        for preset in session_ids
        if source_items[preset]["kind"] == "reference-result"
    ]
    save_json(snapshot, migrated)
    catalog_hash = sha256(snapshot)
    save_json(delivery / "selection-map.json", selection_map(migrated, catalog_hash))
    session["original_catalog_sha256"] = session.get("catalog_sha256")
    session["catalog_source_path"] = str(source_path)
    session["catalog_path"] = "catalog.snapshot.json"
    session["catalog_sha256"] = catalog_hash
    session["gallery_contract"] = gallery_contract()
    session["catalog_migrated_at"] = now()
    session["updated_at"] = now()
    save_json(delivery / "session.json", session)
    print(f"PASS: migrated legacy session to {len(session_ids)}-preset snapshot")
    return snapshot.resolve()


def selection_map(catalog: dict, catalog_hash: str) -> dict:
    return {
        "schema_version": 1,
        "catalog_sha256": catalog_hash,
        "presets": [
            {
                "number": index,
                "id": item["id"],
                "label": item["label"],
                "kind": item["kind"],
            }
            for index, item in enumerate(catalog_items(catalog), start=1)
        ],
    }


def resolve_selector(value: str, items: list[dict]) -> tuple[str, int]:
    selector = value.strip().lstrip("#")
    if selector.isdigit():
        number = int(selector)
        if 1 <= number <= len(items):
            return items[number - 1]["id"], number
        raise SystemExit(f"preset number must be between 1 and {len(items)}: {value}")
    folded = selector.casefold()
    for number, item in enumerate(items, start=1):
        aliases = {item["id"].casefold(), item["label"].casefold()}
        aliases.update(part.strip().casefold() for part in item["label"].split("/"))
        if folded in aliases:
            return item["id"], number
    raise SystemExit(
        f"unknown preset selector: {value}; use a gallery number or preset ID"
    )


def placeholder(path: Path, preset: str, reason: str, size: tuple[int, int]) -> None:
    image = Image.new("RGB", size, "#EEEAE1")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    draw.rectangle((20, 20, size[0] - 20, size[1] - 20), outline="#8B342F", width=3)
    draw.text((42, 54), "PREVIEW UNAVAILABLE", fill="#8B342F", font=font)
    draw.text((42, 92), preset, fill="#24231F", font=font)
    words = reason.strip() or "generation failed"
    for index in range(0, min(len(words), 240), 48):
        draw.text(
            (42, 140 + index // 48 * 22),
            words[index : index + 48],
            fill="#5A5750",
            font=font,
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def initialize(args: argparse.Namespace) -> None:
    delivery = args.delivery.resolve()
    if delivery.exists() and any(delivery.iterdir()):
        raise SystemExit(f"delivery already exists and is not empty: {delivery}")
    catalog_path = args.catalog.resolve()
    catalog = load_json(catalog_path)
    sources = [path.resolve() for path in args.source]
    if not sources:
        raise SystemExit("at least one --source is required")
    if len(sources) != len(set(sources)):
        raise SystemExit("duplicate --source paths are not allowed")
    for source in sources:
        if not source.is_file():
            raise SystemExit(f"source does not exist: {source}")
        try:
            with Image.open(source) as image:
                image.verify()
        except Exception as exc:
            raise SystemExit(
                f"source is not a readable image: {source}: {exc}"
            ) from exc
    if not re.fullmatch(r"\d+(?:\.\d+)?:\d+(?:\.\d+)?", args.ratio):
        raise SystemExit("--ratio must use a positive W:H value, for example 3:4")
    rw, rh = (float(value) for value in args.ratio.split(":", 1))
    if rw <= 0 or rh <= 0:
        raise SystemExit("--ratio values must be greater than zero")

    (delivery / "sources").mkdir(parents=True, exist_ok=True)
    (delivery / "previews").mkdir(parents=True, exist_ok=True)
    (delivery / "prompts").mkdir(parents=True, exist_ok=True)
    catalog_snapshot = delivery / "catalog.snapshot.json"
    shutil.copy2(catalog_path, catalog_snapshot)
    catalog_hash = sha256(catalog_snapshot)
    save_json(delivery / "selection-map.json", selection_map(catalog, catalog_hash))
    source_records = []
    for index, source in enumerate(sources):
        label = "primary" if index == 0 else f"secondary-{index:02d}"
        target = delivery / "sources" / f"{label}{source.suffix.lower()}"
        shutil.copy2(source, target)
        with Image.open(target) as image:
            orientation = image.getexif().get(274, 1)
            normalized = ImageOps.exif_transpose(image)
            source_records.append(
                {
                    "id": label,
                    "original_name": source.name,
                    "relative_path": target.relative_to(delivery).as_posix(),
                    "sha256": sha256(target),
                    "width": normalized.width,
                    "height": normalized.height,
                    "mode": normalized.mode,
                    "exif_orientation_normalized": orientation not in {None, 1},
                }
            )

    items = catalog_items(catalog)
    session = {
        "schema_version": 3,
        "skill": catalog["skill"],
        "skill_version": catalog["skill_version"],
        "gallery_contract": gallery_contract(),
        "stage": "initialized",
        "created_at": now(),
        "updated_at": now(),
        "ratio": args.ratio,
        "catalog_path": "catalog.snapshot.json",
        "catalog_source_path": str(catalog_path),
        "catalog_sha256": catalog_hash,
        "sources": source_records,
        "preview_status": {
            item["id"]: {"status": "pending", "reason": ""} for item in items
        },
        "selected": None,
    }
    save_json(delivery / "session.json", session)
    print(f"PASS: initialized {delivery} with {len(items)} presets")


def next_version(root: Path, slug: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    versions = []
    pattern = re.compile(rf"^{re.escape(slug)}-v(\d+)$")
    for candidate in root.iterdir():
        match = pattern.match(candidate.name)
        if candidate.is_dir() and match:
            versions.append(int(match.group(1)))
    return root / f"{slug}-v{max(versions, default=0) + 1:02d}"


def new_versioned(args: argparse.Namespace) -> None:
    args.delivery = next_version(args.root.resolve(), args.slug)
    initialize(args)


def mark_preview(args: argparse.Namespace) -> None:
    delivery = args.delivery.resolve()
    session_path = delivery / "session.json"
    session = load_json(session_path)
    session_catalog_path(delivery, session)
    if session["stage"] not in {"initialized", "previewing", "awaiting-selection"}:
        raise SystemExit(f"cannot update previews in stage: {session['stage']}")
    if args.preset not in session["preview_status"]:
        raise SystemExit(f"unknown preset: {args.preset}")
    preview_path = delivery / "previews" / f"{args.preset}.png"
    if args.status == "complete":
        if not preview_path.is_file():
            raise SystemExit(f"preview image is missing: {preview_path}")
        with Image.open(preview_path) as image:
            image.verify()
    else:
        placeholder(
            preview_path, args.preset, args.reason, tuple(args.placeholder_size)
        )
    session["preview_status"][args.preset] = {
        "status": args.status,
        "reason": args.reason,
    }
    pending = [
        item
        for item in session["preview_status"].values()
        if item["status"] == "pending"
    ]
    session["stage"] = "previewing" if pending else "awaiting-selection"
    session["updated_at"] = now()
    save_json(session_path, session)
    print(f"PASS: {args.preset} -> {args.status}; stage={session['stage']}")


def select(args: argparse.Namespace) -> None:
    delivery = args.delivery.resolve()
    session_path = delivery / "session.json"
    session = load_json(session_path)
    append_mode = bool(getattr(args, "append", False))
    allowed_stages = (
        {"awaiting-selection", "selected", "rendering", "complete"}
        if append_mode
        else {"awaiting-selection"}
    )
    if session["stage"] not in allowed_stages:
        raise SystemExit(
            "all preview entries must be resolved before selection; archived "
            "sessions require --append"
        )
    gallery = delivery / "previews" / "style-gallery.png"
    if not gallery.is_file():
        raise SystemExit("style-gallery.png must exist before selection")
    try:
        with Image.open(gallery) as image:
            image.verify()
    except Exception as exc:
        raise SystemExit(f"style-gallery.png is invalid: {exc}") from exc
    contract = session.get("gallery_contract")
    if contract:
        for field in ("primary", "manifest"):
            path = delivery / contract[field]
            if not path.is_file():
                raise SystemExit(f"{path.name} must exist before selection")
    catalog_path = session_catalog_path(delivery, session)
    catalog = load_json(catalog_path)
    items = catalog_items(catalog)
    selections = [resolve_selector(value, items) for value in args.preset]
    if not selections:
        raise SystemExit("select at least one artwork")
    if len(selections) > 6:
        raise SystemExit("a take-home collection can contain at most 6 artworks")
    primary_ids = [value[0] for value in selections]
    primary_numbers = [value[1] for value in selections]
    if len(set(primary_ids)) != len(primary_ids):
        raise SystemExit("selected artworks must be unique")
    existing_lock_path = delivery / "selection.lock.json"
    existing_lock = (
        load_json(existing_lock_path)
        if append_mode and existing_lock_path.is_file()
        else {}
    )
    existing_items = existing_lock.get("items") or []
    existing_ids = {entry["preset"] for entry in existing_items}
    selections = [entry for entry in selections if entry[0] not in existing_ids]
    if append_mode and not selections:
        print("PASS: selection already exists; no new artwork was queued")
        return
    primary, primary_number = selections[0]
    primary_ids = [value[0] for value in selections]
    primary_numbers = [value[1] for value in selections]
    blends_with_numbers = [resolve_selector(value, items) for value in args.blend]
    blends = [value[0] for value in blends_with_numbers]
    blend_numbers = [value[1] for value in blends_with_numbers]
    known = set(session["preview_status"])
    chosen = [*primary_ids, *blends]
    unknown = sorted(set(chosen) - known)
    if unknown:
        raise SystemExit(f"unknown presets: {unknown}")
    unavailable = sorted(
        preset
        for preset in chosen
        if session["preview_status"][preset]["status"] != "complete"
    )
    if unavailable:
        raise SystemExit(
            f"cannot select presets without completed previews: {unavailable}"
        )
    if len(set(blends)) != len(blends) or set(primary_ids) & set(blends):
        raise SystemExit("selected artworks and blend preset must be unique")
    if len(blends) > 1:
        raise SystemExit("at most one blend preset is allowed")
    by_id = {item["id"]: item for item in catalog_items(catalog)}
    if blends and by_id[blends[0]]["kind"] != "native":
        raise SystemExit("blend preset must be a native visual-language preset")
    new_lock_items = [
        {
            "preset": preset,
            "number": number,
            "blend_presets": blends,
            "blend_numbers": blend_numbers,
        }
        for preset, number in selections
    ]
    lock_items = [*existing_items, *new_lock_items]
    if len(lock_items) > len(items):
        raise SystemExit("selection archive cannot contain more than the catalog")
    selected_at = existing_lock.get("selected_at", now())
    history = list(existing_lock.get("selection_history", []))
    history.append(
        {
            "selected_at": now(),
            "append": bool(existing_items),
            "items": new_lock_items,
        }
    )
    lock = {
        "schema_version": 4,
        "items": lock_items,
        "selected_count": len(lock_items),
        "primary_preset": existing_lock.get("primary_preset", primary),
        "primary_number": existing_lock.get("primary_number", primary_number),
        "blend_presets": existing_lock.get("blend_presets", blends),
        "blend_numbers": existing_lock.get("blend_numbers", blend_numbers),
        "selected_at": selected_at,
        "updated_at": now(),
        "selection_history": history,
        "catalog_sha256": sha256(catalog_path),
    }
    save_json(existing_lock_path, lock)
    take_home = delivery / "take-home"
    packing_path = take_home / "packing-status.json"
    existing_packing = load_json(packing_path) if packing_path.is_file() else {}
    packing_items = list(existing_packing.get("items", []))
    packing_ids = {entry["preset"] for entry in packing_items}
    for entry in new_lock_items:
        root = take_home / f"{entry['number']:02d}-{entry['preset']}"
        root.mkdir(parents=True, exist_ok=True)
        if entry["preset"] not in packing_ids:
            packing_items.append(
                {
                    "number": entry["number"],
                    "preset": entry["preset"],
                    "status": "awaiting-high-resolution-render",
                    "relative_path": root.relative_to(delivery).as_posix(),
                }
            )
    save_json(
        packing_path,
        {
            "schema_version": 2,
            "stage": "selection-confirmed",
            "updated_at": now(),
            "items": packing_items,
        },
    )
    session["selected"] = lock
    session["stage"] = "selected"
    session["updated_at"] = now()
    save_json(session_path, session)
    print(
        "PASS: selected collection batch "
        f"{list(zip(primary_numbers, primary_ids, strict=True))}; "
        f"shared_blend={list(zip(blend_numbers, blends, strict=True))}; "
        f"archive_total={len(lock_items)}"
    )


def show_status(args: argparse.Namespace) -> None:
    delivery = args.delivery.resolve()
    session = load_json(delivery / "session.json")
    catalog = load_json(session_catalog_path(delivery, session))
    items = catalog_items(catalog)
    counts = {"pending": 0, "complete": 0, "failed": 0}
    for value in session["preview_status"].values():
        counts[value["status"]] += 1
    print(f"delivery: {delivery}")
    print(f"stage: {session['stage']}")
    print(
        "previews: "
        f"{counts['complete']} complete, {counts['failed']} failed, "
        f"{counts['pending']} pending"
    )
    if args.list or session["stage"] == "awaiting-selection":
        for number, item in enumerate(items, start=1):
            status = session["preview_status"][item["id"]]["status"]
            print(f"{number:02d}  {status:8}  {item['id']}  |  {item['label']}")
    selected = session.get("selected")
    if selected:
        selected_items = selected.get("items") or [
            {
                "number": selected.get("primary_number", "?"),
                "preset": selected["primary_preset"],
            }
        ]
        print(
            "selected collection: "
            + ", ".join(
                f"#{item['number']} {item['preset']}" for item in selected_items
            )
        )
    packing_path = delivery / "take-home" / "packing-status.json"
    if packing_path.is_file():
        packing = load_json(packing_path)
        print(f"packing: {packing.get('stage', 'unknown')}")
    next_actions = {
        "initialized": "write analysis.md, then build thumbnail prompts",
        "previewing": "finish or fail every pending preview",
        "awaiting-selection": "finish the visit and choose 1 to 6 artworks",
        "selected": "build final prompts and render every selected artwork",
        "rendering": "package the collection, finish materials.md and visual QA",
        "complete": "collection is ready at take-home/index.html",
        "failed": "inspect the failure reason and resume from saved artifacts",
    }
    print(f"next: {next_actions.get(session['stage'], 'inspect session.json')}")


def set_stage(args: argparse.Namespace) -> None:
    delivery = args.delivery.resolve()
    session_path = delivery / "session.json"
    session = load_json(session_path)
    allowed = {"rendering", "complete", "failed"}
    if args.stage not in allowed:
        raise SystemExit(f"unsupported stage: {args.stage}")
    if (
        args.stage in {"rendering", "complete"}
        and not (delivery / "selection.lock.json").is_file()
    ):
        raise SystemExit("selection.lock.json is required")
    transitions = {
        "initialized": {"failed"},
        "previewing": {"failed"},
        "awaiting-selection": {"failed"},
        "selected": {"rendering", "failed"},
        "rendering": {"complete", "failed"},
        "failed": {"failed"},
        "complete": {"complete"},
    }
    if args.stage not in transitions.get(session["stage"], set()):
        raise SystemExit(
            f"invalid stage transition: {session['stage']} -> {args.stage}"
        )
    if args.stage == "failed" and session["stage"] != "failed":
        session["failed_from_stage"] = session["stage"]
    session["stage"] = args.stage
    session["updated_at"] = now()
    save_json(session_path, session)
    metadata_path = delivery / "metadata.json"
    if metadata_path.is_file():
        metadata = load_json(metadata_path)
        metadata["stage"] = args.stage
        save_json(metadata_path, metadata)
    print(f"PASS: stage={args.stage}")


def resume(args: argparse.Namespace) -> None:
    delivery = args.delivery.resolve()
    session_path = delivery / "session.json"
    session = load_json(session_path)
    if session["stage"] != "failed":
        raise SystemExit("resume is only available from the failed stage")
    target = session.get("failed_from_stage")
    if target not in {
        "initialized",
        "previewing",
        "awaiting-selection",
        "selected",
        "rendering",
    }:
        raise SystemExit("session does not contain a resumable failed_from_stage")
    session["stage"] = target
    session["resumed_at"] = now()
    session["updated_at"] = now()
    save_json(session_path, session)
    print(f"PASS: resumed stage={target}")


def migrate(args: argparse.Namespace) -> None:
    delivery = args.delivery.resolve()
    session_path = delivery / "session.json"
    session = load_json(session_path)
    catalog_path = session_catalog_path(delivery, session)
    if session.get("gallery_contract") != gallery_contract():
        session = load_json(session_path)
        session["gallery_contract"] = gallery_contract()
        session["updated_at"] = now()
        save_json(session_path, session)
        print("PASS: upgraded gallery contract to desktop Three.js v4")
    print(f"PASS: session catalog ready at {catalog_path}")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init")
    init.add_argument("delivery", type=Path)
    init.add_argument("--catalog", type=Path, required=True)
    init.add_argument("--source", type=Path, action="append", required=True)
    init.add_argument("--ratio", default="3:4")
    init.set_defaults(func=initialize)

    new = commands.add_parser("new")
    new.add_argument("root", type=Path)
    new.add_argument("--slug", required=True)
    new.add_argument("--catalog", type=Path, required=True)
    new.add_argument("--source", type=Path, action="append", required=True)
    new.add_argument("--ratio", default="3:4")
    new.set_defaults(func=new_versioned)

    mark = commands.add_parser("mark-preview")
    mark.add_argument("delivery", type=Path)
    mark.add_argument("--preset", required=True)
    mark.add_argument("--status", choices=("complete", "failed"), required=True)
    mark.add_argument("--reason", default="")
    mark.add_argument("--placeholder-size", type=int, nargs=2, default=(768, 1024))
    mark.set_defaults(func=mark_preview)

    choose = commands.add_parser("select")
    choose.add_argument("delivery", type=Path)
    choose.add_argument("--preset", action="append", required=True)
    choose.add_argument("--blend", action="append", default=[])
    choose.add_argument(
        "--append",
        action="store_true",
        help="append a new 1–6 artwork batch to an existing exhibition archive",
    )
    choose.set_defaults(func=select)

    stage = commands.add_parser("set-stage")
    stage.add_argument("delivery", type=Path)
    stage.add_argument("--stage", required=True)
    stage.set_defaults(func=set_stage)

    status = commands.add_parser("status")
    status.add_argument("delivery", type=Path)
    status.add_argument("--list", action="store_true")
    status.set_defaults(func=show_status)

    resume_command = commands.add_parser("resume")
    resume_command.add_argument("delivery", type=Path)
    resume_command.set_defaults(func=resume)

    migrate_command = commands.add_parser("migrate")
    migrate_command.add_argument("delivery", type=Path)
    migrate_command.set_defaults(func=migrate)
    return root


if __name__ == "__main__":
    arguments = parser().parse_args()
    arguments.func(arguments)

"""Convenient entry point for LaplaceLajiang photo-card sessions."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_DIR / "scripts"
DEFAULT_CATALOG = SKILL_DIR / "references" / "integrated-preset-catalog.json"


def run(script: str, *values: object) -> int:
    command = [sys.executable, str(SCRIPTS / script)]
    command.extend(str(value) for value in values if value is not None)
    environment = os.environ.copy()
    environment["PYTHONUTF8"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(command, check=False, env=environment).returncode


def configure_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="replace")


def start(args: argparse.Namespace) -> int:
    values: list[object] = [
        "new",
        args.output_root,
        "--slug",
        args.slug,
        "--catalog",
        args.catalog,
        "--ratio",
        args.ratio,
    ]
    for source in args.source:
        values.extend(("--source", source))
    return run("manage_session.py", *values)


def status(args: argparse.Namespace) -> int:
    values: list[object] = ["status", args.delivery]
    if args.list:
        values.append("--list")
    return run("manage_session.py", *values)


def select(args: argparse.Namespace) -> int:
    values: list[object] = ["select", args.delivery]
    for preset in args.preset:
        values.extend(("--preset", preset))
    if args.blend:
        values.extend(("--blend", args.blend))
    if args.append:
        values.append("--append")
    return run("manage_session.py", *values)


def resume(args: argparse.Namespace) -> int:
    return run("manage_session.py", "resume", args.delivery)


def migrate(args: argparse.Namespace) -> int:
    return run("manage_session.py", "migrate", args.delivery)


def gallery(args: argparse.Namespace) -> int:
    delivery = args.delivery.resolve()
    status_code = run("manage_session.py", "migrate", delivery)
    if status_code:
        return status_code
    values: list[object] = [
        "--catalog",
        delivery / "catalog.snapshot.json",
        "--preview-dir",
        delivery / "previews",
        "--output",
        delivery / "previews" / "style-gallery.png",
        "--columns",
        args.columns,
        "--thumb-width",
        args.thumb_width,
        "--thumb-height",
        args.thumb_height,
    ]
    result = run("make_contact_sheet.py", *values)
    if result:
        return result
    return run("build_exhibition_gallery.py", delivery)


def serve(args: argparse.Namespace) -> int:
    values: list[object] = [
        args.delivery,
        "--host",
        args.host,
        "--port",
        args.port,
        "--idle-timeout",
        args.idle_timeout,
    ]
    if args.open:
        values.append("--open")
    return run("gallery_server.py", *values)


def consumer_pack(args: argparse.Namespace) -> int:
    values: list[object] = [
        "--catalog", args.catalog,
        "--preview-dir", args.preview_dir,
        "--source-image", args.source_image,
        "--output", args.output,
    ]
    return run("build_consumer_prompt_pack.py", *values)


def consumer_page(args: argparse.Namespace) -> int:
    return run(
        "build_single_page_prompt_product.py",
        "--source-pack", args.source_pack,
        "--output", args.output,
    )


def package(args: argparse.Namespace) -> int:
    return run("package_collection.py", args.delivery)


def validate(args: argparse.Namespace) -> int:
    catalog = args.catalog
    if catalog is None:
        session_path = args.delivery / "session.json"
        if not session_path.is_file():
            raise SystemExit(f"missing session.json: {session_path}")
        status_code = run("manage_session.py", "status", args.delivery)
        if status_code:
            return status_code
        catalog = args.delivery / "catalog.snapshot.json"
    return run("validate_delivery.py", args.delivery, "--catalog", catalog)


def self_test(_: argparse.Namespace) -> int:
    return run("self_test.py")


def doctor(_: argparse.Namespace) -> int:
    catalog = json.loads(DEFAULT_CATALOG.read_text(encoding="utf-8"))
    print(f"skill: laplacelajiang-photo-card {catalog['skill_version']}")
    print(f"python: {sys.version.split()[0]}")
    missing = [
        dependency
        for dependency in ("PIL",)
        if importlib.util.find_spec(dependency) is None
    ]
    if missing:
        print(f"FAIL: missing Python dependencies: {', '.join(missing)}")
        return 1
    print("PASS: Pillow is available")
    if sys.version_info < (3, 10):
        print("FAIL: Python 3.10 or newer is required")
        return 1
    print("PASS: Python version is supported")
    catalog_result = run("check_preset_catalog.py", SKILL_DIR)
    if catalog_result:
        return catalog_result
    runtime = SKILL_DIR / "assets" / "exhibition"
    required_runtime = [
        runtime / "gallery-shell.html",
        runtime / "gallery.css",
        runtime / "gallery-runtime.js",
        runtime / "vendor" / "three.module.min.js",
        runtime / "vendor" / "three.core.min.js",
        runtime / "vendor" / "gsap.min.js",
        runtime / "textures" / "floor-color.jpg",
        runtime / "textures" / "mahogany-color.jpg",
        runtime / "textures" / "plaster-color.jpg",
        runtime / "textures" / "linen-color.jpg",
    ]
    missing_runtime = [str(path) for path in required_runtime if not path.is_file()]
    if missing_runtime:
        print("FAIL: immersive gallery runtime is incomplete")
        for path in missing_runtime:
            print(f"  missing: {path}")
        return 1
    print("PASS: offline Three.js gallery runtime is complete")
    print("PASS: environment is ready")
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)

    start_command = commands.add_parser("start", help="create a versioned session")
    start_command.add_argument("--source", type=Path, action="append", required=True)
    start_command.add_argument("--output-root", type=Path, required=True)
    start_command.add_argument("--slug", default="photo-card")
    start_command.add_argument("--ratio", default="3:4")
    start_command.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    start_command.set_defaults(func=start)

    status_command = commands.add_parser("status", help="show state and next action")
    status_command.add_argument("delivery", type=Path)
    status_command.add_argument("--list", action="store_true")
    status_command.set_defaults(func=status)

    select_command = commands.add_parser(
        "select", help="select by gallery number, ID or complete label"
    )
    select_command.add_argument("delivery", type=Path)
    select_command.add_argument("preset", nargs="+")
    select_command.add_argument("--blend")
    select_command.add_argument(
        "--append",
        action="store_true",
        help="append a new batch to an existing exhibition archive",
    )
    select_command.set_defaults(func=select)

    resume_command = commands.add_parser("resume", help="resume a failed session")
    resume_command.add_argument("delivery", type=Path)
    resume_command.set_defaults(func=resume)

    migrate_command = commands.add_parser(
        "migrate", help="freeze the catalog for a legacy session"
    )
    migrate_command.add_argument("delivery", type=Path)
    migrate_command.set_defaults(func=migrate)

    gallery_command = commands.add_parser(
        "gallery", help="build immersive HTML and static PNG galleries"
    )
    gallery_command.add_argument("delivery", type=Path)
    gallery_command.add_argument("--columns", type=int, default=3)
    gallery_command.add_argument("--thumb-width", type=int, default=360)
    gallery_command.add_argument("--thumb-height", type=int, default=480)
    gallery_command.set_defaults(func=gallery)

    serve_command = commands.add_parser(
        "serve",
        help="run the localhost exhibition and real workflow-state bridge",
    )
    serve_command.add_argument("delivery", type=Path)
    serve_command.add_argument("--host", default="127.0.0.1")
    serve_command.add_argument("--port", type=int, default=8765)
    serve_command.add_argument("--idle-timeout", type=int, default=300)
    serve_command.add_argument("--open", action="store_true")
    serve_command.set_defaults(func=serve)

    consumer_command = commands.add_parser(
        "consumer-pack",
        help="build a no-Codex 24-style prompt product for consumer AI platforms",
    )
    consumer_command.add_argument("--preview-dir", type=Path, required=True)
    consumer_command.add_argument("--source-image", type=Path, required=True)
    consumer_command.add_argument("--output", type=Path, required=True)
    consumer_command.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    consumer_command.set_defaults(func=consumer_pack)

    page_command = commands.add_parser(
        "consumer-page",
        help="build a self-contained one-file offline prompt product",
    )
    page_command.add_argument("--source-pack", type=Path, required=True)
    page_command.add_argument("--output", type=Path, required=True)
    page_command.set_defaults(func=consumer_page)

    package_command = commands.add_parser(
        "package", help="verify and package the selected take-home collection"
    )
    package_command.add_argument("delivery", type=Path)
    package_command.set_defaults(func=package)

    validate_command = commands.add_parser("validate", help="validate current stage")
    validate_command.add_argument("delivery", type=Path)
    validate_command.add_argument("--catalog", type=Path)
    validate_command.set_defaults(func=validate)

    test_command = commands.add_parser("self-test", help="run deterministic regression")
    test_command.set_defaults(func=self_test)

    doctor_command = commands.add_parser("doctor", help="check runtime readiness")
    doctor_command.set_defaults(func=doctor)
    return root


def main() -> int:
    configure_console()
    args = parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

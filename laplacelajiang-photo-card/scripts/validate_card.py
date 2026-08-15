"""Compatibility validator for an already-composed final card directory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


def validate(delivery: Path) -> list[str]:
    errors: list[str] = []
    metadata_path = delivery / "metadata.json"
    if not metadata_path.is_file():
        return ["missing metadata.json"]
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"cannot read metadata.json: {exc}"]
    required = {
        "primary_preset",
        "layout",
        "width",
        "height",
        "ratio",
        "language",
        "title",
        "subtitle",
        "microcopy",
    }
    missing = sorted(required - set(metadata))
    if missing:
        errors.append(f"missing metadata fields: {missing}")
    expected = (metadata.get("width"), metadata.get("height"))
    for relative in (
        "final/editorial-card.png",
        "final/editorial-card.jpg",
        "layers/photo-primary.png",
        "layers/design-panel.png",
        "layers/text-overlay.png",
    ):
        path = delivery / relative
        if not path.is_file():
            errors.append(f"missing {relative}")
            continue
        try:
            with Image.open(path) as image:
                image.verify()
            if relative.startswith("final/"):
                with Image.open(path) as image:
                    if image.size != expected:
                        errors.append(f"wrong size for {relative}: {image.size}")
        except Exception as exc:
            errors.append(f"cannot open {relative}: {exc}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("delivery", type=Path)
    args = parser.parse_args()
    errors = validate(args.delivery.resolve())
    if errors:
        print("FAIL")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print("PASS: final card, layers, metadata and dimensions are valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

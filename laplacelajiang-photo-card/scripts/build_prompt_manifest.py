"""Build thumbnail or final prompt manifests from the integrated catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def all_items(catalog: dict) -> list[dict]:
    return catalog["native_presets"] + catalog["reference_result_presets"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prompt(
    item: dict, evidence: str, defaults: dict, stage: str, blend: dict | None = None
) -> str:
    stage_rule = (
        "Low-resolution style-direction thumbnail only; simplify local detail and do not create final typography."
        if stage == "thumbnail"
        else "High-resolution selected result; refine materials and edges while preserving source fidelity."
    )
    blend_rule = ""
    if blend:
        theme = blend["theme"]
        blend_rule = (
            f" Use {blend['label']} only for material and palette: paper {theme['paper']}, "
            f"ink {theme['ink']}, accent {theme['accent']}; do not replace the primary result structure."
        )
    guardrails = "; ".join(defaults["guardrails"])
    return (
        f"Use the attached source image and this evidence matrix: {evidence.strip()}\n"
        f"Preset: {item['label']}. Output form: {item['output_form']}. Layout: {item['layout']}. "
        f"Visual direction: {item['prompt_kernel']}.{blend_rule}\n"
        f"Guardrails: {guardrails}. {stage_rule} Do not render precise text; reserve clean typography zones for later composition."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stage", choices=("thumbnail", "final"), required=True)
    parser.add_argument("--selection-lock", type=Path)
    args = parser.parse_args()

    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    if not args.evidence.is_file():
        raise SystemExit(f"evidence file does not exist: {args.evidence}")
    evidence = args.evidence.read_text(encoding="utf-8").strip()
    if not evidence:
        raise SystemExit("evidence file is empty")
    items = all_items(catalog)
    by_id = {item["id"]: item for item in items}
    result: dict = {"schema_version": 2, "stage": args.stage, "prompts": []}
    if args.stage == "thumbnail":
        selected = [(item, None) for item in items]
    else:
        if not args.selection_lock:
            raise SystemExit("--selection-lock is required for final prompts")
        lock = json.loads(args.selection_lock.read_text(encoding="utf-8"))
        if lock.get("catalog_sha256") != sha256(args.catalog):
            raise SystemExit("selection lock does not match the current catalog")
        if lock.get("primary_preset") not in by_id:
            raise SystemExit(f"unknown primary preset: {lock.get('primary_preset')}")
        unknown_blends = sorted(set(lock.get("blend_presets", [])) - set(by_id))
        if unknown_blends:
            raise SystemExit(f"unknown blend presets: {unknown_blends}")
        if len(lock.get("blend_presets", [])) > 1:
            raise SystemExit("at most one blend preset is allowed")
        blend_ids = lock.get("blend_presets", [])
        blend = by_id[blend_ids[0]] if blend_ids else None
        if blend and blend["kind"] != "native":
            raise SystemExit("blend preset must be a native visual-language preset")
        locked_items = lock.get("items") or [
            {
                "preset": lock["primary_preset"],
                "number": lock.get("primary_number", 1),
            }
        ]
        unknown_selected = sorted(
            {entry["preset"] for entry in locked_items} - set(by_id)
        )
        if unknown_selected:
            raise SystemExit(f"unknown selected presets: {unknown_selected}")
        selected = [(by_id[entry["preset"]], blend) for entry in locked_items]
        result["selection"] = lock
    for index, (item, blend) in enumerate(selected):
        number = None
        if args.stage == "final":
            number = locked_items[index].get("number")
        result["prompts"].append(
            {
                "id": item["id"],
                "label": item["label"],
                "number": number,
                "prompt": prompt(
                    item, evidence, catalog["defaults"], args.stage, blend
                ),
            }
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"PASS: wrote {len(result['prompts'])} {args.stage} prompts to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

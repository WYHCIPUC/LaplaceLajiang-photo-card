"""Validate the integrated preset catalog and its Markdown registry."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
LAYOUTS = {"split", "stacked", "board", "full-bleed"}
NATIVE_POLICIES = {"explicit-only", "adapter-only"}


def canonical_source(url: str) -> str:
    """Normalize harmless GitHub URL suffixes before duplicate checks."""
    normalized = url.rstrip("|/")
    if normalized.endswith(".git"):
        normalized = normalized[:-4]
    return normalized


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill_dir", type=Path)
    args = parser.parse_args()
    skill_dir = args.skill_dir.resolve()
    catalog_path = skill_dir / "references" / "integrated-preset-catalog.json"
    registry_path = skill_dir / "references" / "style-presets.md"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    if catalog.get("schema_version") != 2:
        raise SystemExit("catalog schema_version must be 2")
    if not re.fullmatch(r"\d+\.\d+\.\d+", catalog.get("skill_version", "")):
        raise SystemExit("catalog skill_version must use semantic X.Y.Z format")
    groups = (catalog["native_presets"], catalog["reference_result_presets"])
    items = groups[0] + groups[1]
    catalog_ids = [item["id"] for item in items]
    registry_ids = re.findall(
        r"^## `([^`]+)`", registry_path.read_text(encoding="utf-8"), re.MULTILINE
    )
    if len(catalog_ids) != len(set(catalog_ids)):
        raise SystemExit("duplicate preset id in catalog")
    if set(catalog_ids) != set(registry_ids):
        missing = sorted(set(catalog_ids) - set(registry_ids))
        extra = sorted(set(registry_ids) - set(catalog_ids))
        raise SystemExit(f"catalog/registry mismatch; missing={missing}; extra={extra}")

    required = {
        "id",
        "label",
        "kind",
        "layout",
        "theme",
        "output_form",
        "prompt_kernel",
    }
    for item in items:
        missing = sorted(required - set(item))
        if missing:
            raise SystemExit(f"{item.get('id', '<unknown>')} lacks fields: {missing}")
        if not re.fullmatch(r"[a-z0-9-]+", item["id"]):
            raise SystemExit(f"invalid preset id: {item['id']}")
        if item["layout"] not in LAYOUTS:
            raise SystemExit(f"invalid layout for {item['id']}: {item['layout']}")
        if set(item["theme"]) != {"paper", "ink", "accent"}:
            raise SystemExit(f"invalid theme fields for {item['id']}")
        if not all(HEX.fullmatch(value) for value in item["theme"].values()):
            raise SystemExit(f"invalid theme color for {item['id']}")
        if len(item["prompt_kernel"].strip()) < 24:
            raise SystemExit(f"prompt_kernel too short for {item['id']}")
    for item in catalog["native_presets"]:
        if item["kind"] != "native":
            raise SystemExit(f"native preset has wrong kind: {item['id']}")
    source_keys = []
    for item in catalog["reference_result_presets"]:
        reference_required = {
            "source_project",
            "native_skill",
            "adapter",
            "native_policy",
        }
        missing = sorted(reference_required - set(item))
        if missing:
            raise SystemExit(f"reference preset lacks fields: {item['id']} {missing}")
        if not item["source_project"].startswith("https://github.com/"):
            raise SystemExit(f"invalid source_project for {item['id']}")
        canonical = canonical_source(item["source_project"])
        if item["source_project"] != canonical:
            raise SystemExit(
                f"source_project must use canonical URL for {item['id']}: {canonical}"
            )
        source_keys.append(canonical.casefold())
        if item["native_policy"] not in NATIVE_POLICIES:
            raise SystemExit(f"invalid native_policy for {item['id']}")
        if item["native_policy"] == "explicit-only" and not item["native_skill"]:
            raise SystemExit(f"explicit native route lacks native_skill: {item['id']}")
        if item.get("source_status", "").startswith("unverified") and (
            item["native_policy"] != "adapter-only" or item["native_skill"] is not None
        ):
            raise SystemExit(
                f"unverified source must be isolated to adapter-only: {item['id']}"
            )
        if item.get("license_status") == "unverified" and (
            item["native_policy"] != "adapter-only" or item["native_skill"] is not None
        ):
            raise SystemExit(
                f"unverified license must be isolated to adapter-only: {item['id']}"
            )
    if len(source_keys) != len(set(source_keys)):
        raise SystemExit("duplicate reference source_project in catalog")

    defaults = catalog.get("defaults", {})
    if (
        not defaults.get("guardrails")
        or not defaults.get("preview_size")
        or not defaults.get("final_size")
    ):
        raise SystemExit("catalog defaults are incomplete")
    print(f"PASS: {len(items)} presets registered, themed, prompted and routed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

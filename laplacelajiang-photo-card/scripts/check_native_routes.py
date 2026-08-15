"""Report which reference-result presets can use an installed native skill."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--skills-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    routes = []
    for item in catalog["reference_result_presets"]:
        native_skill = item.get("native_skill")
        installed = bool(
            native_skill and (args.skills_dir / native_skill / "SKILL.md").is_file()
        )
        route = (
            "native-available"
            if installed
            and item["native_policy"] == "explicit-only"
            and not item.get("source_status", "").startswith("unverified")
            and item.get("license_status") != "unverified"
            else "adapter"
        )
        routes.append(
            {
                "preset": item["id"],
                "native_skill": native_skill,
                "native_policy": item["native_policy"],
                "installed": installed,
                "source_status": item.get("source_status", "not-recorded"),
                "license_status": item.get("license_status", "not-recorded"),
                "effective_route": route,
            }
        )
    result = {
        "schema_version": 1,
        "skills_dir": str(args.skills_dir.resolve()),
        "routes": routes,
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    native_count = sum(
        route["effective_route"] == "native-available" for route in routes
    )
    print(
        f"PASS: {native_count} native routes available; {len(routes) - native_count} adapter routes"
    )
    for route in routes:
        print(f"- {route['preset']}: {route['effective_route']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

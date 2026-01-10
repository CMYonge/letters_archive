#!/usr/bin/env python3
"""Validate that every entity path recorded in data/entities.yml exists."""

from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
ENTITIES_PATH = ROOT / "data" / "entities.yml"


def main() -> int:
    if not ENTITIES_PATH.exists():
        print(f"[validate_entities] Missing {ENTITIES_PATH.relative_to(ROOT)}", file=sys.stderr)
        return 1

    with open(ENTITIES_PATH, "r", encoding="utf-8") as handle:
        entities = yaml.safe_load(handle) or {}

    missing = []
    root_resolved = ROOT.resolve()

    for entity_id, info in entities.items():
        rel_path = (info or {}).get("path")
        if not rel_path:
            missing.append((entity_id, "path field is empty"))
            continue

        target = (ROOT / rel_path).resolve()
        try:
            target.relative_to(root_resolved)
        except ValueError:
            missing.append((entity_id, f"path escapes repository: {rel_path}"))
            continue

        if not target.exists():
            missing.append((entity_id, f"missing target: {rel_path}"))

    if missing:
        print("[validate_entities] The following issues were found:", file=sys.stderr)
        for entity_id, message in missing:
            print(f"  - {entity_id}: {message}", file=sys.stderr)
        return 1

    print(f"[validate_entities] {len(entities)} entities validated successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

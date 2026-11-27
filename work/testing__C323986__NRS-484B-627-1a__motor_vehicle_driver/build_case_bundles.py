"""Materialize one exact inline construction for every selected case."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def main() -> None:
    plan = json.loads((ROOT / "case-plan.json").read_text(encoding="utf-8"))
    root = json.loads((ROOT / "construction.json").read_text(encoding="utf-8"))
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    for row in plan["cases"]:
        case_id = row["case_id"]
        suffix = case_id.rsplit("__", 1)[-1]
        if suffix == "slow_center_wide":
            continue
        bundle = json.loads(json.dumps(root))
        bundle["case_id"] = case_id
        bundle["recording_description"] = row["recording_description"]
        selected = json.loads(json.dumps(config))
        selected["selected_case_id"] = case_id
        selected["case"] = {"case_id": case_id, "variant": suffix}
        # The selected config is inline and case-local. Shared code retains
        # exact source bindings to the root implementation.
        for entry in bundle["files"]:
            if entry["path"] == "config.json":
                entry.pop("source", None)
                entry["content"] = json.dumps(selected, indent=2) + "\n"
            elif entry.get("source"):
                entry["content"] = (ROOT / entry["path"]).read_text(encoding="utf-8")
        destination = ROOT / "cases" / suffix
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "construction.json").write_text(
            json.dumps(bundle, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

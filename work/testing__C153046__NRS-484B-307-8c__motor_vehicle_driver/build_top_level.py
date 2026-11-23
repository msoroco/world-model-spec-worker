"""Materialize the shared C153046 draft package at assignment root."""
from __future__ import annotations

import json
from pathlib import Path

from build_case_plan import AID, KINDS

ROOT = Path(__file__).resolve().parent
BASELINE = "stopped_leftmost_clear"


def build() -> dict:
    construction = json.loads((ROOT / "constructions" / (BASELINE + ".json")).read_text())
    files = {item["path"]: item["content"] for item in construction["files"]}
    config = json.loads(files["config.json"])
    config["supported_case_ids"] = [AID + "__" + suffix for suffix in KINDS]
    files["config.json"] = json.dumps(config, indent=2) + "\n"
    construction["files"] = [{"path": item["path"], "content": files[item["path"]]}
                              for item in construction["files"]]
    construction["status"] = "partial shared CPU package; original Native source and delivery pending"
    return construction


def main() -> None:
    construction = build()
    files = {item["path"]: item["content"] for item in construction["files"]}
    (ROOT / "config.json").write_text(files["config.json"])
    (ROOT / "measurement-contract.json").write_text(files["measurement-contract.json"])
    (ROOT / "construction.json").write_text(json.dumps(construction, indent=2) + "\n")
    print("shared top-level draft package:", construction["case_id"])


if __name__ == "__main__":
    main()

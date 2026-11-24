"""Bind current pinned compatibility and negative source receipts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SUFFIXES = ("response_siren_pedestrian", "response_lamps_only",
            "response_silent", "pursuit_actual_siren", "pursuit_suspected_siren",
            "unqualified_siren", "unqualified_lamps_only")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        suffix = case_id.removeprefix(HERE.name + "__")
        if suffix not in SUFFIXES:
            raise ValueError("Unexpected exact case")
        version = "v9"
        source = REPO / ".runtime-work" / f"c109035-compat-{suffix}-{version}"
        receipt_source = source / "compatibility.json"
        receipt = json.loads(receipt_source.read_text())
        recipe = REPO / entry["fixture_recipe"]
        if (receipt.get("case_id") != case_id or
                receipt.get("construction_sha256") != entry["construction_sha256"] or
                receipt.get("fixture_recipe_sha256") != sha(recipe) or
                receipt.get("passed") is not True):
            raise ValueError("Stale or incomplete compatibility: " + suffix)
        for name in ("compatibility-analysis.log", "negative-analysis.log"):
            source_log = source / name
            if sha(source_log) != receipt[("negative_" if name.startswith("negative") else "") + "log_sha256"]:
                raise ValueError("Changed compatibility source log: " + suffix)
            target = HERE / f"compat-{suffix}-{name}"
            target.write_bytes(source_log.read_bytes())
            data = target.read_bytes()
            if not data.endswith(b"\n") or data.endswith(b"\n\n") or any(
                    line.rstrip(b" \t\r") != line for line in data.split(b"\n")):
                raise ValueError("Unexpected compatibility log whitespace")
        destination = HERE / f"compat-{suffix}-receipt.json"
        destination.write_text(json.dumps(receipt, indent=2) + "\n")
        entry["compatibility"] = {
            "receipt": destination.name, "sha256": sha(destination),
            "log": f"compat-{suffix}-compatibility-analysis.log"}
        entry["negative"] = {"log": f"compat-{suffix}-negative-analysis.log"}
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print("bound seven current primary compatibility receipts")


if __name__ == "__main__":
    main()

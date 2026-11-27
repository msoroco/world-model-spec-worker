"""Build source-hashed controller tuning alternative for each linked exact case."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "execution-manifest.json"
MARKER = "    built = construct(adapter, site_path, selected[\"case_id\"])"
TUNING = (
    "    # Predeclared engineering fallback: begin the lane-change earlier with a\n"
    "    # longer approach gap. The reviewed Native adapter must support it.\n"
    "    adapter.configure_pass_controller(approach_gap_m=20.0, "
    "lane_change_lead_m=28.0)\n"
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    runner = (HERE / "runner.py").read_text()
    if runner.count(MARKER) != 1:
        raise ValueError("Native controller insertion point changed")
    variant = runner.replace(MARKER, TUNING + MARKER)
    for entry in manifest["cases"]:
        case = entry["case_id"]
        name = case[len(HERE.name) + 2:]
        folder = HERE / "cases" / name / "fallback1"
        folder.mkdir(parents=True, exist_ok=True)
        variant_path = folder / "runner.py"
        variant_path.write_text(variant)
        primary = json.loads((HERE / entry["construction"]).read_text())
        alternate = json.loads(json.dumps(primary))
        alternate["candidate_id"] = "fallback1"
        alternate["engineering_tuning"] = {
            "approach_gap_m": 20.0, "lane_change_lead_m": 28.0,
            "changed_only": "Native lane-change controller approach timing and geometry",
        }
        for file in alternate["files"]:
            if file["path"] == "runner.py":
                file["content"] = variant
                file["source"] = str(variant_path.relative_to(HERE.parents[1]))
        construction_path = folder / "construction.json"
        construction_path.write_text(json.dumps(alternate, indent=2, sort_keys=True) + "\n")
        entry["candidates"] = [{
            "id": "fallback1",
            "construction": str(construction_path.relative_to(HERE)),
            "construction_sha256": sha(construction_path),
            "trigger": {
                "source": "sealed original-trace.jsonl and four-camera review",
                "metric": "relative progress, lane-change clearance and zone coverage",
                "failure_condition": "requested pass lacks order reversal or required lane clearance inside reviewed zone",
            },
            "changed_knobs": ["approach_gap_m: 20.0", "lane_change_lead_m: 28.0"],
        }]
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(len(manifest["cases"]), "exact fallback constructions")


if __name__ == "__main__":
    main()

"""Bind the six saved protocol fixtures to pinned CPU compatibility contracts.

This manifest is diagnostic only; synthetic sources do not establish delivery.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from parking_pose import REQUESTS


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def build():
    plan_path = ROOT / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    branch = plan["selected_branches"][0]
    source = {"path": branch["source"], "sha256": branch["source_sha256"],
              "source_index": branch["source_index"]}
    disposition = {"requirement": branch["requirement"], "source": source,
                   "status": "selected_required",
                   "case_ids": [ROOT.name + "__" + kind for kind in REQUESTS],
                   "evidence_or_gap": "Saved original pose measurements implemented; genuine roadway, activity and Chapter source review remains open."}
    plan["requirement_dispositions"] = [disposition]
    plan["selected_branch"] = branch["branch"]
    write(plan_path, plan)
    cases = []
    for kind in REQUESTS:
        folder = ROOT / "diagnostic" / kind
        prior = json.loads((folder / "diagnostic-manifest.json").read_text())["cases"][0]
        def compatibility_construction(source_name, destination_name):
            construction = json.loads((folder / source_name).read_text())
            construction["files"] = [item for item in construction["files"]
                                     if item["path"] != "reviewed-context.json"
                                     and not item["path"].startswith("reviewed_sources/")]
            construction["source_kind"] = "synthetic_saved_fixture_protocol_only"
            destination = folder / destination_name
            write(destination, construction)
            return destination
        primary = compatibility_construction("construction.json", "construction-compatibility.json")
        fallback = compatibility_construction("construction-fallback1.json", "construction-compatibility-fallback1.json")
        contract = {"format": "worker-measurement-contract",
                    "case_id": prior["case_id"],
                    "requirements": [{"disposition_index": 0,
                                      "requirement": disposition["requirement"],
                                      "source": source, "kind": "measured",
                                      "method": "measure_original",
                                      "output_key": "parking_orientation_heading_measurement",
                                      "value_type": "object",
                                      "inputs": ["reviewed-context.json", "parking-history.jsonl",
                                                 "video_frames.jsonl", "camera-frame-map.jsonl",
                                                 "trace.jsonl"]}],
                    "negative": {"remove": ["parking-history.jsonl"],
                                 "error_contains": "Missing required source: parking-history.jsonl"},
                    "scope": "synthetic saved protocol software check only"}
        contract_path = folder / "measurement-contract.json"
        write(contract_path, contract)
        cases.append({"case_id": prior["case_id"], "kind": "diagnostic_only",
                      "construction": primary.relative_to(ROOT).as_posix(),
                      "construction_sha256": sha(primary),
                      "measurement_procedure": {"entrypoint": "parking_analysis.py"},
                      "measurement_contract": contract_path.relative_to(ROOT).as_posix(),
                      "fixture_recipe": (folder / "saved-fixture-recipe.json").relative_to(REPO).as_posix(),
                      "candidate_risk": prior["candidate_risk"],
                      "candidates": [{**candidate,
                                      "construction": fallback.relative_to(ROOT).as_posix(),
                                      "construction_sha256": sha(fallback)}
                                     for candidate in prior["candidates"]]})
    batch = json.loads((REPO / "batch.json").read_text())
    manifest = {"assignment_id": ROOT.name, "diagnostic_only": True,
                "runtime_manifest_sha256": batch["runtime"]["source_manifest_sha256"],
                "cases": cases}
    destination = ROOT / "cpu-compatibility-manifest.json"
    write(destination, manifest)
    return destination


if __name__ == "__main__":
    print(build())

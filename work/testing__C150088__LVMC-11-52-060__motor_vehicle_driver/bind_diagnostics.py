"""Bind exact projection diagnostic contracts and stage case requests."""

import hashlib
import json
from pathlib import Path

from projection_construction import CASES

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write():
    plan = json.loads((ROOT / "case-plan.json").read_text(encoding="utf-8"))
    manifest_path = ROOT / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source = plan["requirement_dispositions"][0]["source"]
    proposals = []
    for case, entry in zip(CASES, manifest["cases"]):
        assert case.case_id == entry["case_id"]
        base = ROOT if case == CASES[0] else ROOT / "cases" / case.suffix
        config = json.loads((base / "config.json").read_text(encoding="utf-8"))
        proposals.append({"case_id": case.case_id,
                          "target_law_id": "LVMC-11-52-060",
                          "target_type": "boundary_probe",
                          "rationale": "Original complete assembly outline projected perpendicular to the reviewed curb; physical and legal findings deferred.",
                          "variable_assignments": {
                              "requested_projection_m": {"kind": "world_setup", "value": case.projection_m,
                                                         "note": "Engineering construction target; measured original outline governs."},
                              "controlling_part": {"kind": "world_setup", "value": case.controlling_part,
                                                   "note": "Selected assembly part, confirmed from original source."}},
                          "recording_description": config["case"]["recording_description"],
                          "unresolved_judgment_calls": ["At-boundary physical measurement uncertainty remains for local review."]})
        contract = {"format": "worker-measurement-contract", "requirements": [{
            "disposition_index": 0, "requirement": "LVMC-11-52-060", "source": source,
            "output_key": "maximum_perpendicular_projection", "method": "measure_projection",
            "value_type": "object", "kind": "measured",
            "inputs": ["diagnostic-source-note.json", "original-projection-history.jsonl",
                       "video_frames.jsonl", "camera-frame-map.jsonl"]}],
            "negative": {"remove": ["original-projection-history.jsonl"],
                         "error_contains": "Missing required source: original-projection-history.jsonl"}}
        cp = base / "measurement-contract.json"
        cp.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")
        entry["measurement_contract"] = str(cp.relative_to(ROOT))
        entry["fixture_recipe"] = str((ROOT / "diagnostics" / case.suffix / "fixture-recipe.json").relative_to(REPO))
        entry["measurement_procedure"] = {"entrypoint": "analysis.py"}
        risks = {
            "vehicle_below": "A parked body near the curb can hide the curb reference beneath its wheels in overview pixels.",
            "vehicle_equal": "At 4.572 m the curb reference and outer body edge must both remain visible; geometry readback uncertainty cannot decide legal equality.",
            "vehicle_above": "The farthest body corner may leave the overview frame or mask its curb-normal reference.",
            "load_above": "The attached load tip can be occluded by the vehicle body in overview or driver-reference pixels.",
            "trailer_above": "The hitch and farthest trailer corner may be occluded separately, defeating attachment and projection review."}
        entry["candidate_risk"] = {"status": "physical", "reason": risks[case.suffix]}
        entry["candidates"][0]["trigger"] = {
            "source": "900-frame original Native part readback and four-camera pixel audit",
            "metric": "complete controlling-part and curb-line visibility in synchronized original pixels",
            "failure_condition": "primary 15 m curb station hides required body/load/trailer corner, attachment, or curb reference"}
    proposal = {"cell_id": "C150088", "actor": "motor_vehicle_driver", "status": "draft",
                "cases": proposals, "sweep_specs": [], "sweeps_expanded": True}
    out = ROOT / "proposals" / "cases.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(proposal, indent=2) + "\n", encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    write()

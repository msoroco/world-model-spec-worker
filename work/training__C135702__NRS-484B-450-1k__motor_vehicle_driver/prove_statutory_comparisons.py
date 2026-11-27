"""Run controlled synthetic request-axis comparisons for statutory drafts."""
import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT / "native"))
from statutory_comparison import audit

NAMES = ("stop_activity", "stand_activity", "alongside_placement",
         "traffic_conflict", "law_direction", "traffic_device", "excavation_kind")
AXIS = {"stop_activity": "activity_request", "stand_activity": "activity_request",
        "alongside_placement": "placement_request", "traffic_conflict": "exception_request",
        "law_direction": "exception_request", "traffic_device": "exception_request",
        "excavation_kind": "obstruction_kind_request"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def request(name):
    recipe = ROOT / ("selected-recipe-statutory-" + name + ".json")
    plan = json.loads((ROOT / "statutory-branch-draft.json").read_text())
    row = next(item for item in plan["cases"] if item["case_id"].endswith("selected_statutory_" + name))
    construction_name = "excavation-construction.json" if name == "excavation_kind" else "statutory-construction.json"
    cfg = json.loads(next(item["content"] for item in json.loads(
        (ROOT / "cases" / name / construction_name).read_text())["files"]
        if item["path"] == "config.json"))
    if cfg["case_id"] != row["case_id"]:
        raise ValueError("Construction case differs from statutory request")
    for key, value in row["requests"].items():
        if cfg[key] != value:
            raise ValueError("Construction statutory request changed: " + key)
    return {"case_id": row["case_id"], "law_id": cfg["law_id"],
            "cell_id": cfg["cell_id"], "actor": cfg["actor"],
            "road_geometry_sha256": sha(ROOT / "native/geometry.py"),
            "camera_profile": cfg["cameras"], "duration_s": cfg["duration_s"],
            "rate_hz": cfg["rate_hz"], "passing_controller": "fixed-primary-policy",
            **row["requests"], "source_gate_passed": True,
            "source_gate_kind": "synthetic_cpu", "source_gate_sha256": sha(recipe),
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}


def prove(name):
    if name not in NAMES:
        raise ValueError("Unknown statutory comparison")
    left, right = request("baseline"), request(name)
    if name == "excavation_kind":
        left["surface_profile_sha256"] = sha(ROOT / "native/geometry.py")
        right["surface_profile_sha256"] = sha(ROOT / "native/excavation_geometry.py")
    with tempfile.TemporaryDirectory(dir=REPO / ".runtime-work", prefix="c135702-stat-compare-") as temp:
        a, b = Path(temp) / "a.json", Path(temp) / "b.json"
        a.write_text(json.dumps(left) + "\n")
        b.write_text(json.dumps(right) + "\n")
        proof = audit(a, b, AXIS[name])
        changed = dict(right, duration_s=29)
        b.write_text(json.dumps(changed) + "\n")
        try:
            audit(a, b, AXIS[name])
        except ValueError as error:
            if "Fixed comparison condition changed" not in str(error):
                raise
        else:
            raise AssertionError("Changed duration accepted")
        changed = dict(right, source_gate_sha256=None)
        b.write_text(json.dumps(changed) + "\n")
        try:
            audit(a, b, AXIS[name])
        except ValueError as error:
            if "source gate missing" not in str(error):
                raise
        else:
            raise AssertionError("Missing source gate accepted")
    proof["negative_fixed_condition_rejected"] = True
    proof["negative_missing_source_rejected"] = True
    target = ROOT / "cases" / name / "proofs" / "request-comparison.json"
    target.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"case_ids": proof["case_ids"], "axis": AXIS[name],
                      "synthetic_only": True, "negative_tests_passed": 2}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", choices=NAMES, required=True)
    args = parser.parse_args()
    prove(args.name)

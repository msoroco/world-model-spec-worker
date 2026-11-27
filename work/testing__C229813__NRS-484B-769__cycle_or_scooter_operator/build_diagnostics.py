"""Generate nine signal-specific text fixtures; never original physical proof."""

import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path(__file__).resolve().parent
ASSIGNMENT = PACKAGE.name
PLAN = json.loads((PACKAGE / "case-plan.json").read_text())
BASE = json.loads((ROOT / "runtime/fixtures/example.json").read_text())


def text(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"


def sha_bytes(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")


def build_case(case):
    case_id = case["case_id"]
    suffix = case_id[len(ASSIGNMENT) + 2:]
    kind = case["operator_vehicle_kind"]
    posture = suffix[len(kind) + 1:]
    spec = copy.deepcopy(BASE)
    files = spec["files"]
    for name in ("alley_context.json", "body_history.jsonl", "speed_samples.jsonl"):
        files.pop(name, None)
    old_rows = [json.loads(line) for line in files["trace.jsonl"].splitlines()]
    positions = [row["position_m"] for row in old_rows]
    manifest = json.loads(files["capture/manifest.json"])
    manifest.update(status="draft", acquisition="synthetic_fixture", case_id=case_id,
                    source_run="c229813-signal-software-fixture",
                    required_observations=[], speed_source="synthetic diagnostic trace only")
    manifest["sources"]["trace.jsonl"] = sha_bytes(files["trace.jsonl"])
    files["capture/manifest.json"] = text(manifest)
    road_sha = sha_bytes(files["road.xodr"])
    context = {
        "case_id": case_id, "map_sha256": road_sha,
        "operator_vehicle_kind": kind,
        "operator_identity_source": "diagnostic rider identity only",
        "roadway_status": "roadway", "highway_status_source": "diagnostic highway only",
        "roadway_polygon": [[95, -5], [110, -5], [110, 5], [95, 5]],
        "shoulder_polygon": [[95, -8], [110, -8], [110, -5], [95, -5]],
        "roadway_geometry_source": "diagnostic polygon only",
        "shoulder_geometry_source": "diagnostic polygon only",
        "right_turn_route": {"waypoint_source": "diagnostic clockwise path only",
                             "first_heading": [1, 0], "last_heading": [0, -1]},
        "requested_signal_posture": posture}
    files["signal-context.json"] = text(context)
    signal_rows = []
    for index, row in enumerate(old_rows):
        x, y, _ = positions[index]
        heading = [1, 0]
        right = [heading[1], -heading[0]]
        def point(lateral, forward, height):
            return [x + right[0] * lateral + heading[0] * forward,
                    y + right[1] * lateral + heading[1] * forward, height]
        elbow = point(.3, 0, 1.5 if posture != "downward_right_arm" else 1.25)
        if posture == "horizontal_right_arm":
            wrist = point(.6, 0, 1.5)
        elif posture == "downward_right_arm":
            wrist = point(.6, 0, .9)
        else:
            wrist = point(.38, .3, 1.5)
        signal_rows.append({"frame": row["frame"], "time_s": row["time_s"],
                            "operator_vehicle_contact_point": [x, y],
                            "operator_heading": heading,
                            "right_arm": {"shoulder": point(0, 0, 1.5),
                                          "elbow": elbow, "wrist": wrist}})
    files["signal-readback.jsonl"] = "".join(text(row) for row in signal_rows)
    receipt = {"assignment_id": ASSIGNMENT, "case_id": case_id,
               "context_sha256": sha_bytes(files["signal-context.json"]),
               "trace_sha256": sha_bytes(files["signal-readback.jsonl"]),
               "frame_count": 9, "fps": 20, "diagnostic_fixture": True}
    files["signal-receipt.json"] = text(receipt)
    files["diagnostic-source-note.json"] = text({
        "scope": "software_fixture_only", "case_id": case_id,
        "physical_acceptance_claimed": False,
        "law_compliance_claimed": False,
        "source": "authored cycle/right-arm probe over generic source-shaped converter fixture"})
    files["fixture-provenance.json"] = text({
        "scope": "CPU diagnostic cycle/right-arm source shape only, never physical evidence",
        "diagnostic_fixture": True, "frames": 9, "case_id": case_id})
    spec_path = PACKAGE / "diagnostics" / (suffix + "-generator.json")
    write(spec_path, spec)
    relative = str(spec_path.relative_to(ROOT))
    digest = hashlib.sha256(spec_path.read_bytes()).hexdigest()
    recipe = {"format": "worker-fixture-recipe",
              "sources": [{"path": "diagnostic-input.json", "source": relative,
                           "sha256": digest}],
              "generator": {"source": relative, "sha256": digest}}
    recipe_path = PACKAGE / "diagnostics" / (suffix + "-recipe.json")
    write(recipe_path, recipe)
    contract = {
        "format": "worker-measurement-contract", "case_id": case_id,
        "requirements": [{"disposition_index": 0,
                          "requirement": "NRS-484B-769",
                          "source": "inputs/testing__C229813__NRS-484B-769__cycle_or_scooter_operator/assignment.json",
                          "output_key": "right_arm_roadway_turn", "method": "measure_case",
                          "value_type": "object", "kind": "measured",
                          "inputs": ["signal-context.json", "signal-readback.jsonl",
                                     "signal-receipt.json"]}],
        "negative": {"remove": ["signal-readback.jsonl"],
                     "error_contains": "Missing required source: signal-readback.jsonl"}}
    contract_path = PACKAGE / "diagnostics" / (suffix + "-measurement-contract.json")
    write(contract_path, contract)
    return suffix, recipe_path, contract_path


def main():
    manifest_path = PACKAGE / "execution-manifest.draft.json"
    manifest = json.loads(manifest_path.read_text())
    for case, entry in zip(PLAN["cases"], manifest["cases"]):
        suffix, recipe, contract = build_case(case)
        entry["fixture_recipe"] = str(recipe.relative_to(ROOT))
        entry["measurement_contract"] = str(contract.relative_to(PACKAGE))
    write(manifest_path, manifest)
    print(json.dumps({"diagnostic_cases": len(manifest["cases"])}))


if __name__ == "__main__":
    main()

"""Build one stopped drive-to exact bundle from the proved traveling source form."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name + "__stopped_drive_to_500ft"
DEST = HERE / "cases/stopped_drive_to_500ft"


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(",", ":") if path.name == "diagnostic.json"
                               else None, indent=None if path.name == "diagnostic.json"
                               else 2) + "\n")


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def replace_one(value, before, after):
    if value.count(before) != 1:
        raise ValueError("Expected exactly one selected source location: " + before)
    return value.replace(before, after)


def construction():
    result = deepcopy(json.loads((HERE / "construction.json").read_text()))
    result["case_id"] = CASE
    files = {item["path"]: item for item in result["files"]}
    runner = files["runner.py"]["content"]
    runner = runner.replace("traveling 500 ft", "stopped drive-to 500 ft")
    runner = runner.replace("__traveling_follow_500ft", "__stopped_drive_to_500ft")
    runner = replace_one(runner, 'config.get("fire_branch") != "traveling_follow"',
                         'config.get("fire_branch") != "stopped_drive_to"')
    runner = replace_one(runner, "from follow_controller import control_step",
                         "from stopped_controller import approach_step")
    runner = replace_one(runner,
                         'route = select_intersection_route(world.get_map(), target_gap_ft=500)',
                         'route = select_intersection_route(world.get_map(), target_gap_ft=520)')
    runner = replace_one(runner,
                         '_cruise_apparatus(world.get_map(), apparatus, carla)',
                         'apparatus.apply_control(carla.VehicleControl(hand_brake=True))')
    runner = replace_one(runner,
                         'control_step(ego, apparatus, target_gap_ft=500,\n'
                         '                         steer=_ego_steer(route["chain"], ego), carla_module=carla)',
                         'approach_step(ego, apparatus, target_distance_ft=500,\n'
                         '                          steer=_ego_steer(route["chain"], ego), carla_module=carla)')
    files["runner.py"]["content"] = runner
    files["stopped_controller.py"] = {"path": "stopped_controller.py",
                                      "content": (HERE / "stopped_controller.py").read_text()}
    config = json.loads(files["config.json"]["content"])
    config["selected_case_id"] = CASE
    config["supported_case_ids"] = [CASE]
    config["fire_branch"] = "stopped_drive_to"
    config["case"]["case_id"] = CASE
    files["config.json"]["content"] = json.dumps(config, indent=2) + "\n"
    test = files["tests/test_runner.py"]["content"]
    test = test.replace("traveling_follow_500ft", "stopped_drive_to_500ft")
    test = test.replace("traveling 500 ft", "stopped drive-to 500 ft")
    test = test.replace('"fire_branch": "traveling_follow"',
                        '"fire_branch": "stopped_drive_to"')
    files["tests/test_runner.py"]["content"] = test
    result["files"] = list(files.values())
    put(DEST / "construction.json", result)


def diagnostic():
    spec = deepcopy(json.loads((HERE / "diagnostic-input.json").read_text()))
    files = spec["files"]
    feet = 3.280839895013123
    shift = 5 - 1 / feet
    footprints = [json.loads(line) for line in files["participant_footprints.jsonl"].splitlines()]
    for index, row in enumerate(footprints):
        for corner in row["ego_corners"]:
            corner[0] += -index + .15 * index
        for corner in row["apparatus_corners"]:
            corner[0] += -index - shift
    files["participant_footprints.jsonl"] = "".join(
        json.dumps(row, separators=(",", ":")) + "\n" for row in footprints)
    states = [json.loads(line) for line in files["participant_state.jsonl"].splitlines()]
    for row in states:
        row.update(apparatus_moving=False, ego_moving=True,
                   ego_following=False, ego_parked=False)
    files["participant_state.jsonl"] = "".join(
        json.dumps(row, separators=(",", ":")) + "\n" for row in states)
    manifest = json.loads(files["capture/manifest.json"])
    manifest["case_id"] = CASE
    files["capture/manifest.json"] = json.dumps(manifest, indent=2) + "\n"
    provenance = json.loads(files["fixture-provenance.json"])
    provenance["case_id"] = CASE
    files["fixture-provenance.json"] = json.dumps(provenance, indent=2) + "\n"
    put(DEST / "diagnostic.json", spec)
    relative = (DEST / "diagnostic.json").relative_to(ROOT).as_posix()
    put(DEST / "diagnostic-recipe.json", {
        "format": "worker-fixture-recipe",
        "sources": [{"path": "diagnostic.json", "source": relative,
                     "sha256": digest(DEST / "diagnostic.json")}],
        "generator": {"source": relative, "sha256": digest(DEST / "diagnostic.json")}})


def main():
    construction()
    diagnostic()
    contract = deepcopy(json.loads((HERE / "first-measurement-contract.json").read_text()))
    contract["case_id"] = CASE
    contract["requirements"][0]["disposition_index"] = 1
    contract["requirements"][0]["requirement"] = "drive to apparatus stopped in answer to a fire alarm"
    put(DEST / "measurement-contract.json", contract)
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    entry = {"case_id": CASE, "kind": "delivery",
             "construction": "cases/stopped_drive_to_500ft/construction.json",
             "construction_sha256": digest(DEST / "construction.json"),
             "measurement_contract": "cases/stopped_drive_to_500ft/measurement-contract.json",
             "measurement_procedure": {"entrypoint": "fire_finalizer.py"},
             "fixture_recipe": (DEST / "diagnostic-recipe.json").relative_to(ROOT).as_posix(),
             "native_handoff": deepcopy(manifest["cases"][0]["native_handoff"]),
             "candidate_risk": {"status": "physical", "reason":
                                "Native approach may stop short or cross the intended centre-distance boundary"},
             "candidates": [], "acquisition": deepcopy(manifest["cases"][0]["acquisition"])}
    manifest["cases"] = [row for row in manifest["cases"] if row["case_id"] != CASE] + [entry]
    put(manifest_path, manifest)
    plan_path = HERE / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    plan["cases"] = [row for row in plan["cases"] if row["case_id"] != CASE]
    plan["cases"].append({"case_id": CASE, "target_law_id": "NRS-484B-710",
                          "branch": "stopped_drive_to", "target_distance_ft": 500,
                          "gap_ids": ["stopped-drive-to"],
                          "construction_status": "exact_bundle_pending_proofs",
                          "physical_risk": {"risk": "Controller may not stop at the target centre distance",
                                            "trigger_source": "original participant footprint and state streams",
                                            "trigger_metric": "active-frame centre distance and closing motion",
                                            "failure_condition": "No active frame reaches the engineering target"}})
    plan["requirement_dispositions"][1]["status"] = "selected_required"
    plan["requirement_dispositions"][1]["case_ids"] = [CASE]
    plan["requirement_dispositions"][1]["evidence_or_gap"] = (
        "No accepted recording; stopped drive-to primary has an exact software bundle. "
        "Other boundary probes remain pending.")
    put(plan_path, plan)
    proposal_path = HERE / "proposals/cases.json"
    proposal = json.loads(proposal_path.read_text())
    proposal["cases"] = [row for row in proposal["cases"] if row["case_id"] != CASE]
    row = deepcopy(proposal["cases"][0])
    row["case_id"] = CASE
    row["rationale"] = ("Measure drive-to closing toward fire apparatus stopped in answer "
                        "to an alarm at the 500 ft engineering command; preserve legal uncertainty")
    row["variable_assignments"]["target_distance_ft"]["value"] = 500
    row["paired_probe_id"] = "stopped_drive_to_500_boundary"
    proposal["cases"].append(row)
    put(proposal_path, proposal)


if __name__ == "__main__":
    main()

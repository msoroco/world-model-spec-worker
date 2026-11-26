"""Add an exact available-lane, closing-vehicle safety-context probe."""

import hashlib
import json
from pathlib import Path
import shutil


HERE = Path(__file__).resolve().parent
SUFFIX = "exception_unsafe_available"
CASE = HERE.name + "__" + SUFFIX
BASE = "exception_1_2"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main():
    plan_path = HERE / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    if CASE not in {c["case_id"] for c in plan["cases"]}:
        case = next(c for c in plan["cases"] if c["case_id"].endswith("__exception_1_1"))
        case = json.loads(json.dumps(case))
        case.update(case_id=CASE,
                    physical_target="Driver passes rider while immediate-left lane is nominally open but an original closing left-lane vehicle raises a separate reasonable-safety context for review",
                    comparison_variable="closing_left_vehicle_context",
                    source_branch="moving into the available immediate-left lane would not be reasonably safe",
                    delivery_readiness="selected_cpu_draft_incomplete")
        case["controller"]["requested_behavior"] = "hold right lane; measure closing left-lane vehicle separately from lane availability"
        plan["cases"].append(case)
        plan["comparisons"].append({
            "comparison_id": HERE.name + "__unsafe_available_comparison",
            "case_ids": [HERE.name + "__exception_1_1", CASE],
            "deliberate_differences": ["closing_left_vehicle_context"],
            "fixed_conditions": ["same original two-lane road and bicycle pass target",
                                 "same ego and cyclist longitudinal and lateral controller targets",
                                 "same cameras and duration; left-lane approaching vehicle differs"],
        })
        plan["requirement_dispositions"][1]["case_ids"].append(CASE)
        plan["blockers"] = ["Reasonable-safety context is newly planned but unjudged; original Native closing-vehicle motion and independent comparison still require proof."]
        plan["runtime_uncertainties"] = ["Original Native actor, lane and closing-vehicle motion are unobserved.",
                                         "Reasonably safe movement and due care require source-grounded independent judgment; engineering gap is not a legal threshold."]
        write(plan_path, plan)
    primary = json.loads((HERE / "selected-native-draft" / BASE / "construction.json").read_text())
    primary["case_id"] = CASE
    config_file = next(f for f in primary["files"] if f["path"] == "config.json")
    config = json.loads(config_file["content"])
    config["case_id"] = config["selected_case_id"] = config["case"]["case_id"] = CASE
    config["case_suffix"] = SUFFIX
    config["supported_case_ids"] = list(dict.fromkeys(config["supported_case_ids"] + [CASE]))
    config_file["content"] = json.dumps(config, indent=2) + "\n"
    scene = next(f for f in primary["files"] if f["path"] == "scene.py")
    source = scene["content"]
    source = source.replace('    "exception_1_2": (False, True),',
                            '    "exception_1_2": (False, True),\n    "exception_unsafe_available": (False, True),')
    source = source.replace('    blocker_x = ego_x + 2 if block_left else None',
                            '    blocker_x = (ego_x - 25 + 3 * t) if case_suffix == "exception_unsafe_available" else (ego_x + 2 if block_left else None)')
    if source == scene["content"] or 'exception_unsafe_available' not in source:
        raise ValueError("Fifth-case scene source insertion failed")
    scene["content"] = source
    runner = next(f for f in primary["files"] if f["path"] == "runner.py")
    source = runner["content"]
    needle = 'blocker.set_target_velocity(carla.Vector3D(x=3, y=0, z=0))'
    if needle not in source:
        raise ValueError("Fifth-case blocker velocity insertion failed")
    runner["content"] = source.replace(needle,
        'blocker.set_target_velocity(carla.Vector3D(x=6 if case_suffix == "exception_unsafe_available" else 3, y=0, z=0))')
    tests = next(f for f in primary["files"] if f["path"] == "tests/test_scene.py")
    tests["content"] = (tests["content"].replace('self.assertEqual(len(proof["case_suffixes"]), 4)',
                                                 'self.assertEqual(len(proof["case_suffixes"]), 5)')
                       .replace('suffix == "exception_1_2"',
                                'suffix in ("exception_1_2", "exception_unsafe_available")'))
    primary["mechanisms"] = list(primary["mechanisms"]) + [
        "closing left-lane original vehicle approaches from behind at planned 6 m/s while ego target is 3 m/s"]
    primary["status"] = "unsafe_available_cpu_draft_original_unobserved"
    target = HERE / "selected-native-draft" / SUFFIX / "construction.json"
    write(target, primary)
    contract = json.loads((HERE / (BASE + "-measurement-contract.json")).read_text())
    contract["case_id"] = CASE
    write(HERE / (SUFFIX + "-measurement-contract.json"), contract)
    source_root = HERE / "diagnostic" / SUFFIX / "sources"
    base_root = HERE / "diagnostic" / BASE / "sources"
    source_root.mkdir(parents=True, exist_ok=True)
    poses = []
    for i, line in enumerate((base_root / "participant-poses.jsonl").read_text().splitlines()):
        row = json.loads(line)
        blocker = row["left_blocker"]
        blocker["center_xy_m"][0] = row["ego"]["center_xy_m"][0] - 25 + 3 * (i / 20)
        blocker["speed_mps"] = 6
        poses.append(json.dumps(row, separators=(",", ":")))
    (source_root / "participant-poses.jsonl").write_text("\n".join(poses) + "\n")
    context = json.loads((base_root / "pass-context.json").read_text())
    context.update(case_id=CASE, left_lane_nominally_open_at_start=True,
                   closing_left_vehicle_requires_safety_review=True,
                   reasonable_safety_judged=False)
    write(source_root / "pass-context.json", context)
    capture = json.loads((base_root / "capture/manifest.json").read_text())
    capture["sources"]["participant-poses.jsonl"] = sha(source_root / "participant-poses.jsonl")
    capture["sources"]["pass-context.json"] = sha(source_root / "pass-context.json")
    write(source_root / "capture/manifest.json", capture)
    recipe = json.loads((HERE / "diagnostic" / BASE / "fixture-recipe.json").read_text())
    for item in recipe["sources"]:
        if item["path"] in ("participant-poses.jsonl", "pass-context.json", "capture/manifest.json"):
            path = source_root / item["path"]
            item["source"] = "work/" + HERE.name + "/diagnostic/" + SUFFIX + "/sources/" + item["path"]
            item["sha256"] = sha(path)
    write(HERE / "diagnostic" / SUFFIX / "fixture-recipe.json", recipe)
    entry = {
        "case_id": CASE, "kind": "delivery",
        "construction": str(target.relative_to(HERE)),
        "construction_sha256": sha(target),
        "measurement_contract": SUFFIX + "-measurement-contract.json",
        "measurement_procedure": {"entrypoint": "finalize.py"},
        "fixture_recipe": "work/" + HERE.name + "/diagnostic/" + SUFFIX + "/fixture-recipe.json",
        "native_handoff": {"python_env_var": "CARLA_PYTHON", "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"},
        "candidate_risk": {"status": "physical", "reason": "Original closing-vehicle trajectory, passing motion and four-view context require readback"},
        "candidates": [], "delivery_readiness": "incomplete",
    }
    for manifest_path in (HERE / "selected-native-draft-manifest.json", HERE / "execution-manifest.json"):
        manifest = json.loads(manifest_path.read_text())
        if CASE not in {e["case_id"] for e in manifest["cases"]}:
            manifest["cases"].append(entry)
        write(manifest_path, manifest)
    print(json.dumps({"case_id": CASE, "construction_sha256": sha(target)}, sort_keys=True))


if __name__ == "__main__":
    main()

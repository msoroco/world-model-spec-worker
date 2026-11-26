"""CPU-only proof of 14 source-surveyed construction contracts and seven pairs."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ASSIGNMENT = ROOT.name
BRANCHES = ("road", "transit_stop", "boarding", "school_zone", "school_crossing",
            "marked_crosswalk", "unmarked_crosswalk")


def load_runner(path):
    spec = importlib.util.spec_from_file_location("exact_branch_runner", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def synthetic_survey(branch, keys):
    survey = {"source_kind": "original_native_context_survey",
              "map_name": "synthetic-map-contract-only", "vehicle_spawn_index": 1,
              "pedestrian_spawn_xyz_m": [11.0, 2.0, 0.0],
              "pedestrian_classification_source": "synthetic-classification-contract",
              "control_relationship_source": "synthetic-driver-contract"}
    survey.update({key: "synthetic-source-contract" for key in keys})
    if branch in ("transit_stop", "school_zone", "school_crossing"):
        survey.update({"context_prop_blueprint": "static.prop.synthetic",
                       "context_prop_xyz_m": [11.0, 3.0, 0.0]})
    if branch == "boarding":
        survey.update({"transit_vehicle_blueprint": "vehicle.synthetic.bus",
                       "transit_vehicle_xyz_m": [12.0, 3.0, 0.0],
                       "boarding_waypoints_xyz_m": [[10.0, 3.0, 0.0], [12.0, 3.0, 0.0]]})
    if branch in ("boarding", "marked_crosswalk", "unmarked_crosswalk"):
        survey["pedestrian_path_xyz_m"] = [[11.0, 2.0, 0.0], [11.0, -2.0, 0.0]]
    if branch in ("marked_crosswalk", "unmarked_crosswalk"):
        survey["crossing_polygon_xyz_m"] = [[9.0, -3.0, 0.0], [13.0, -3.0, 0.0],
                                             [13.0, 3.0, 0.0], [9.0, 3.0, 0.0]]
    if branch == "marked_crosswalk":
        survey["marked_crossing_visible_source"] = "synthetic-marking-contract"
    return survey


def reject(function, phrase):
    try:
        function()
    except ValueError as exc:
        assert phrase in str(exc), (phrase, str(exc))
        return str(exc)
    raise AssertionError("Expected rejection: " + phrase)


class FakeLibrary:
    def find(self, name):
        return name


class FakeWorld:
    def __init__(self):
        self.spawned = []

    def get_blueprint_library(self):
        return FakeLibrary()

    def try_spawn_actor(self, blueprint, transform):
        actor = type("FakeActor", (), {"id": 100 + len(self.spawned)})()
        self.spawned.append((blueprint, transform, actor))
        return actor


class FakeCarla:
    @staticmethod
    def Location(**coordinates):
        return coordinates

    @staticmethod
    def Transform(location):
        return location


def main():
    manifest = json.loads((ROOT / "draft-all-branches-manifest.json").read_text())
    entries = {entry["case_id"]: entry for entry in manifest["cases"]}
    plan = json.loads((ROOT / "case-plan.json").read_text())
    positives, negatives, comparisons = {}, {}, {}
    for branch in BRANCHES:
        members = []
        configs = []
        for mode in ("caution", "maintain"):
            suffix = f"probe_{1 if mode == 'caution' else 2}" if branch == "road" else f"{branch}_{mode}"
            cid = f"{ASSIGNMENT}__{suffix}"
            entry = entries[cid]
            path = HERE / "branch-cases" / suffix
            runner = load_runner(path / "runner.py")
            config = json.loads((path / "config.json").read_text())
            assert runner.check(config)["case_id"] == cid
            assert runner.control(10, 8)["phase"] == ("slow_request" if mode == "caution" else "approach_request")
            survey = synthetic_survey(branch, runner.CONTEXT_KEYS[branch])
            temp = Path(__import__("os").environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) / "surveys" / f"{suffix}.json"
            temp.parent.mkdir(parents=True, exist_ok=True)
            temp.write_text(json.dumps(survey) + "\n")
            assert runner.read_survey(temp) == survey
            world = FakeWorld()
            actors = [type("Ego", (), {"id": 1})(), type("Ped", (), {"id": 2})()]
            context_ids = runner.spawn_context(world, FakeCarla, survey, actors)
            expected_context = 1 if branch in ("transit_stop", "boarding", "school_zone", "school_crossing") else 0
            assert len(world.spawned) == len(context_ids) == expected_context
            if branch in ("transit_stop", "school_zone", "school_crossing"):
                assert world.spawned[0][0] == survey["context_prop_blueprint"]
            if branch == "boarding":
                assert world.spawned[0][0] == survey["transit_vehicle_blueprint"]
            bad = copy.deepcopy(survey)
            key = runner.CONTEXT_KEYS[branch][0]
            bad.pop(key)
            temp.write_text(json.dumps(bad) + "\n")
            negatives[suffix] = reject(lambda: runner.read_survey(temp), "Missing original " + key)
            bad_config = copy.deepcopy(config)
            bad_config["driver_observation_not_inferred_from_visibility"] = False
            reject(lambda: runner.check(bad_config), "Actual observation policy changed")
            if branch in ("boarding", "marked_crosswalk", "unmarked_crosswalk"):
                assert runner.pedestrian_target(survey, 160) == survey["pedestrian_path_xyz_m"][0]
                assert runner.pedestrian_target(survey, 280) == survey["pedestrian_path_xyz_m"][-1]
            positives[suffix] = {"case_id": cid,
                                 "construction_sha256": entry["construction_sha256"],
                                 "software_contract_only": True}
            members.append(cid)
            configs.append(config)
        fixed_keys = set(configs[0]) - {"case_id", "selected_case_id", "mode", "controller"}
        assert all(configs[0][key] == configs[1][key] for key in fixed_keys)
        assert configs[0]["controller"] != configs[1]["controller"]
        comparison = next(item for item in plan["comparisons"] if item["source_branch"] ==
                          next(case["source_branch"] for case in plan["cases"] if case["case_id"] == members[0]))
        assert comparison["case_ids"] == members
        comparisons[branch] = comparison["comparison_id"]
    proof = {"format": "worker-nrs280-branch-construction-cpu-proof-v1",
             "positive": positives, "negative_rejections": negatives,
             "comparison_isolation": comparisons,
             "positive_count": len(positives), "negative_count": len(negatives),
             "comparison_count": len(comparisons),
             "physical_execution_proven": False, "legal_verdict": None}
    path = HERE / "branch-construction-proof.json"
    data = json.dumps(proof, indent=2) + "\n"
    path.write_text(data)
    print(json.dumps({"positive": len(positives), "negative": len(negatives),
                      "comparisons": len(comparisons),
                      "sha256": hashlib.sha256(data.encode()).hexdigest()}))


if __name__ == "__main__":
    main()

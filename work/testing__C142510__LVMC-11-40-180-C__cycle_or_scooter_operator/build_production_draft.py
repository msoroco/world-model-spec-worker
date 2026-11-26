"""Materialize source-gated root construction without changing diagnostic proofs."""

import json
import hashlib
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
SIZES = ((1920, 1080), (1280, 720), (1280, 720), (1280, 720))


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    plan_path = HERE / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    cases = plan["cases"]
    first = cases[0]["case_id"]
    diagnostic = json.loads((HERE / ("construction-compatibility-" +
                                    first.removeprefix(AID + "__") + ".json")).read_text())
    inline_config = json.loads(next(item["content"] for item in diagnostic["files"]
                                    if item["path"] == "config.json"))
    config = {"assignment_id": AID, "law_id": plan["law_id"],
              "cell_id": plan["cell_id"], "actor": plan["actor"],
              "selected_case_id": first,
              "supported_case_ids": [case["case_id"] for case in cases],
              "rate_hz": 20, "duration_s": 45, "frame_count": 900,
              "required_atoms": [], "source_packets": [],
              "source_gate": "reviewed_original_connected_sidewalk_required",
              "rider_start_offset_m": 0,
              "cameras": [{"name": name, "width": width, "height": height,
                           "fov_deg": 90,
                           "pose_strategy": "reviewed original sidewalk and rider/pedestrian body readback"}
                          for name, (width, height) in zip(VIEWS, SIZES)],
              "case": {"case_id": first,
                       "rider_kind": inline_config["case"]["rider_kind"],
                       "signal_frame": inline_config["case"]["signal_frame"],
                       "rider_response": inline_config["case"]["rider_response"]}}
    plan["source_observation_mapping"] = {}
    plan["camera_plan"] = {
        "profile": "overview1080-capability", "duration_s": 45,
        "composition": "synchronized_four_view_primary",
        "coverage": [{"view": name,
                      "subject": "rider, pedestrian, connected sidewalk and passing interval",
                      "interval": "all 900 original frames"} for name in VIEWS]}
    production_description = {"channels": [
        {"name": "sidewalk_body_history", "unit": "m",
         "method": "original rider and pedestrian full-body polygon and 20 Hz frame join",
         "sampling_rate_hz": 20, "time_window": "all 900 original frames",
         "reference_frame": "original Native frame/time",
         "uncertainty": "physical and legal yielding review remains open"},
        {"name": "pedestrian_audio", "unit": "PCM16 waveform",
         "method": "original emitter-event history joined to pedestrian microphone waveform",
         "sampling_rate_hz": 20, "time_window": "all 900 original frames",
         "reference_frame": "original Native frame/time and microphone clock",
         "uncertainty": "engineering detection is not human audibility"},
        {"name": "rider_response", "unit": "m/s and brake state",
         "method": "original rider velocity and brake readback",
         "sampling_rate_hz": 20, "time_window": "all 900 original frames",
         "reference_frame": "original Native frame/time",
         "uncertainty": "right-of-way yielding remains legal review"},
        {"name": "camera_frame_identity", "unit": "original frame ID",
         "method": "four synchronized camera frame identities",
         "sampling_rate_hz": 20, "time_window": "all 900 original frames",
         "reference_frame": "original Native frame/time",
         "uncertainty": "actual pixels require local review"}],
        "context_inputs": [],
        "limitations": ["Physical original sidewalk, audio and legal outcome require local review."]}
    plan["observations"] = [{"name": item["name"], "mandatory": True}
                            for item in production_description["channels"]]
    config["case"]["recording_description"] = production_description
    dump(HERE / "config.json", config)
    dump(plan_path, plan)
    files = []
    for name, materialized in (("runner.py", "runner.py"),
                               ("config.json", "config.json"),
                               ("native_overtake.py", "native_overtake.py"),
                               ("reviewed_sidewalk.py", "reviewed_sidewalk.py"),
                               ("sidewalk_overtake.py", "sidewalk_overtake.py"),
                               ("production_analysis.py", "production_analysis.py"),
                               ("diagnostic_analysis.py", "diagnostic_analysis.py"),
                               ("selected_analysis.py", "analysis.py")):
        path = HERE / name
        files.append({"path": materialized, "content": path.read_text(),
                      "source": str(path.relative_to(ROOT))})
    construction = {"law_id": plan["law_id"], "cell_id": plan["cell_id"],
                    "actor": plan["actor"], "case_id": first,
                    "entrypoint": "runner.py", "diagnostic_fixture": False,
                    "files": files,
                    "measurement_plan": {"procedure": "analysis.py",
                                         "source": "reviewed original 900-frame rider/pedestrian/audio history"},
                    "recording_description": production_description,
                    "static_checks": ["exact identity", "reviewed original sidewalk source hashes",
                                      "four camera and microphone frame counts"],
                    "termination_rules": {"duration_s": 45,
                                          "missing_original_source": "reject without accepted attempt"},
                    "mechanisms": ["reviewed original sidewalk route and actor readback",
                                   "physical audible emitter and pedestrian microphone readback",
                                   "four synchronized original cameras"]}
    dump(HERE / "construction.json", construction)
    draft_entries = []
    for case in cases:
        case_id = case["case_id"]
        name = case_id.removeprefix(AID + "__")
        old = json.loads((HERE / ("construction-compatibility-" + name + ".json")).read_text())
        old_config = json.loads(next(item["content"] for item in old["files"]
                                     if item["path"] == "config.json"))
        scene_content = next(item["content"] for item in old["files"]
                             if item["path"] == "scene.json")
        scene_path = HERE / "diagnostics" / (name + "-production-scene.json")
        scene_path.write_text(scene_content)
        recipe_path = HERE / "diagnostics" / (name + "-production-recipe.json")
        recipe = json.loads((HERE / "diagnostics" / (name + "-recipe.json")).read_text())
        recipe["sources"] = [item for item in recipe["sources"]
                             if item["path"] != "diagnostic/scene.json"]
        recipe["sources"].append({"path": "diagnostic/scene.json",
                                  "source": str(scene_path.relative_to(ROOT)),
                                  "sha256": sha(scene_path)})
        dump(recipe_path, recipe)
        exact = json.loads(json.dumps(construction))
        exact["case_id"] = case_id
        exact_config = json.loads(json.dumps(config))
        exact_config["selected_case_id"] = case_id
        exact_config["case"] = {"case_id": case_id,
                                "rider_kind": old_config["case"]["rider_kind"],
                                "signal_frame": old_config["case"]["signal_frame"],
                                "rider_response": old_config["case"]["rider_response"],
                                "recording_description": production_description}
        for entry in exact["files"]:
            if entry["path"] == "config.json":
                entry.pop("source", None)
                entry["content"] = json.dumps(exact_config, indent=2,
                                               ensure_ascii=False) + "\n"
        exact["files"].append({"path": "tests/test_bundle.py", "content":
            "import json\nfrom pathlib import Path\nimport unittest\n\n"
            "class TestExactBundle(unittest.TestCase):\n"
            "    def test_source_gate_and_identity(self):\n"
            "        root = Path(__file__).resolve().parents[1]\n"
            "        config = json.loads((root / 'config.json').read_text())\n"
            "        self.assertEqual(config['selected_case_id'], " + repr(case_id) + ")\n"
            "        self.assertEqual(config['source_gate'], 'reviewed_original_connected_sidewalk_required')\n"
            "        self.assertEqual(len(config['cameras']), 4)\n"})
        path = HERE / ("construction-production-" + name + ".json")
        dump(path, exact)
        requirement = plan["requirement_dispositions"][0]
        contract_path = HERE / "diagnostics" / (name + "-production-measurement-contract.json")
        dump(contract_path, {"format": "worker-measurement-contract",
                             "case_id": case_id,
                             "requirements": [{"disposition_index": 0,
                                               "requirement": requirement["requirement"],
                                               "source": requirement["source"],
                                               "output_key": "sidewalk_overtake_signal",
                                               "method": "measure_case", "value_type": "object",
                                               "kind": "measured",
                                               "inputs": ["overtake-rows.json",
                                                          "diagnostic-source-note.json"]}],
                             "negative": {"remove": ["overtake-rows.json"],
                                          "error_contains": "Missing required source: overtake-rows.json"}})
        fallback = json.loads(json.dumps(exact))
        fallback_config = json.loads(json.dumps(exact_config))
        fallback_config["rider_start_offset_m"] = 1
        for entry in fallback["files"]:
            if entry["path"] == "config.json":
                entry["content"] = json.dumps(fallback_config, indent=2,
                                               ensure_ascii=False) + "\n"
        fallback_path = HERE / ("construction-production-fallback1-" + name + ".json")
        dump(fallback_path, fallback)
        draft_entries.append({"case_id": case_id, "kind": "delivery",
                              "construction": path.name,
                              "construction_sha256": sha(path),
                              "measurement_contract": str(contract_path.relative_to(HERE)),
                              "measurement_procedure": {"entrypoint": "analysis.py"},
                              "fixture_recipe": str(recipe_path.relative_to(ROOT)),
                              "candidate_risk": {
                                  "status": "physical",
                                  "reason": "Rider spawn clearance or approach pass can fail on the reviewed sidewalk."},
                              "candidates": [{"id": "fallback1",
                                              "construction": fallback_path.name,
                                              "construction_sha256": sha(fallback_path),
                                              "trigger": {
                                                  "source": "original rider spawn and 900-frame body history",
                                                  "metric": "spawn clearance and behind-to-ahead pass",
                                                  "failure_condition": "primary spawn obstructed or stable approach pass absent"},
                                              "changed_knobs": ["reviewed rider route start moved one meter upstream; same route readback required"]}]})
    dump(HERE / "execution-manifest.production-draft.json", {
        "format": "worker-execution-manifest", "assignment_id": AID,
        "status": "production_source_gated_unselected",
        "runtime_manifest_sha256": sha(ROOT / "runtime/SOURCE-MANIFEST.json"),
        "cases": draft_entries})


if __name__ == "__main__":
    main()

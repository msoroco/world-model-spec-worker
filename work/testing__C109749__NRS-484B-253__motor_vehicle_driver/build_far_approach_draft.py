"""Build an isolated far-approach construction for the hazard judgment sweep.

The draft is outside the canonical manifest until saved-source and comparison
proofs establish a controlled exact case. It never starts CARLA.
"""
import hashlib
import json
from pathlib import Path


FOLDER = Path(__file__).resolve().parent
TARGET = FOLDER / "cases" / "approaching_far"
BASE = "testing__C109749__NRS-484B-253__motor_vehicle_driver__approaching_yield"
CASE = "testing__C109749__NRS-484B-253__motor_vehicle_driver__approaching_far"


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source = json.loads((FOLDER / "cases/approaching_yield/construction.json").read_text())
    files = {row["path"]: row["content"] for row in source["files"]}
    config = json.loads(files["config.json"])
    assert config["selected_case_id"] == BASE
    config["selected_case_id"] = CASE
    config["supported_case_ids"] = [CASE]
    config["hazard_sweep_role"] = "far_approach_control_probe"
    config["hazard_legal_threshold"] = None
    runner = files["runner.py"]
    assert "from controller import LeftTurnController" in runner
    runner = runner.replace("from controller import LeftTurnController",
                            "from hazard_sweep_policy import HazardSweepPolicy")
    assert "controller = LeftTurnController(" in runner
    runner = runner.replace("controller = LeftTurnController(",
                            "controller = HazardSweepPolicy(")
    assert runner.count(BASE) == 1
    runner = runner.replace(BASE, CASE)
    files["runner.py"] = runner
    files["config.json"] = json.dumps(config, indent=2, ensure_ascii=False) + "\n"
    files["hazard_sweep_policy.py"] = (FOLDER / "hazard_sweep_policy.py").read_text()
    files["far_approach_observation.py"] = (FOLDER / "far_approach_observation.py").read_text()
    finalizer = files["finalizer.py"]
    finalizer = finalizer.replace(
        "from approaching_yield_observation import observe as observe_approaching_yield",
        "from far_approach_observation import observe as observe_far_approach")
    start = finalizer.index("def measure_approaching_yield(")
    end = finalizer.index("\ndef finalize(", start)
    finalizer = finalizer[:start] + (
        "def measure_far_approach(observation):\n"
        "    return {'ego_turn_start_frame': observation['ego_turn_start_frame'],\n"
        "            'opposing_entry_frame': observation['opposing_entry_frame'],\n"
        "            'turn_sample': observation['turn_sample'],\n"
        "            'engineering_release_ttc_s': observation['engineering_release_ttc_s'],\n"
        "            'legal_verdict_asserted': False}\n\n") + finalizer[end:]
    finalizer = finalizer.replace(BASE, CASE)
    finalizer = finalizer.replace("observe_approaching_yield(attempt)", "observe_far_approach(attempt)")
    start = finalizer.index("      'measured_values':{")
    end = finalizer.index("      'setup_confirmed':", start)
    finalizer = finalizer[:start] + (
        "      'measured_values':{'ego_turn_start_frame':approaching['ego_turn_start_frame'],\n"
        "                         'opposing_entry_frame':approaching['opposing_entry_frame'],\n"
        "                         'turn_sample':approaching['turn_sample']},\n"
        "      'target_checks':[{'target':'far_approach_turn_before_opposing_entry',\n"
        "                        'requested':True,'measured':True,\n"
        "                        'method':'original body overlap, closing motion, heading, indicator and frame joins',\n"
        "                        'tolerance':0,'matched':True,'physical_cause_confirmed':False,\n"
        "                        'cause_evidence':['interaction_history.jsonl','intersection_geometry.json',\n"
        "                                          'video_frames.jsonl']}],\n") + finalizer[end:]
    finalizer = finalizer.replace("'approaching_yield_observation':{'method':'measure_approaching_yield'", 
                                  "'far_approach_observation':{'method':'measure_far_approach'")
    finalizer = finalizer.replace("measure_approaching_yield(approaching)", "measure_far_approach(approaching)")
    files["finalizer.py"] = finalizer
    files["tests/test_hazard_sweep.py"] = (TARGET / "tests/test_hazard_sweep.py").read_text()
    files["tests/test_far_approach_observation.py"] = (TARGET / "tests/test_far_approach_observation.py").read_text()
    files["tests/source_fixture.json"] = (TARGET / "tests/source_fixture.json").read_text()
    source["case_id"] = CASE
    source["files"] = [{"path": path, "content": content}
                       for path, content in files.items()]
    source["mechanisms"]["subject"] = (
        "measured far-approach controller prototype; Native motion unverified")
    source["mechanisms"]["traffic"] = (
        "opposing body remains outside while subject tests a measured far-approach turn")
    TARGET.mkdir(parents=True, exist_ok=True)
    (TARGET / "runner.py").write_text(runner)
    (TARGET / "config.json").write_text(files["config.json"])
    (TARGET / "hazard_sweep_policy.py").write_text(files["hazard_sweep_policy.py"])
    (TARGET / "finalizer.py").write_text(finalizer)
    (TARGET / "far_approach_observation.py").write_text(files["far_approach_observation.py"])
    write_json(TARGET / "construction.json", source)
    candidate_specs = [
        ("fallback1", "controller_release_ttc_s", 5.5,
         "measured opposing closing motion leaves too little engineered release margin before subject turn"),
        ("fallback2", "approach_speed_mps", 4.0,
         "subject reaches the hold or conflict region at excessive measured speed"),
        ("fallback3", "reciprocal_approach_speed_mps", 1.5,
         "later opposing body reaches the junction during the subject's incomplete turn"),
    ]
    candidates = []
    for ident, knob, value, failure in candidate_specs:
        alternate = json.loads(json.dumps(source))
        alt_files = {row["path"]: row["content"] for row in alternate["files"]}
        alt_config = dict(config, **{knob: value})
        alt_files["config.json"] = json.dumps(alt_config, indent=2, ensure_ascii=False) + "\n"
        alternate["files"] = [{"path": path, "content": content}
                              for path, content in alt_files.items()]
        candidate_path = TARGET / (ident + "-construction.json")
        write_json(candidate_path, alternate)
        candidates.append({"id": ident, "construction": candidate_path.name,
                           "construction_sha256": sha(candidate_path),
                           "trigger": {"source": "interaction_history.jsonl and intersection_geometry.json",
                                       "metric": knob + " physical-risk observation",
                                       "failure_condition": failure},
                           "changed_knobs": [knob]})
    write_json(TARGET / "draft-manifest.json", {
        "format": "worker-execution-manifest",
        "assignment_id": FOLDER.name,
        "cases": [{"case_id": CASE, "construction": "construction.json",
                   "construction_sha256": sha(TARGET / "construction.json"),
                   "candidate_risk": {"status": "physical",
                                      "reason": "Native opposing and subject paths may not realize the intended far approach"},
                   "candidates": candidates}],
        "canonical_selection": False,
        "saved_source_proved": False,
        "comparison_proved": False,
    })
    print(json.dumps({"case_id": CASE,
                      "construction_sha256": sha(TARGET / "construction.json"),
                      "canonical_selection": False}))


if __name__ == "__main__":
    main()

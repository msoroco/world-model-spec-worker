"""Build unselected physical-obstruction branch constructions."""
import hashlib
import json
from pathlib import Path

from build_package import recording_description

ROOT = Path(__file__).resolve().parent
NATIVE = ROOT / "native"
PREFIX = ROOT.name + "__selected_statutory_"
SOURCES = {"runner.py": "statutory_runner.py", "geometry.py": "geometry.py",
           "activity_controller.py": "activity_controller.py",
           "statutory_variants.py": "statutory_variants.py",
           "branch_context.py": "branch_context.py",
           "statutory_measure.py": "statutory_measure.py",
           "source_join.py": "source_join.py", "finalize.py": "statutory_finalize.py"}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    plan = json.loads((ROOT / "statutory-branch-draft.json").read_text())
    chosen = [item for item in plan["cases"]
              if item["requests"]["obstruction_kind_request"] == "physical_obstruction"]
    ids = [item["case_id"] for item in chosen]
    template = json.loads((NATIVE / "config-condition_a.json").read_text())
    files = [{"path": target, "content": (NATIVE / source).read_text()}
             for target, source in SOURCES.items()]
    files.append({"path": "tests/test_bundle.py", "content": (ROOT / "tests/test_bundle.py").read_text()})
    entries = []
    for item in chosen:
        name = item["case_id"].removeprefix(PREFIX)
        requests = item["requests"]
        position = {"opposite": (2.5, -2.2), "alongside": (7.5, 2.2)}[requests["placement_request"]]
        cfg = dict(template, **requests, case_id=item["case_id"],
                   selected_case_id=item["case_id"], supported_case_ids=ids,
                   park_x_m=position[0], park_y_m=position[1], required_atoms=[],
                   source_packets=[], recording_description=recording_description())
        bundle = dict(case_id=item["case_id"], law_id="NRS-484B-450-1k",
                      cell_id="C135702", actor="motor_vehicle_driver",
                      entrypoint="runner.py", files=files + [{"path": "config.json",
                          "content": json.dumps(cfg, indent=2) + "\n"}],
                      measurement_plan={"entrypoint": "finalize.py", "required_sources": [
                          "native_samples.jsonl", "camera-frames.jsonl", "exception-context.json",
                          "obstruction-inventory.json", "road.xodr", "video_frames.jsonl"],
                          "source_review_required": True},
                      recording_description=recording_description(),
                      static_checks=["frozen assignment identity and source-gated statutory request",
                                     "physical barrier bodies and authored non-overlapping placement",
                                     "600 original frames at 20 Hz with four synchronized cameras"],
                      termination_rules=["600 original frames", "restore Native world and owned actors"],
                      mechanisms=["two-lane OpenDRIVE and three physical barrier assets",
                                  "finite stop/stand/park controller requests",
                                  "original body/velocity and reviewed activity/spatial/exception source readback"],
                      status="unselected_branch_draft_original_capture_pending")
        path = ROOT / "cases" / name / "statutory-construction.json"
        digest = write(path, bundle)
        fallback = json.loads(json.dumps(bundle))
        fallback_config = next(part for part in fallback["files"] if part["path"] == "config.json")
        fallback_values = json.loads(fallback_config["content"])
        fallback_values["passing_throttle"] = .35
        fallback_values["brake_station_x_m"] = -15
        fallback_config["content"] = json.dumps(fallback_values, indent=2) + "\n"
        fallback_path = ROOT / "cases" / name / "statutory-fallback1-construction.json"
        fallback_digest = write(fallback_path, fallback)
        entries.append({"case_id": item["case_id"], "kind": "delivery",
                        "construction": str(path.relative_to(ROOT)), "construction_sha256": digest,
                        "candidate_risk": {"status": "physical", "reason": "Original passing vehicle may not sustain a stable pre-obstruction halt with the primary braking station."},
                        "candidates": [{"id": "fallback1", "construction": str(fallback_path.relative_to(ROOT)),
                                        "construction_sha256": fallback_digest,
                                        "trigger": {"source": "original native_samples.jsonl",
                                                    "metric": "minimum_passing_speed_m_s and passing_halt_frames",
                                                    "failure_condition": "fewer than 20 source halt frames before the physical obstruction"},
                                        "changed_knobs": ["passing_throttle .25 to .35", "brake_station_x_m -11 to -15"]}],
                        "fixture_recipe": "work/" + ROOT.name + "/selected-recipe-statutory-" + name + ".json",
                        "measurement_contract": "measurement-statutory-" + name + ".json",
                        "measurement_procedure": {"entrypoint": "finalize.py"}})
    write(ROOT / "statutory-offline-draft-manifest.json",
          {"format": "worker-execution-manifest", "assignment_id": ROOT.name,
           "runtime_manifest_sha256": json.loads((ROOT / "execution-manifest.json").read_text())["runtime_manifest_sha256"],
           "status": "unselected_offline_branch_draft", "cases": entries})
    return len(entries)


if __name__ == "__main__":
    print(build())

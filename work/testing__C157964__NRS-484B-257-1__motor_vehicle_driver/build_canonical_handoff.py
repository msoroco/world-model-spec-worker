"""Build the root four-case source-gated canonical handoff artifacts."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ASSIGNMENT = "testing__C157964__NRS-484B-257-1__motor_vehicle_driver"
SHORT_CASES = ("yield_slow_approaching", "yield_stop_approaching",
               "yield_slow_occupied", "officer_controlling")
SIZES = ((1920, 1080), (1280, 720), (1280, 720), (1280, 720))
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def main():
    cases = [ASSIGNMENT + "__" + case for case in SHORT_CASES]
    config = {"assignment_id": ASSIGNMENT, "cell_id": "C157964",
              "law_id": "NRS-484B-257-1", "actor": "motor_vehicle_driver",
              "supported_case_ids": cases, "required_atoms": [], "source_packets": [],
              "duration_s": 45, "rate_hz": 20, "frame_count": 900,
              "source_gate": "reviewed_original_required",
              "cameras": [{"name": name, "width": width, "height": height,
                           "fov_deg": 90,
                           "pose_strategy": "reviewed site and original actor readback"}
                          for name, (width, height) in zip(VIEWS, SIZES)]}
    write(ROOT / "config.json", config)
    plan_path = ROOT / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    plan["camera_plan"] = {"profile": "overview1080-capability",
                           "duration_s": 45,
                           "composition": "synchronized_four_view_primary",
                           "coverage": [
                               {"view": "overview", "subject": "ego and through bodies, yield sign and highway",
                                "interval": "all 900 original frames"},
                               {"view": "approach", "subject": "yield approach and sign",
                                "interval": "approach through crossing"},
                               {"view": "reference_corner", "subject": "nearest-view reference and through body",
                                "interval": "approach through crossing"},
                               {"view": "driver_reference", "subject": "driver sight and governing control",
                                "interval": "approach through crossing"}]}
    write(plan_path, plan)
    proposal = json.loads((ROOT / "proposals/cases.json").read_text())
    recording = proposal["cases"][0]["recording_description"]
    paths = ("runner.py", "config.json", "yield_view.py", "reviewed_site.py",
             "native_capture.py", "native_adapter.py", "saved_audit.py", "saved_finalizer.py",
             "comparison_audit.py", "delivery_audit.py", "analysis.py")
    files = [{"path": path, "source": "work/" + ASSIGNMENT + "/" + path,
              "content": (ROOT / path).read_text()} for path in paths]
    construction = {"entrypoint": "runner.py", "cell_id": "C157964",
                    "law_id": "NRS-484B-257-1", "actor": "motor_vehicle_driver",
                    "supported_case_ids": cases, "files": files,
                    "recording_description": recording,
                    "measurement_plan": {"procedure": "analysis.py",
                                         "source": "900 sealed original Native frames and reviewed site"},
                    "mechanisms": ["source-gated yield approach", "source-gated through phase",
                                   "four synchronized original camera views"],
                    "static_checks": ["exact law/cell/actor/case identity",
                                      "reviewed site and source hashes",
                                      "original 20 Hz frame and camera joins"],
                    "termination_rules": {"duration_s": 45,
                                          "failed_source_or_camera": "reject without sealed original attempt"},
                    "diagnostic_fixture": False,
                    "physical_acceptance_claimed": False,
                    "legal_judgment": None}
    write(ROOT / "construction.json", construction)
    print(json.dumps({"canonical_cases": len(cases), "files": len(files)}, sort_keys=True))


if __name__ == "__main__":
    main()

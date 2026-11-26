"""Bundle all sixteen exact LVMC driveway cases and reverse approaches."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SOURCES = ("case-plan.json", "runner.py", "native_driveway.py", "finalize_native.py", "parking_controller.py",
           "driveway_construction.py", "driveway_measurements.py", "driveway_comparisons.py",
           "tests/test_bundle_contract.py")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def description():
    return {"channels": [
        {"name": "full_vehicle_footprint_to_driveway_mouth", "unit": "metres",
         "method": "original eight Native body vertices against reviewed mouth segment",
         "sampling_rate_hz": 20, "time_window": "45-second source-joined episode",
         "reference_frame": "original Native map and frame/time",
         "uncertainty": "physical placement and legal frontage require later review"},
        {"name": "settled_stop_stand_or_park_activity", "unit": "structured original source record",
         "method": "original Native speed, requested brake and control phase",
         "sampling_rate_hz": 20, "time_window": "45-second source-joined episode",
         "reference_frame": "original Native frame/time",
         "uncertainty": "requested activity alone does not prove legal activity"},
        {"name": "driveway_and_exception_context", "unit": "source record",
         "method": "retained reviewed map, mouth, frontage, relationship, purpose, direction and postal sources",
         "sampling_rate_hz": 20, "time_window": "entire exact episode",
         "reference_frame": "reviewed source packet and original map SHA",
         "uncertainty": "exception sufficiency and legal status require independent review"}],
        "context_inputs": [{"name": "reviewed_driveway_packet", "unit": "source record",
                            "method": "reviewed original context and source hashes before Native dispatch"}],
        "limitations": ["Five-foot geometry is a requested engineering bracket, not a legal finding.",
                        "Original pixels, activity and statutory exceptions require local review."]}


def construction(config_path, case):
    config = json.loads(config_path.read_text())
    files = []
    for name, path in [("config.json", config_path),
                       *[(name, ROOT / name) for name in SOURCES]]:
        files.append({"path": name, "source": str(path.relative_to(REPO)),
                      "content": path.read_text(encoding="utf-8")})
    return {"law_id": config["law_id"], "cell_id": config["cell_id"],
            "actor": config["actor"], "case_id": case["case_id"],
            "entrypoint": "runner.py", "files": files,
            "recording_description": config["recording_description"],
            "measurement_plan": {"case_id": case["case_id"],
                                 "procedure": "driveway_measurements.py",
                                 "original_frames": 900,
                                 "source_packets": ["reviewed_driveway_packet", "road.xodr",
                                                    "body-control-trace.jsonl", "camera-frame-map.jsonl"],
                                 "legal_frontage_and_exception_judgments": "unresolved"},
            "static_checks": ["exact source-hashed plan and selected condition",
                              "reviewed map, mouth, frontage and exception facts before Native launch",
                              "four same-tick original camera streams and eight body vertices"],
            "termination_rules": ["900 original frames at 20 Hz",
                                  "fail closed on absent source, short settled activity or restoration failure"],
            "mechanisms": ["source-gated full-footprint driveway target",
                           "route tracking then exact stop, stand or park hold",
                           "same-tick four-view original PNG acquisition",
                           "saved original source-sealed footprint and activity measurement"]}


def main():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    cases = [row["case_id"] for row in plan["cases"]]
    template = {"assignment_id": plan["assignment_id"], "law_id": plan["law_id"],
                "cell_id": plan["cell_id"], "actor": plan["actor"],
                "plan_sha256": sha(ROOT / "case-plan.json"),
                "rate_hz": 20, "frame_count": 900, "duration_s": 45,
                "cameras": [{"name": name, "width": width, "height": height,
                             "fov_deg": 75, "pose_strategy": "reviewed original source packet"}
                            for name, width, height in (("overview", 1920, 1080),
                                                        ("approach", 1280, 720),
                                                        ("reference_corner", 1280, 720),
                                                        ("driver_reference", 1280, 720))],
                "recording_description": description(),
                "required_atoms": [], "source_packets": [],
                "source_requirements": ["reviewed_driveway_packet", "original_eight_body_vertices",
                                        "original_activity", "four_original_camera_png_streams"],
                "supported_case_ids": cases, "diagnostic_only": True}
    entries = []
    for row in plan["cases"]:
        slug = row["case_id"].removeprefix(plan["assignment_id"] + "__")
        folder = ROOT / "cases" / slug
        candidates = []
        for candidate, direction in (("primary", 1), ("fallback1", -1)):
            config = dict(template, selected_case_id=row["case_id"],
                          driveway_kind=row["driveway_kind"], activity=row["activity"],
                          position_target=row["position_target"],
                          driver_relationship=row["driver_relationship"],
                          necessity_or_postal_context=row["necessity_or_postal_context"],
                          approach_direction=direction)
            config_path = folder / ("config.json" if candidate == "primary"
                                    else "config-fallback1.json")
            write(config_path, config)
            path = folder / ("construction.json" if candidate == "primary"
                             else "construction-fallback1.json")
            bundle = construction(config_path, row)
            bundle["candidate_id"] = candidate
            write(path, bundle)
            candidates.append((path, sha(path)))
            if row is plan["cases"][0] and candidate == "primary":
                write(ROOT / "config.json", config)
                write(ROOT / "construction.json", construction(ROOT / "config.json", row))
        entries.append({"case_id": row["case_id"], "kind": "delivery",
                        "construction": str(candidates[0][0].relative_to(ROOT)),
                        "construction_sha256": candidates[0][1],
                        "candidate_risk": {"status": "physical",
                                           "reason": "surveyed approach may be obstructed in Native map"},
                        "candidates": [{"id": "fallback1",
                                        "construction": str(candidates[1][0].relative_to(ROOT)),
                                        "construction_sha256": candidates[1][1],
                                        "trigger": {"source": "original Native route and collision feedback",
                                                    "metric": "unobstructed target reachability",
                                                    "failure_condition": "primary approach cannot reach the exact target"},
                                        "changed_knobs": ["approach_direction: +1 to -1"]}]})
    write(ROOT / "execution-manifest.draft.json",
          {"format": "worker-execution-manifest", "assignment_id": plan["assignment_id"],
           "cases": entries, "draft_missing_proofs": ["semantic", "offline", "compatibility",
                                               "saved", "physical", "delivery"]})
    print(len(entries), "exact LVMC driveway bundles and reverse-approach candidates built")


if __name__ == "__main__":
    main()

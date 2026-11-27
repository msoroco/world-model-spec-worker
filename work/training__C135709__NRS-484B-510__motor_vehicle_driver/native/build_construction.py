"""Materialize the six exact restricted-zone Native request bundles.

This creates construction inputs only. It does not select a case for delivery or
claim that the sign, purpose, passenger exchange, or interference was observed.
"""

import hashlib
import json
from pathlib import Path

from capture_plan import AID, CAMERAS, CASES, build

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SOURCES = ("runner.py", "capture_plan.py", "geometry.py", "parking_controller.py",
           "original_source_contract.py", "finalize.py")
CHANNELS = ("st.curb_zone", "dev.regulatory_sign", "drv.condition_in_effect",
            "drv.standing_or_parked", "kin.time", "ru.occupant_count",
            "sig.door_open", "ru.pedestrian", "ru.motor_vehicle", "drv.approaching")
TEST = '''import json
import unittest
from pathlib import Path
from capture_plan import AID, build
from runner import check


class ExactRestrictedZoneRequest(unittest.TestCase):
    def test_materialized_request(self):
        config = json.loads(Path("config.json").read_text())
        case_id = config["case_id"]
        request = build(case_id[len(AID) + 2:],
                        approach_speed_cap_mps=config["approach_speed_cap_mps"])
        self.assertEqual(check(request)["case_id"], case_id)
        self.assertEqual(config["camera_sizes"], {name: list(size) for name, size in request["camera_sizes"].items()})
        self.assertEqual(config["frames"], 600)
        self.assertIn(config["approach_speed_cap_mps"], (3.0, 4.0))
        self.assertFalse(config["physical_acceptance_claimed"])
        request["duration_s"] = 10
        with self.assertRaisesRegex(ValueError, "differs"):
            check(request)
'''


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def recording_description() -> dict:
    return {"channels": [{"name": name, "unit": "structured",
                           "sampling_rate_hz": 20,
                           "method": "Original Native map, actor, camera and independent review source join",
                           "time_window": "all 600 original frames",
                           "reference_frame": "authored C135709 narrow road and surveyed zone",
                           "uncertainty": "Sign authority, actual purpose, passenger loading and interference require original review"}
                          for name in CHANNELS],
            "context_inputs": [],
            "limitations": ["Authored sign and controller requests do not establish legal restriction",
                            "Door requests and nearby walkers do not establish actual passenger loading",
                            "Synthetic source checks do not establish physical camera visibility"]}


def main() -> None:
    description = recording_description()
    outputs = []
    draft_entries = []
    for suffix in CASES:
        request = build(suffix)
        case_id = request["case_id"]
        folder = ROOT / "cases" / suffix
        cameras = [{"name": name, "width": size[0], "height": size[1],
                    "fps": 20, "fov_deg": 85,
                    "pose_strategy": "fixed_world_restricted_zone_and_approach"}
                   for name, size in CAMERAS.items()]
        config = {"assignment_id": AID, "case_id": case_id,
                  "selected_case_id": case_id, "supported_case_ids": [AID + "__" + s for s in CASES],
                  "law_id": "NRS-484B-510", "cell_id": "C135709",
                  "actor": "motor_vehicle_driver", "frozen_cell": request["frozen_cell"],
                  "rate_hz": 20, "duration_s": 30, "frames": 600,
                  "camera_sizes": {name: list(size) for name, size in CAMERAS.items()},
                  "cameras": cameras, "required_atoms": [], "source_packets": [],
                  "requested_purpose": request["requested_purpose"],
                  "passenger_exchange_request": request["passenger_exchange_request"],
                  "waiting_vehicle_request": request["waiting_vehicle_request"],
                  "departure_frame": request["departure_frame"],
                  "approach_speed_cap_mps": 4.0,
                  "physical_acceptance_claimed": False, "legal_verdict": None,
                  "recording_description": description,
                  "case": {"case_id": case_id, "recording_description": description}}
        write(folder / "config.json", config)
        files = [{"path": name, "content": (HERE / name).read_text(encoding="utf-8")}
                 for name in SOURCES]
        files.extend(({"path": "config.json", "content": (folder / "config.json").read_text(encoding="utf-8")},
                      {"path": "tests/test_request.py", "content": TEST}))
        construction = {"format": "worker-inline-construction", "case_id": case_id,
                        "law_id": "NRS-484B-510", "cell_id": "C135709",
                        "actor": "motor_vehicle_driver", "entrypoint": "runner.py",
                        "files": files, "recording_description": description,
                        "measurement_plan": {"entrypoint": "finalize.py",
                                             "source_review_required": True,
                                             "required_sources": ["road.xodr", "zone-survey.json",
                                                                  "actor-frames.jsonl", "camera-frames.jsonl",
                                                                  "trace.jsonl", "video_frames.jsonl",
                                                                  "capture-manifest.json", "capture-seal.json",
                                                                  "source-review.json"]},
                        "static_checks": ["Exact six-case restricted-purpose, stop, stand and exception request matrix",
                                          "30-second four-camera Native source joins",
                                          "Original sign authority and purpose remain independently reviewed"],
                        "mechanisms": ["Authored OpenDRIVE sign and restricted zone",
                                       "Source-hashed actor, camera and map capture",
                                       "Independent original-source review required"],
                        "termination_rules": ["600 original Native frames",
                                              "Destroy owned actors and restore world"],
                        "status": "cpu_construction_physical_unverified"}
        write(folder / "construction.json", construction)
        fallback_folder = folder / "fallback1"
        fallback_config = dict(config, approach_speed_cap_mps=3.0)
        write(fallback_folder / "config.json", fallback_config)
        fallback_files = [dict(item) for item in files]
        for item in fallback_files:
            if item["path"] == "config.json":
                item["content"] = (fallback_folder / "config.json").read_text(encoding="utf-8")
        fallback_construction = dict(construction, files=fallback_files)
        write(fallback_folder / "construction.json", fallback_construction)
        fallback_sha = hashlib.sha256((fallback_folder / "construction.json").read_bytes()).hexdigest()
        outputs.append(case_id)
        draft_entries.append({"case_id": case_id,
                              "construction": f"cases/{suffix}/construction.json",
                              "construction_sha256": hashlib.sha256(
                                  (folder / "construction.json").read_bytes()).hexdigest(),
                              "candidate_risk": {"status": "physical",
                                                 "reason": "At 4 m/s the full ego footprint may overshoot the narrow restricted zone"},
                              "candidates": [{"id": "fallback1",
                                              "construction": f"cases/{suffix}/fallback1/construction.json",
                                              "construction_sha256": fallback_sha,
                                              "trigger": {"source": "original ego body and zone survey",
                                                          "metric": "full footprint inside surveyed zone at rest",
                                                          "failure_condition": "primary footprint overshoots zone"},
                                              "changed_knobs": ["approach_speed_cap_mps: 4.0 to 3.0"]}]})
    write(ROOT / "config.json", json.loads((ROOT / "cases" / "witness_1" / "config.json").read_text()))
    write(ROOT / "construction.json", json.loads((ROOT / "cases" / "witness_1" / "construction.json").read_text()))
    write(ROOT / "draft-construction-manifest.json",
          {"format": "restricted-zone-unselected-construction-manifest-v1",
           "assignment_id": AID, "cases": draft_entries,
           "delivery_readiness_claimed": False})
    print(json.dumps({"constructed_case_ids": outputs, "selected": False}, sort_keys=True))


if __name__ == "__main__":
    main()

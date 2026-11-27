"""Build two selected signed-road Native bundles with one shared capture policy."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent.parent
NATIVE = HERE / "native"
AID = HERE.name
LAW = "LVMC-11-40-180-B"
CASES = ("witness_1", "witness_2")
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
CHANNELS = ("dev.regulatory_sign", "dev.governs", "dev.position", "ru.bicycle",
            "ru.electric_bicycle", "ru.electric_scooter", "st.sidewalk",
            "st.roadway", "rel.occupies")


def encoded(value):
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    source_files = {name: (NATIVE / name).read_text() for name in
                    ("runner.py", "signed_access_measure.py", "finalize.py", "signed-road.xodr")}
    cameras = [{"name": name, "width": 1920 if name == "overview" else 1280,
                "height": 1080 if name == "overview" else 720,
                "fov_deg": 85 if name == "overview" else 80,
                "pose_strategy": "fixed source-reviewed roadway and sign view"}
               for name in CAMERAS]
    recording = {"channels": [{"name": name, "unit": "structured", "sampling_rate_hz": 20,
                               "method": "joined original rider, sign, street and source review",
                               "time_window": "all 600 source frames",
                               "reference_frame": "Native roadway and sign-governed interval",
                               "uncertainty": "original sign pixels and authority need independent review"}
                              for name in CHANNELS],
                 "context_inputs": [{"name": "sign_source_review", "unit": "structured",
                                     "method": "hash-bound original sign and administrative source packet"}],
                 "limitations": ["Synthetic diagnostic does not prove an erected applicable original sign",
                                 "Riding and Director determination remain source-reviewed at delivery"]}
    refs = []
    for suffix in CASES:
        case = AID + "__" + suffix
        route = "outside" if suffix == "witness_1" else "enter"
        cfg = {"format": "c230207-signed-road-request-v1", "assignment_id": AID,
               "law_id": LAW, "cell_id": "C230207", "actor": "cycle_or_scooter_operator",
               "case_id": case, "selected_case_id": case,
               "supported_case_ids": [AID + "__" + name for name in CASES],
               "case": {"case_id": case, "recording_description": recording},
               "candidate_id": "primary", "route_kind": route,
               "start_x_m": 10 if route == "outside" else 30,
               "target_speed_mps": .4 if route == "outside" else 1.0,
               "street_y_m": -3.0, "governed_x_interval_m": [40, 60],
               "rate_hz": 20, "duration_s": 30, "capture_frames": 600,
               "cameras": cameras, "road_sha256": hashlib.sha256(
                   source_files["signed-road.xodr"].encode()).hexdigest(),
               "required_atoms": [], "source_packets": [],
               "original_native_observed": False,
               "physical_or_legal_acceptance": False}
        folder = HERE if suffix == "witness_1" else HERE / "cases" / suffix
        folder.mkdir(parents=True, exist_ok=True)
        test = ("import json\nimport unittest\nfrom runner import config_check, request\n\n"
                "class TestSignedRoad(unittest.TestCase):\n"
                "    def test_exact_route(self):\n"
                "        cfg = config_check()\n"
                "        self.assertEqual(cfg['case_id'], '" + case + "')\n"
                "        self.assertFalse(request(200, cfg)['observed_motion'])\n")
        files = [(name, text) for name, text in source_files.items()]
        files.extend((("config.json", encoded(cfg)), ("tests/test_signed_road.py", test)))
        for name, text in files:
            path = folder / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        construction = {"case_id": case, "law_id": LAW, "cell_id": "C230207",
                        "actor": "cycle_or_scooter_operator", "entrypoint": "runner.py",
                        "files": [{"path": name, "content": text} for name, text in files],
                        "measurement_plan": {"entrypoint": "finalize.py",
                                             "required_sources": ["setup.json", "raw-frames.json",
                                                                  "video_frames.jsonl"],
                                             "source_review_required": True},
                        "recording_description": recording,
                        "static_checks": ["same sign and roadway geometry", "600 joined frames",
                                          "four source cameras"],
                        "mechanisms": ["surveyed physical prohibition sign prop",
                                       "source reviewed rider path and governed interval"],
                        "termination_rules": ["600 synchronized 20 Hz frames", "restore Native world"],
                        "status": "selected_cpu_draft_original_capture_pending"}
        path = folder / "construction.json"
        path.write_text(encoded(construction))
        refs.append({"case_id": case, "construction": str(path.relative_to(HERE)),
                     "construction_sha256": digest(path), "kind": "draft_not_ready",
                     "candidates": []})
    manifest = {"format": "worker-signed-road-construction-draft-v1",
                "assignment_id": AID, "status": "partial_cpu_construction", "cases": refs}
    (HERE / "construction-draft.json").write_text(encoded(manifest))
    print(encoded({"cases": refs}))


if __name__ == "__main__":
    build()

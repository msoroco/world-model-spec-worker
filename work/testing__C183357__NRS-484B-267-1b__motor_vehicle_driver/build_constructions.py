"""Materialize source-gated exact 1b bundles for every selected variant."""

from __future__ import annotations

import json
from pathlib import Path

from native_packet import AID, VIEWS

HERE = Path(__file__).resolve().parent
SCRIPTS = ("runner.py", "native_packet.py", "curb_construction.py", "analysis.py")
SIZES = ((1920, 1080), (1280, 720), (1280, 720), (1280, 720))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("construction exceeds 2 MiB: " + str(path))


def description():
    channels = (
        ("sealed_native_original_frames", "frame identity", "byte-sealed 20 Hz Native source"),
        ("unit_motion", "metres", "original emergency/regulatory unit poses"),
        ("qualifying_flashing_lights", "on/off", "original lamp state and front-camera pixels"),
        ("front_visible_red_lamp", "source", "reviewed equipment and original front-view pixels"),
        ("siren_equipment", "source", "reviewed installed equipment"),
        ("target_authorization", "source", "reviewed authorized or official status"),
        ("subject_driver", "source", "reviewed ordinary vehicle and actual driver control"),
        ("relative_approach", "metres", "joined subject/unit poses and route direction"),
        ("ego_response", "control", "original subject brake and speed chronology"),
        ("officer_direction", "source", "independent original officer direction or absence"),
        ("edge_distance", "m", "subject body edge to surveyed right curb/roadway edge"),
        ("body_yaw_to_edge", "degrees", "subject body axis versus surveyed edge tangent"),
        ("intersection_overlap", "boolean", "subject body polygon versus intersection boundary"),
        ("shoulder_region", "class", "subject body versus roadway and paved shoulder polygons"),
        ("ego_body_geometry", "metres", "original subject body polygon after each Native tick"),
        ("shoulder_sign", "source", "reviewed lawful sign class and applicability"),
        ("video_four_views", "frame identity", "four synchronized original camera views"),
    )
    return {"channels": [{"name": name, "unit": unit, "method": method,
                          "sampling_rate_hz": 20, "time_window": "all 900 original frames",
                          "reference_frame": "reviewed Native highway/curb/shoulder packet",
                          "uncertainty": "physical realization and legal positioning remain unverified"}
                         for name, unit, method in channels],
            "context_inputs": [], "limitations": [
                "Immediate approach and as close as possible are judgment phrases without invented legal distance cutoffs.",
                "Authorization, red lamp, siren, shoulder sign and officer context require independent original-source review.",
                "Physical body position, lane boundaries and pixels require local Native capture and review."]}


def config(case, all_ids):
    return {"assignment_id": AID, "law_id": "NRS-484B-267-1b", "cell_id": "C183357",
            "actor": "motor_vehicle_driver", "selected_case_id": case["case_id"],
            "supported_case_ids": all_ids, "rate_hz": 20, "duration_s": 45, "frame_count": 900,
            "required_atoms": [], "source_packets": [],
            "engineering": {"alternate_unit_route": False},
            "cameras": [{"name": name, "width": size[0], "height": size[1],
                         "pose_strategy": "reviewed Native body, curb and unit source survey",
                         "fov_deg": 90} for name, size in zip(VIEWS, SIZES)],
            "case": dict(case, recording_description=description(),
                         yield_response_request=case["subject_position_request"] != "paved_shoulder_traverse")}


def build():
    plan_path = HERE / "case-plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    cases = plan["cases"]
    all_ids = [row["case_id"] for row in cases]
    if len(cases) != 19 or len(set(all_ids)) != 19 or len(plan["comparisons"]) != 18:
        raise ValueError("exact selected plan changed")
    plan["observations"] = [{"name": channel["name"], "mandatory": True}
                            for channel in description()["channels"]]
    plan["source_observation_mapping"] = {}
    plan["camera_plan"] = {"profile": "overview1080-capability", "duration_s": 45,
        "composition": "synchronized_four_view_primary",
        "coverage": [{"view": name, "subject": subject, "interval": "all original 900 frames"}
                     for name, subject in zip(VIEWS, (
                         "subject and approaching unit", "front flashing lamp and unit motion",
                         "curb, paved shoulder, sign and intersection", "driver view and body-to-edge position"))]}
    for case in cases:
        case["construction_status"] = "source_gated_exact_bundle"
    write(plan_path, plan)
    code = {name: (HERE / name).read_text(encoding="utf-8") for name in SCRIPTS}
    for index, case in enumerate(cases):
        case_id = case["case_id"]
        cfg = json.dumps(config(case, all_ids), indent=2, ensure_ascii=False) + "\n"
        suffix = case["variant"]
        test = ('"""Exact bundle identity."""\nimport unittest\nimport sys\nfrom pathlib import Path\n'
                'sys.path.insert(0, str(Path(__file__).resolve().parents[1]))\n'
                'from runner import check\n\nclass BundleTest(unittest.TestCase):\n'
                '    def test_case(self):\n        self.assertTrue(check()["selected_case_id"].endswith("__'
                + suffix + '"))\n')
        files = [{"path": name, "content": content} for name, content in code.items()]
        files += [{"path": "config.json", "content": cfg},
                  {"path": "tests/test_bundle.py", "content": test}]
        bundle = {"law_id": "NRS-484B-267-1b", "cell_id": "C183357",
                  "actor": "motor_vehicle_driver", "case_id": case_id,
                  "entrypoint": "runner.py", "diagnostic_only": True,
                  "recording_description": description(), "files": files,
                  "measurement_plan": "900 original subject/unit poses, full body geometry, curb and shoulder distances, sign and lamp source, four-view video",
                  "static_checks": ["reviewed Native highway, curb, paved shoulder, intersection and sign source hashes",
                                    "connected qualifying emergency approach and officer context",
                                    "four synchronized camera frame joins"],
                  "termination_rules": ["900 synchronized Native ticks", "restore and read back world"],
                  "mechanisms": ["source-gated road, shoulder, curb, sign and intersection geometry",
                                 "spawn two real Native vehicle actors and control approach and subject positioning",
                                 "seal original histories and four-view camera capture"]}
        path = HERE / "cases" / suffix
        write(path / "construction.json", bundle)
        if index == 0:
            (HERE / "config.json").write_text(cfg, encoding="utf-8")
            (HERE / "tests/test_bundle.py").write_text(test, encoding="utf-8")
            write(HERE / "construction.json", bundle)
    return all_ids


if __name__ == "__main__":
    print("\n".join(build()))

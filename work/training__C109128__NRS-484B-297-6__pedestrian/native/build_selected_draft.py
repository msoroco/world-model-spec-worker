"""Bind the original Native construction into two exact offline drafts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


TEST = '''import json
import unittest
from pathlib import Path
from native_scene import check, request, FRAMES, CAMERAS

class ExactBypassOffline(unittest.TestCase):
    def test_exact_identity_and_geometry(self):
        cfg = json.loads(Path('config.json').read_text())
        self.assertTrue(check()['passed'])
        self.assertEqual(cfg['case_id'], cfg['selected_case_id'])
        self.assertEqual(cfg['case_id'], cfg['case']['case_id'])
        self.assertEqual((cfg['cell_id'], cfg['law_id'], cfg['actor']),
                         ('C109128', 'NRS-484B-297-6', 'pedestrian'))
        self.assertEqual((cfg['rate_hz'], cfg['duration_s']), (20, 30))
        self.assertEqual(len(cfg['cameras']), len(CAMERAS))
        self.assertEqual(request(cfg['case_suffix'], FRAMES - 1)['target_xy_m'][1], -5)
        self.assertIn(cfg['candidate_id'], ('primary', 'fallback1'))
'''


def build():
    plan = json.loads((ASSIGNMENT / "case-plan.json").read_text())
    cases = plan["cases"]
    if len(cases) != 2 or {case["condition_index"] for case in cases} != {0, 1}:
        raise ValueError("two exact frozen lateral bypass case identities required")
    names = ("ru.subject", "ru.pedestrian", "st.sidewalk", "st.obstruction",
             "st.highway", "st.road_edge", "st.intersection", "rel.occupies",
             "kin.position", "kin.heading", "kin.path_length", "kin.time")
    recording = {"channels": [{"name": name, "unit": "structured",
                               "sampling_rate_hz": 20,
                               "method": "saved original Native map, body and camera/frame joins",
                               "time_window": "entire 600-frame 30-second attempt",
                               "reference_frame": "original Native frame and time",
                               "uncertainty": "50 ms samples; physical and legal judgments pending",
                               "source": "channels/" + name + ".jsonl"} for name in names],
                 "context_inputs": [{"name": "sidewalk_context", "unit": "source",
                                     "method": "original Native map and obstruction readback"}],
                 "limitations": ["Physical obstruction, due care, immediately adjacent highway public status, side-as-possible and practicable return require independent review"]}
    camera = [{"name": name, "width": width, "height": height, "fps": 20,
               "location_xyz_m": [x, y, z],
               "rotation_pitch_yaw_roll_deg": [pitch, 0, 0],
               "source_required": True}
              for name, width, height, x, y, z, pitch in __import__("native_scene").CAMERAS]
    shared = {"cell_id": "C109128", "law_id": "NRS-484B-297-6",
              "actor": "pedestrian", "duration_s": 30, "rate_hz": 20,
              "supported_case_ids": [case["case_id"] for case in cases],
              "required_atoms": ["ru.pedestrian", "kin.position", "kin.heading",
                                 "rel.occupies", "st.sidewalk", "st.obstruction",
                                 "st.intersection"],
              "source_packets": [], "cameras": camera,
              "recording_description": recording}
    common_files = [("runner.py", (HERE / "runner.py").read_text()),
                    ("native_scene.py", (HERE / "native_scene.py").read_text()),
                    ("finalize.py", (HERE / "finalize.py").read_text()),
                    ("tests/test_offline.py", TEST)]
    entries = []
    for case in cases:
        condition = "condition_a" if case["condition_index"] == 0 else "condition_b"
        candidates = []
        for candidate_id, shift in (("primary", 0.0), ("fallback1", .08)):
            config = dict(shared, case_id=case["case_id"],
                          selected_case_id=case["case_id"],
                          case={"case_id": case["case_id"]},
                          case_suffix=condition, candidate_id=candidate_id,
                          lateral_shift_m=shift, obstruction_raise_z_m=0.0)
            files = [{"path": path, "content": content} for path, content in common_files]
            files.append({"path": "config.json", "content":
                          json.dumps(config, indent=2) + "\n"})
            construction = {"case_id": case["case_id"], "cell_id": "C109128",
                            "law_id": "NRS-484B-297-6", "actor": "pedestrian",
                            "entrypoint": "runner.py", "files": files,
                            "recording_description": recording,
                            "measurement_plan": "Original walker footprint, lane and obstruction readbacks, edge distance and full sidewalk return",
                            "static_checks": ["600 frames at 20 Hz", "four source cameras",
                                              "four-way junction with adjacent sidewalk", "ten physical obstruction props"],
                            "termination_rules": ["30-second capture end", "abort on missing source or Native mutation failure"],
                            "mechanisms": ["Native OpenDRIVE four-way junction", "Native walker controller",
                                           "Native static obstruction actors", "per-tick source capture"],
                            "status": "selected_cpu_draft_no_public_receipt"}
            target = HERE / "selected-drafts" / condition / candidate_id / "construction.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(construction, indent=2) + "\n")
            candidates.append((candidate_id, target, sha(target)))
        primary, fallback = candidates
        entries.append({"case_id": case["case_id"],
                        "construction": str(primary[1].relative_to(HERE)),
                        "construction_sha256": primary[2],
                        "candidate_risk": {"status": "physical",
                            "reason": "Native shoulder tracking could leave the intended near-side strip; fallback shifts the controller target laterally by 8 cm while preserving the exact case and comparison variable"},
                        "candidates": [{"id": "fallback1",
                            "construction": str(fallback[1].relative_to(HERE)),
                            "construction_sha256": fallback[2],
                            "trigger": {"source": "original pedestrian footprint/map readback",
                                        "metric": "minimum distance to sidewalk-side road edge",
                                        "failure_condition": "primary full footprint leaves surveyed shoulder strip before obstruction clearance"},
                            "changed_knobs": ["lateral_shift_m: 0.0 to 0.08"]}]})
    manifest = {"format": "worker-selected-cpu-draft-manifest-v1",
                "assignment_id": ASSIGNMENT.name,
                "status": "draft_no_public_compatibility",
                "delivery_ready": False, "cases": entries}
    target = HERE / "selected-draft-manifest.json"
    target.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"cases": len(entries), "candidates": 4,
                      "manifest_sha256": sha(target)}))


if __name__ == "__main__":
    build()

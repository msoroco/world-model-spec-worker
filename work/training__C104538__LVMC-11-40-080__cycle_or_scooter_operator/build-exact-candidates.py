"""Build eight exact, unselected mounted-bicycle Native constructions."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
NAMES = ("primary", "fallback1", "fallback2", "fallback3")
CASE_MAP = {"mounted_obey": AID+"__controlled_1",
            "mounted_turn": AID+"__controlled_2"}
RUNTIME_SHA = "391baee19ccece687c5632aa2cc64ba3b958c8b492045b30e4bfc4caa131c235"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True)+"\n")


def description():
    methods = {
        "dev.regulatory_sign": "Native landmark readback and original sign pixels; authorization review pending",
        "dev.governs": "Original sign pixels joined to surveyed approach lane; applicability review pending",
        "dev.position": "Native landmark station and sign camera frame",
        "ru.bicycle": "Original Native bicycle blueprint, actor ID and full-body pose",
        "ru.rider_posture": "Original rider pixels required; Native actor class alone cannot establish mounting",
        "drv.u_turn": "Original Native body and heading trace; requested turn is separate",
        "kin.heading": "Original Native forward vector per joined frame",
        "rel.occupies": "Original bicycle full-body polygon and Native lane ID",
        "native_body_pose_control": "Original Native pose, speed and controller request",
        "camera_frame_join": "Four original source cameras joined to Native frame and time",
    }
    return {"channels": [{"name": name, "unit": "structured", "sampling_rate_hz": 20,
             "method": method, "time_window": "entire 24 s / 480-frame attempt",
             "reference_frame": "Native map and original camera frame",
             "uncertainty": "50 ms sampling; original sign and rider pixels require review"}
             for name, method in methods.items()],
            "context_inputs": [{"name": "signed_hill_crest", "unit": "structured",
             "method": "Native lane/landmark readback and original sign pixel review"}],
            "limitations": ["Authored sign is not proof of legal authorization",
                            "Bicycle blueprint does not prove mounted rider posture",
                            "Requested turn does not prove physical movement or a legal outcome"]}


def build():
    plan = json.loads((HERE/"case-plan.json").read_text())
    planned = {case["case_id"] for case in plan["cases"]}
    assert set(CASE_MAP.values()).issubset(planned)
    files = {name: (HERE/"native"/name).read_text() for name in
             ("runner.py", "geometry.py", "engineering.py", "controller.py", "cameras.py", "finalize.py")}
    files["tests/test_bundle.py"] = (
        "import json\nimport unittest\nfrom pathlib import Path\nimport runner\n"
        "class Bundle(unittest.TestCase):\n"
        "    def test_exact_preflight(self):\n"
        "        c=json.loads(Path('config.json').read_text())\n"
        "        p=runner.check(c['case_suffix'],c['candidate_id'])\n"
        "        self.assertEqual(p['native_route_points']>600,True)\n"
        "        self.assertEqual(len(p['camera_views']),4)\n"
        "        self.assertFalse(p['native_imported'])\n"
        "        self.assertTrue(p['native_capture_pending'])\n")
    desc = description()
    manifest = {"format": "worker-unselected-draft-construction-manifest-v1",
                "assignment_id": AID, "runtime_manifest_sha256": RUNTIME_SHA,
                "status": "draft_not_selected", "cases": []}
    risk = {
        "fallback1": ("approach_runway_m", "under 35 m", ["approach start -35 to -50 m"]),
        "fallback2": ("release_error_frames", "over 3 frames", ["turn release 220 to 225"]),
        "fallback3": ("scripted_visibility", "below 0.95", ["sign camera [-12,9,5] to [-12,11,6]"]),
    }
    for kind, case_id in CASE_MAP.items():
        entry = {"case_id": case_id, "kind": "draft_not_selected",
                 "candidate_risk": {"status": "physical", "reason": "Bicycle asset, sign, rider posture, route and pixels need original Native readback"},
                 "measurement_contract": "draft-measurement-contract.json",
                 "measurement_procedure": {"entrypoint": "finalize.py", "output_schema": "c104538-lvmc-synthetic-saved-mounted-diagnostic-v1"},
                 "candidates": []}
        for name in NAMES:
            config = {"case_id": case_id, "selected_case_id": case_id,
                      "supported_case_ids": [case_id], "case_suffix": kind,
                      "candidate_id": name, "cell_id": "C104538",
                      "law_id": "LVMC-11-40-080", "actor": "cycle_or_scooter_operator",
                      "rate_hz": 20, "duration_s": 24,
                      "required_atoms": ["dev.regulatory_sign", "dev.governs", "dev.position",
                                         "ru.bicycle", "ru.rider_posture", "drv.u_turn",
                                         "kin.heading", "rel.occupies"],
                      "source_packets": [], "mandatory_channels": ["ru.bicycle", "ru.rider_posture"],
                      "case": {"case_id": case_id}, "recording_description": desc,
                      "cameras": [{"name": view, "width": width, "height": height,
                         "pose_strategy": "candidate-specific Native mount in cameras.py", "fov_deg": fov}
                         for view, width, height, fov in
                         (("overview",1920,1080,75), ("approach",1280,720,92),
                          ("sign_reference",1280,720,90), ("driver_reference",1280,720,105))],
                      "status": "unselected_native_capture_draft"}
            candidate_files = [{"path": path, "content": content} for path, content in files.items()]
            candidate_files.append({"path": "config.json", "content": json.dumps(config, indent=2)+"\n"})
            construction = {"case_id": case_id, "cell_id": "C104538",
                "law_id": "LVMC-11-40-080", "actor": "cycle_or_scooter_operator",
                "entrypoint": "runner.py", "files": candidate_files,
                "measurement_plan": {"method": "original Native bicycle full body, sign and rider posture review",
                                     "status": "exact_bundle_unselected_original_native_pending"},
                "recording_description": desc,
                "static_checks": ["authored map/route", "four original cameras",
                                  "source-bound synthetic trigger measurements"],
                "termination_rules": ["480 original frames", "failure retained on capture/restoration error"],
                "mechanisms": ["authored hill crest and sign proposal", "exact bicycle blueprint",
                               "observed-pose path controller", "four FFV1 original cameras"],
                "status": "unselected_cpu_draft"}
            relative = f"draft-exact-candidates/{kind}/{name}/construction.json"
            path = HERE/relative
            write(path, construction)
            ref = {"id": name, "construction": relative, "construction_sha256": sha(path)}
            if name == "primary": entry.update(ref)
            else:
                metric, condition, knobs = risk[name]
                ref.update({"trigger": {"source": "source-hashed Native rows and original sign/rider camera review",
                                        "metric": metric, "failure_condition": condition},
                            "changed_knobs": knobs})
                entry["candidates"].append(ref)
        manifest["cases"].append(entry)
    target = HERE/"draft-exact-execution-manifest.json"
    write(target, manifest)
    return {"cases": 2, "candidates": 8, "manifest_sha256": sha(target), "selected": False}


if __name__ == "__main__":
    print(json.dumps(build()))

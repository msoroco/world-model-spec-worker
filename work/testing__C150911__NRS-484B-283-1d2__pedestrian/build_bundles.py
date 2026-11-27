"""Materialize six distinct 1d2 source-gated delivery constructions."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build_semantic import recording_description

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MODULES = ("runner.py", "native_entry.py", "reviewed_site.py",
    "countdown_crossing.py", "analysis.py")
OFFLINE_TEST = '''import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runner import check

class SelectedCountdownOffline(unittest.TestCase):
    def test_source_gate_and_identity(self):
        root = Path(__file__).resolve().parents[1]
        result = check(root)
        self.assertEqual(result["case_id"], json.loads((root / "config.json").read_text())["selected_case_id"])
        self.assertIn("reviewed original", result["source_gate"])

if __name__ == "__main__":
    unittest.main()
'''


def write(path: Path, value: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True,
        ensure_ascii=False) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> list[dict]:
    plan = json.loads((HERE / "case-plan.json").read_text())
    ids = [case["case_id"] for case in plan["cases"]]
    entries = []
    for case in plan["cases"]:
        cid = case["case_id"]
        short = cid.split("__")[-1]
        folder = HERE / "cases" / short
        description = recording_description()
        config = {"law_id": plan["law_id"], "cell_id": plan["cell_id"],
            "actor": plan["actor"], "selected_case_id": cid,
            "supported_case_ids": ids, "required_atoms": [], "source_packets": [],
            "rate_hz": 20, "duration_s": 45,
            "cameras": [{"name": name, "width": width, "height": height,
                "fov_deg": 75,
                "pose_strategy": "reviewed original crossing, signal and countdown camera pose"}
                for name, width, height in (("overview", 1920, 1080),
                    ("approach", 1280, 720), ("reference_corner", 1280, 720),
                    ("driver_reference", 1280, 720))],
            "physical_completion": {"criterion": "travel_progress",
                "motion_source": "trace.jsonl", "position_key": "position_m",
                "minimum_progress_m": 4.0, "minimum_samples": 3,
                "engineering_tolerances_not_legal": True,
                "completion_goal_method": "Four metres of original pedestrian progress is an engineering proxy; audit complete highway crossing against original zero display separately."},
            "case": {"case_id": cid,
                "physical_target": "pedestrian crosses one-way public highway under facing illuminated flashing numeric countdown",
                "recording_description": description}}
        spec = {key: case[key] for key in
            ("case_id", "signal_form", "direction", "completion")}
        spec["source_status"] = "reviewed_original_countdown_packet_required_at_capture"
        controller = {"walker_speed_mps": 1.2,
            "source": "predeclared route tracking on unchanged reviewed original one-way crossing site",
            "physical_acceptance": False}
        write(folder / "config.json", config)
        write(folder / "case-spec.json", spec)
        write(folder / "controller.json", controller)
        files = [{"path": name, "source": str((HERE / name).relative_to(ROOT)),
            "content": (HERE / name).read_text()} for name in MODULES]
        for name, value in (("config.json", config), ("case-spec.json", spec),
                ("controller.json", controller)):
            files.append({"path": name,
                "source": str((folder / name).relative_to(ROOT)),
                "content": json.dumps(value, indent=2, sort_keys=True,
                    ensure_ascii=False) + "\n"})
        files.append({"path": "tests/test_offline.py", "content": OFFLINE_TEST})
        construction = {"law_id": plan["law_id"], "cell_id": plan["cell_id"],
            "actor": plan["actor"], "case_id": cid, "entrypoint": "runner.py",
            "files": files, "recording_description": description,
            "measurement_plan": {"selected_requirement": plan["requirement_dispositions"][2]["requirement"],
                "original_source": "reviewed original 20 Hz signal/countdown and pedestrian crossing readback",
                "saved_method": "source-bound first highway entry, complete crossing and first displayed zero comparison"},
            "mechanisms": ["source-gated one-way highway, crossing and official facing signal selection",
                "same-tick pedestrian, countdown and four-camera capture with world restoration"],
            "static_checks": ["exact law, cell, actor, case, 20 Hz and four cameras",
                "reviewed original source packet required before Native world mutation"],
            "termination_rules": {"duration_s": 45,
                "early_termination": "retain failed capture; never publish it as completed crossing"}}
        digest = write(folder / "construction.json", construction)
        entries.append({"case_id": cid,
            "construction": str((folder / "construction.json").relative_to(HERE)),
            "construction_sha256": digest, "kind": "delivery",
            "measurement_procedure": {"entrypoint": "analysis.py"},
            "fixture_recipe": str((folder / "fixture-recipe.json").relative_to(ROOT)),
            "measurement_contract": str((folder / "measurement-contract.json").relative_to(HERE)),
            "acquisition": {channel["name"]: {"entrypoint": "analysis.py",
                "method": channel["method"],
                "evidence": "channels/" + channel["name"] + ".jsonl"}
                for channel in description["channels"]},
            "candidate_risk": {"status": "none",
                "reason": "The source review fixes signal, crossing and camera poses; a fallback requires new original source qualification, so none is preselected."},
            "candidates": [],
            "native_handoff": {"python_env_var": "CARLA_PYTHON",
                "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"}})
    write(HERE / "execution-manifest.draft.json", {
        "format": "worker-execution-manifest", "assignment_id": HERE.name,
        "status": "reviewed_original_countdown_packet_required_at_capture",
        "runtime_manifest_sha256": hashlib.sha256(
            (ROOT / "runtime/SOURCE-MANIFEST.json").read_bytes()).hexdigest(),
        "cases": entries})
    first = plan["cases"][0]["case_id"].split("__")[-1]
    for name in ("config.json", "construction.json", "case-spec.json", "controller.json"):
        (HERE / name).write_bytes((HERE / "cases" / first / name).read_bytes())
    (HERE / "tests/test_offline.py").write_text(OFFLINE_TEST)
    return entries


if __name__ == "__main__":
    print(len(build()), "countdown bundles")

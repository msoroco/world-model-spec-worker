"""Build exact flashing-yellow-arrow diagnostic bundles for pinned offline proof."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
AID = HERE.name
VARIANTS = (
    "arrow_clear", "arrow_ped_crosswalk", "arrow_ped_intersection",
    "arrow_vehicle_intersection", "arrow_concurrent_movement",
)
SOURCES = (
    "native_arrow.py", "turn_control.py", "aspect_capture.py",
    "event_capture.py", "saved_aspect.py", "saved_finalizer.py",
    "comparison_audit.py", "saved_pair.py", "native_camera_capture.py",
    "saved_camera_audit.py", "analysis.py", "saved_package.py", "delivery_audit.py", "runner.py",
    "native_seal.py",
)
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")

TEST = '''import json
from pathlib import Path
import unittest
from unittest.mock import patch
import runner


class BundleTests(unittest.TestCase):
    def test_exact_arrow_case(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(runner.check(), json.loads((root / "config.json").read_text())["selected_case_id"])

    def test_unsourced_execution_rejected(self):
        with patch("sys.argv", ["runner.py", "--output-dir", "."]):
            with self.assertRaisesRegex(ValueError, "reviewed original C111610 site packet"):
                runner.main()


if __name__ == "__main__":
    unittest.main()
'''


def build():
    source = (HERE / "case-plan.json").read_bytes()
    plan = json.loads(source)
    semantic = json.loads((HERE / "proposals/cases.json").read_text())
    semantic_cases = {row["case_id"]: row for row in semantic["cases"]}
    if len(plan["cases"]) != len(VARIANTS) or {row["case_suffix"] for row in plan["cases"]} != set(VARIANTS):
        raise ValueError("Exact arrow cases changed")
    rows = []
    for item in plan["cases"]:
        case_id, suffix = item["case_id"], item["case_suffix"]
        if case_id != AID + "__" + suffix:
            raise ValueError("Foreign arrow case")
        if case_id not in semantic_cases:
            raise ValueError("Exact arrow case lacks semantic proposal")
        config = {
            "assignment_id": AID, "law_id": "NRS-484B-307-7a", "cell_id": "C111610",
            "actor": "motor_vehicle_driver", "selected_case_id": case_id,
            "case_suffix": suffix, "construction_plan": item["construction"],
            "plan_sha256": hashlib.sha256(source).hexdigest(),
            "rate_hz": 20, "frame_count": 900, "duration_s": 45,
            "cameras": list(CAMERAS),
            "required_sources": ["surveyed_map", "official_head", "external_aspect_readback", "actor_events", "original_camera_media"],
            "required_atoms": [], "diagnostic_only": True,
            "controller_gain": 1.0,
            "physical_completion": {
                "criterion": "travel_progress" if suffix == "arrow_concurrent_movement" else "turn",
                "motion_source": "body_history.jsonl",
                "body_key": "body_vertices_m", "heading_key": "heading_deg",
                "turn_degrees": 90, "turn_tolerance_deg": 30,
                "turn_sign": 1, "minimum_progress_m": 1.0,
                "context_sources": [],
            },
        }
        files = {name: (HERE / name).read_text() for name in SOURCES}
        files.update({"case-plan.json": source.decode(),
                      "config.json": json.dumps(config, indent=2) + "\n",
                      "tests/test_bundle.py": TEST})
        construction = {
            "law_id": config["law_id"], "cell_id": config["cell_id"],
            "actor": config["actor"], "case_id": case_id,
            "entrypoint": "runner.py", "diagnostic_only": True,
            "recording_description": semantic_cases[case_id]["recording_description"],
            "files": [{"path": path, "content": content} for path, content in files.items()],
        }
        output = HERE / ("construction-" + suffix + ".json")
        output.write_text(json.dumps(construction, indent=2) + "\n")
        rows.append({"case_id": case_id, "construction": output.name,
                     "construction_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                     "measurement_contract": "cases/" + suffix + "/measurement-contract.json",
                     "measurement_procedure": {"entrypoint": "analysis.py"},
                     "candidate_risk": item["candidate_risk"]})
    (HERE / "execution-manifest.draft.json").write_text(json.dumps({
        "assignment_id": AID, "status": "diagnostic_offline_only_original_arrow_sources_pending", "cases": rows,
    }, indent=2) + "\n")
    print("built", len(rows), "exact C111610 diagnostic arrow constructions")


if __name__ == "__main__":
    build()

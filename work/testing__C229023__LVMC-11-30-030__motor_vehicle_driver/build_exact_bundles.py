"""Build six exact crosswalk constructions for pinned offline diagnostics.

These bundles retain source and capture code, but are diagnostic until a
reviewed intersection packet and the selected delivery proofs are attached.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from case_construction import CASES
from build_semantic_draft import recording_description
from crosswalk_measurements import ASSIGNMENT_ID

HERE = Path(__file__).resolve().parent
SOURCES = (
    "case_construction.py", "crosswalk_construction.py", "crosswalk_measurements.py",
    "native_crosswalk_capture.py", "native_crosswalk_world.py", "saved_capture_audit.py",
    "native_crosswalk_media.py", "saved_video_audit.py", "saved_crosswalk_finalizer.py",
    "saved_comparison_audit.py", "native_crosswalk_actors.py", "native_crosswalk_session.py",
    "analysis.py",
)
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")

RUNNER = '''"""Exact crosswalk construction entrypoint; unsourced launch is rejected."""
import argparse
import hashlib
import json
from pathlib import Path


def check():
    root = Path(__file__).resolve().parent
    config = json.loads((root / 'config.json').read_text())
    plan_raw = (root / 'case-plan.json').read_bytes()
    if hashlib.sha256(plan_raw).hexdigest() != config['plan_sha256']:
        raise ValueError('Exact crosswalk case plan changed')
    plan = json.loads(plan_raw)
    matches = [row for row in plan['cases'] if row['case_id'] == config['selected_case_id']]
    if len(matches) != 1 or config['assignment_id'] != plan['assignment_id']:
        raise ValueError('Exact crosswalk case missing')
    row = matches[0]
    if (row['crosswalk_kind'] != config['crosswalk_kind'] or
            row['ego_maneuver_request'] != config['ego_behavior'] or
            row['stopped_vehicle_purpose_claim'] != config['lead_stop_purpose']):
        raise ValueError('Exact crossing, behavior or purpose target changed')
    if (config['law_id'] != 'LVMC-11-30-030' or config['cell_id'] != 'C229023' or
            config['actor'] != 'motor_vehicle_driver'):
        raise ValueError('Exact crosswalk law/cell/actor changed')
    if (config['rate_hz'] != 20 or config['frame_count'] != 900 or
            config['duration_s'] != 45 or config['cameras'] !=
            ['overview','approach','reference_corner','driver_reference']):
        raise ValueError('Original capture profile changed')
    return config['selected_case_id']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--site')
    parser.add_argument('--output-dir')
    parser.add_argument('--carla-host', default='127.0.0.1')
    parser.add_argument('--carla-port', type=int, default=2000)
    args = parser.parse_args()
    case = check()
    if args.check:
        print('diagnostic crosswalk bundle passed: ' + case)
        return
    if not args.site or not args.output_dir:
        raise ValueError('Reviewed road intersection site and original output directory required')
    from case_construction import construct
    from native_crosswalk_session import capture_case
    proposal = construct(args.site, case, plan_path=Path(__file__).with_name('case-plan.json'))
    import carla
    client = carla.Client(args.carla_host, args.carla_port)
    client.set_timeout(30.0)
    result = capture_case(world=client.get_world(), carla=carla, proposal=proposal,
                          output=args.output_dir)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
'''

TEST = '''import json
from pathlib import Path
import unittest
from unittest.mock import patch
import runner


class ExactBundleTests(unittest.TestCase):
    def test_selected_case(self):
        root = Path(__file__).resolve().parents[1]
        selected = json.loads((root / 'config.json').read_text())['selected_case_id']
        self.assertEqual(runner.check(), selected)

    def test_unsourced_native_launch_rejected(self):
        with patch('sys.argv', ['runner.py', '--output-dir', '/tmp/not-used']):
            with self.assertRaisesRegex(ValueError, 'Reviewed road intersection site'):
                runner.main()


if __name__ == '__main__':
    unittest.main()
'''


def build() -> list[dict]:
    plan_raw = (HERE / "case-plan.json").read_bytes()
    plan = json.loads(plan_raw)
    expected = {ASSIGNMENT_ID + "__" + suffix for suffix in CASES}
    if {row["case_id"] for row in plan["cases"]} != expected:
        raise ValueError("six exact crosswalk cases required")
    rows = []
    for row in plan["cases"]:
        case_id = row["case_id"]
        suffix = case_id.removeprefix(ASSIGNMENT_ID + "__")
        crossing, behavior, purpose = CASES[suffix]
        if (crossing, behavior, purpose) != (
            row["crosswalk_kind"], row["ego_maneuver_request"],
            row["stopped_vehicle_purpose_claim"],
        ):
            raise ValueError("exact case plan and construction mapping differ")
        config = {
            "assignment_id": ASSIGNMENT_ID, "law_id": "LVMC-11-30-030",
            "cell_id": "C229023", "actor": "motor_vehicle_driver",
            "selected_case_id": case_id,
            "supported_case_ids": sorted(expected),
            "plan_sha256": hashlib.sha256(plan_raw).hexdigest(),
            "crosswalk_kind": crossing, "ego_behavior": behavior,
            "lead_stop_purpose": purpose,
            "rate_hz": 20, "frame_count": 900, "duration_s": 45,
            "cameras": list(CAMERAS), "required_atoms": [],
            "diagnostic_only": True,
        }
        files = {
            "runner.py": RUNNER,
            "case-plan.json": plan_raw.decode("utf-8"),
            "config.json": json.dumps(config, indent=2) + "\n",
            "tests/test_bundle.py": TEST,
        }
        files.update({name: (HERE / name).read_text(encoding="utf-8") for name in SOURCES})
        construction = {
            "law_id": "LVMC-11-30-030", "cell_id": "C229023",
            "actor": "motor_vehicle_driver", "case_id": case_id,
            "entrypoint": "runner.py", "diagnostic_only": True,
            "recording_description": recording_description(),
            "files": [{"path": path, "content": content} for path, content in sorted(files.items())],
        }
        path = HERE / f"construction-{suffix}.json"
        path.write_text(json.dumps(construction, indent=2) + "\n", encoding="utf-8")
        rows.append({
            "case_id": case_id, "construction": path.name,
            "construction_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "candidate_risk": {"status": "physical", "reason": row["physical_risk"]},
        })
    manifest = {
        "assignment_id": ASSIGNMENT_ID,
        "status": "diagnostic_offline_only_source_and_delivery_proofs_pending",
        "cases": rows,
    }
    (HERE / "execution-manifest.draft.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return rows


if __name__ == "__main__":
    print("built", len(build()), "exact diagnostic crosswalk constructions")

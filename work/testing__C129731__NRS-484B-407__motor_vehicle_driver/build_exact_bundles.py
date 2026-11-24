"""Build source-gated exact reversal construction drafts for CPU offline checks."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from native_case_constructor import DISTANCE_TARGETS_FT
from sight_measurement import ASSIGNMENT

HERE = Path(__file__).resolve().parent
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
SOURCES = (
    "carla_sight_adapter.py", "native_case_constructor.py", "native_sight_capture.py",
    "native_sight_cameras.py", "native_camera_audit.py", "reversal_phase.py", "reversal_route_controller.py",
    "sight_measurement.py", "selected_analysis.py",
)

RUNNER = '''"""Source-gated original C129731 reversal acquisition."""
import argparse
import hashlib
import json
import os
from pathlib import Path


def check():
    root = Path(__file__).resolve().parent
    config = json.loads((root / 'config.json').read_text())
    raw = (root / 'case-plan.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != config['plan_sha256']:
        raise ValueError('Exact reversal case plan changed')
    plan = json.loads(raw)
    matching = [row for row in plan['cases'] if row['case_id'] == config['selected_case_id']]
    if len(matching) != 1 or config['assignment_id'] != plan['assignment_id']:
        raise ValueError('Exact reversal case absent')
    if (config['law_id'] != 'NRS-484B-407' or config['cell_id'] != 'C129731' or
            config['actor'] != 'motor_vehicle_driver' or
            config['selected_case_id'] != config['assignment_id'] + '__' + config['suffix']):
        raise ValueError('Exact reversal identity changed')
    from native_case_constructor import DISTANCE_TARGETS_FT
    if (config['target_first_turn_distance_ft'] != DISTANCE_TARGETS_FT[config['suffix']] or
            config['rate_hz'] != 20 or config['frame_count'] != 900 or
            config['duration_s'] != 45 or config['cameras'] !=
            ['overview', 'approach', 'reference_corner', 'driver_reference']):
        raise ValueError('Exact reversal distance or capture profile changed')
    return config['selected_case_id']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--site')
    parser.add_argument('--site-sha256')
    parser.add_argument('--output-dir')
    parser.add_argument('--carla-host', default='127.0.0.1')
    parser.add_argument('--carla-port', type=int, default=2000)
    args = parser.parse_args()
    case = check()
    if args.check:
        print('source-gated reversal bundle passed: ' + case)
        return
    if not args.site or not args.site_sha256 or not args.output_dir:
        raise ValueError('Reviewed original mountain-road site and output required')
    output_root = os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT')
    if not output_root or not Path(args.output_dir).resolve().is_relative_to(Path(output_root).resolve()):
        raise ValueError('Original attempt must be under configured output root')
    from carla_sight_adapter import load_reviewed_site
    load_reviewed_site(Path(args.site), args.site_sha256)
    from carla_sight_adapter import capture_original_carla
    from native_case_constructor import construct_case
    from world_restore import snapshot, restore
    import carla
    client = carla.Client(args.carla_host, args.carla_port)
    client.set_timeout(30.0)
    saved = snapshot(client)
    actors = ()
    try:
        world = client.get_world()
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        def transform(x, y, z, yaw):
            return carla.Transform(carla.Location(x=x, y=y, z=z),
                                   carla.Rotation(yaw=yaw))
        actors = construct_case(world, world.get_blueprint_library(),
                                Path(args.site), args.site_sha256, case, transform)
        result = capture_original_carla(
            world, actors[0], actors[1], Path(args.site), args.site_sha256,
            carla.Location, case, Path(args.output_dir),
            control_factory=carla.VehicleControl)
        print(json.dumps(result, sort_keys=True))
    finally:
        try:
            for actor in reversed(actors):
                actor.destroy()
        finally:
            restore(client, saved)


if __name__ == '__main__':
    main()
'''

TEST = '''import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
import runner


class BundleTests(unittest.TestCase):
    def test_exact_case(self):
        root = Path(__file__).resolve().parents[1]
        expected = json.loads((root/'config.json').read_text())['selected_case_id']
        self.assertEqual(runner.check(), expected)

    def test_unsourced_launch_rejected_before_carla_import(self):
        with patch('sys.argv', ['runner.py', '--output-dir', '/tmp/not-used']):
            with self.assertRaisesRegex(ValueError, 'Reviewed original mountain-road site'):
                runner.main()

    def test_unconfigured_output_root_rejected_before_carla_import(self):
        with patch.dict(os.environ, {'SCENARIO_PIPELINE_OUTPUT_ROOT': ''}):
            with patch('sys.argv', ['runner.py', '--site', 'missing.json',
                                    '--site-sha256', '0'*64, '--output-dir', '/tmp/not-used']):
                with self.assertRaisesRegex(ValueError, 'configured output root'):
                    runner.main()


if __name__ == '__main__':
    unittest.main()
'''


def recording_description() -> dict:
    channels = [
        {"name": name, "unit": "source record", "sampling_rate_hz": 20,
         "method": method, "time_window": "45 s original reversal attempt",
         "reference_frame": "original Native frame and elapsed time",
         "uncertainty": "Physical road geometry, motion and pixels require original review"}
        for name, method in (
            ("ego_motion", "Observed ego heading and turn phase"),
            ("sight_rays", "Nine-point rays from both approach directions to 500 feet"),
            ("frame_join", "Original Native frame and elapsed-time join"),
            ("original_camera_index", "Four frame-joined original RGB views"),
        )]
    return {"channels": channels,
            "context_inputs": [
                {"name": "road_geometry", "unit": "source record",
                 "method": "SHA-bound reviewed mountain-road site and loaded OpenDRIVE"},
                {"name": "case_setup", "unit": "source record",
                 "method": "Exact reviewed spawn, route, camera and distance setup"}],
            "limitations": ["Actual reversal, sight lines, full video and legal visibility remain unverified"]}


def build() -> list[dict]:
    raw = (HERE / "case-plan.json").read_bytes()
    plan = json.loads(raw)
    expected = {ASSIGNMENT + "__" + suffix for suffix in DISTANCE_TARGETS_FT}
    if {row["case_id"] for row in plan["cases"]} != expected:
        raise ValueError("four exact reversal cases required")
    source_files = {name: (HERE / name).read_text() for name in SOURCES}
    source_files["analysis.py"] = source_files["selected_analysis.py"]
    source_files["selected-measurement-contract.json"] = (
        HERE / "selected-measurement-contract.draft.json").read_text()
    source_files["world_restore.py"] = (
        HERE.parents[1] / "runtime/scenario_pipeline/worker_exchange/world_restore.py").read_text()
    rows = []
    for case in plan["cases"]:
        case_id = case["case_id"]
        suffix = case_id.removeprefix(ASSIGNMENT + "__")
        config = {
            "assignment_id": ASSIGNMENT, "law_id": "NRS-484B-407",
            "cell_id": "C129731", "actor": "motor_vehicle_driver",
            "selected_case_id": case_id, "suffix": suffix,
            "target_first_turn_distance_ft": DISTANCE_TARGETS_FT[suffix],
            "plan_sha256": hashlib.sha256(raw).hexdigest(),
            "rate_hz": 20, "frame_count": 900, "duration_s": 45,
            "cameras": list(CAMERAS), "required_atoms": [],
            "diagnostic_only": True,
        }
        files = dict(source_files)
        files.update({"runner.py": RUNNER, "case-plan.json": raw.decode(),
                      "config.json": json.dumps(config, indent=2) + "\n",
                      "tests/test_bundle.py": TEST})
        construction = {
            "law_id": "NRS-484B-407", "cell_id": "C129731",
            "actor": "motor_vehicle_driver", "case_id": case_id,
            "entrypoint": "runner.py", "diagnostic_only": True,
            "recording_description": recording_description(),
            "files": [{"path": path, "content": content}
                      for path, content in sorted(files.items())],
        }
        path = HERE / f"construction-{suffix}.json"
        path.write_text(json.dumps(construction, indent=2) + "\n")
        rows.append({"case_id": case_id, "construction": path.name,
                     "construction_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                     "candidate_risk": case["physical_risk"],
                     "measurement_contract_draft": "selected-measurement-contract.draft.json",
                     "measurement_contract": "selected-measurement-contract.draft.json",
                     "measurement_procedure": {"entrypoint": "analysis.py"},
                     "fixture_recipe_draft": "fixtures/" + suffix + "/fixture-recipe.json",
                     "fixture_recipe": "work/" + ASSIGNMENT + "/fixtures/" + suffix + "/core-fixture-recipe.json",
                     "compatibility_status": "reference_full_core_lean_video_passed_other_cases_pending"})
    manifest = {"format": "worker-execution-manifest",
                "runtime_manifest_sha256": hashlib.sha256(
                    (HERE.parents[1] / "runtime/SOURCE-MANIFEST.json").read_bytes()).hexdigest(),
                "assignment_id": ASSIGNMENT,
                "status": "diagnostic_offline_only_original_source_and_delivery_proofs_pending",
                "cases": rows}
    (HERE / "execution-manifest.draft.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return rows


if __name__ == "__main__":
    print("built", len(build()), "source-gated reversal constructions")

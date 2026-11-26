"""Build eight exact, source-gated C109171 diagnostic constructions."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from native_capture import CAMERAS, DEFAULT_FRAMES, FPS
from saved_measurement import ASSIGNMENT, EXPECTED

HERE = Path(__file__).resolve().parent
SOURCES = ('native_scene.py', 'permission_applicability.py', 'pedestrian_control.py', 'carla_adapter.py',
           'native_capture.py', 'native_runner.py', 'saved_measurement.py', 'saved_process.py',
           'comparison_audit.py', 'delivery_media.py', 'analysis.py',
           'native_output_bridge.py', 'permission_sweep_audit.py')

RECORDING_DESCRIPTION = {
    'channels': [
        {'name': name, 'unit': 'structured',
         'method': 'source-sealed original Native event, walker pose and four-camera frame join',
         'sampling_rate_hz': 20, 'time_window': 'all 900 original world ticks',
         'reference_frame': 'original CARLA world frame',
         'uncertainty': 'actual device visibility and statutory permission remain unverified'}
        for name in ('sampled_highway_entry', 'separate_device_timeline',
                     'official_sole_arrow', 'camera_frame_map')],
    'context_inputs': [
        {'name': 'cited_permission_basis', 'unit': 'structured',
         'method': 'reviewed NRS 484B.283 alternatives and exact governing device source'}],
    'limitations': ['A fixture WALK indication does not establish legal permission or physical visibility.']}

RUNNER = '''"""Exact C109171 diagnostic preflight; reviewed originals required for capture."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from native_capture import CAMERAS, DEFAULT_FRAMES, FPS
from native_output_bridge import publish
from native_runner import run_capture
from analysis import analyze
from saved_measurement import ASSIGNMENT, EXPECTED


def check():
    root = Path(__file__).resolve().parent
    config = json.loads((root / "config.json").read_text(encoding="utf-8"))
    source = (root / "case-plan.json").read_bytes()
    if hashlib.sha256(source).hexdigest() != config["plan_sha256"]:
        raise ValueError("Exact C109171 case plan changed")
    case_id = config["selected_case_id"]
    if not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("Foreign C109171 case")
    suffix = case_id.removeprefix(ASSIGNMENT + "__")
    if suffix not in EXPECTED or config["expected_observations"] != list(EXPECTED[suffix]):
        raise ValueError("Exact C109171 case behavior changed")
    planned = json.loads(source)
    matching = [row for row in planned["cases"] if row["case_id"] == case_id]
    if len(matching) != 1:
        raise ValueError("Exact C109171 case absent from plan")
    parameters = matching[0]["scenario_parameters"]
    if suffix.startswith("permission_applicability-"):
        if config.get("entry_delay_s") != parameters.get("entry_delay_s") or config.get("focus_provision_id") != parameters.get("focus_provision_id"):
            raise ValueError("Cited applicability sweep binding changed")
    if config["fps"] != FPS or config["frame_count"] != DEFAULT_FRAMES:
        raise ValueError("C109171 diagnostic timebase changed")
    if config["cameras"] != list(CAMERAS):
        raise ValueError("C109171 diagnostic camera set changed")
    if config["required_sources"] != ["original_map", "official_arrow_head", "separate_pedestrian_device", "reviewed_permission_applicability", "native_event_trace", "original_camera_png"]:
        raise ValueError("C109171 original source contract changed")
    return case_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    case_id = check()
    if args.check:
        print("diagnostic C109171 case passed: " + case_id)
        return
    operator_path = os.environ.get("SCENARIO_PEDESTRIAN_OPERATOR_MODULE")
    operator_sha = os.environ.get("SCENARIO_PEDESTRIAN_OPERATOR_SHA256")
    if not all((args.output_dir, args.host, args.port, operator_path, operator_sha)):
        raise ValueError("Reviewed original C109171 map, signal, device and camera sources required")
    attempt = Path(args.output_dir).resolve()
    operator = Path(operator_path).resolve()
    if not operator.is_file():
        raise ValueError("Source-bound Native operator missing")
    if hashlib.sha256(operator.read_bytes()).hexdigest() != operator_sha:
        raise ValueError("Source-bound Native operator changed")
    spec = importlib.util.spec_from_file_location("c109171_original_operator", operator)
    if spec is None or spec.loader is None:
        raise ValueError("Source-bound Native operator cannot load")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(30.0)
    world = client.get_world()
    site_ref = module.stage_original_sources(case_id=case_id, attempt=attempt)
    if not isinstance(site_ref, dict) or not site_ref.get("path") or not site_ref.get("sha256"):
        raise ValueError("Operator did not stage a source-hashed original site")
    bindings = module.bind(world=world, case_id=case_id, attempt=attempt, site_ref=site_ref)
    if not isinstance(bindings, dict) or "permission_review_ref" not in bindings:
        raise ValueError("Original Native operator bindings missing")
    result = run_capture(world, attempt=attempt, site_ref=site_ref,
                         case_id=case_id, **bindings)
    (attempt / "pedestrian-source.json").write_text(json.dumps({
        "case_id": case_id, "site_ref": site_ref,
        "permission_review_ref": bindings["permission_review_ref"],
        "events_ref": result["events_ref"], "frame_map_ref": result["frame_map_ref"],
        "diagnostic_fixture": False}, indent=2) + "\\n")
    (attempt / "capture-result.json").write_text(json.dumps(result, indent=2) + "\\n")
    map_bytes = bindings["map_reader"](world)
    seal = publish(attempt, map_bytes=map_bytes, restoration_verified=True)
    analyze(attempt, attempt / "analysis-report.json")
    print("sealed original C109171 capture: " + str(seal))


if __name__ == "__main__":
    main()
'''

TEST = '''import json
from pathlib import Path
import unittest
from unittest.mock import patch
import runner


class BundleTests(unittest.TestCase):
    def test_exact_case_binding(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(runner.check(), json.loads((root / "config.json").read_text())["selected_case_id"])

    def test_unsourced_capture_rejected(self):
        with patch("sys.argv", ["runner.py", "--output-dir", "."]):
            with self.assertRaisesRegex(ValueError, "Reviewed original C109171"):
                runner.main()


if __name__ == "__main__":
    unittest.main()
'''


def build():
    source = (HERE / 'case-plan.json').read_bytes()
    plan = json.loads(source)
    found = {row['case_id'].removeprefix(ASSIGNMENT + '__') for row in plan['cases']
             if row['case_id'].startswith(ASSIGNMENT + '__')}
    if len(plan['cases']) != len(EXPECTED) or found != set(EXPECTED):
        raise ValueError('Exact C109171 case coverage differs from plan')
    proposals = {row['case_id']: row for row in json.loads((HERE / 'proposals/cases.json').read_text())['cases']}
    rows = []
    for item in plan['cases']:
        case_id = item['case_id']
        suffix = case_id.removeprefix(ASSIGNMENT + '__')
        recording_description = proposals[case_id]['recording_description']
        config = {'assignment_id': ASSIGNMENT, 'law_id': 'NRS-484B-307-4b',
                  'cell_id': 'C109171', 'actor': 'pedestrian', 'selected_case_id': case_id,
                  'expected_observations': list(EXPECTED[suffix]),
                  'plan_sha256': hashlib.sha256(source).hexdigest(),
                  'fps': FPS, 'frame_count': DEFAULT_FRAMES,
                  'cameras': list(CAMERAS), 'diagnostic_only': True,
                  'required_sources': ['original_map', 'official_arrow_head',
                                       'separate_pedestrian_device', 'reviewed_permission_applicability',
                                       'native_event_trace',
                                       'original_camera_png'], 'required_atoms': [],
                  'case': {'case_id': case_id,
                           'recording_description': recording_description}}
        if 'entry_delay_s' in item['scenario_parameters']:
            config['entry_delay_s'] = item['scenario_parameters']['entry_delay_s']
            config['focus_provision_id'] = item['scenario_parameters']['focus_provision_id']
        files = {name: (HERE / name).read_text(encoding='utf-8') for name in SOURCES}
        files.update({'runner.py': RUNNER, 'case-plan.json': source.decode('utf-8'),
                      'config.json': json.dumps(config, indent=2) + '\n',
                      'tests/test_bundle.py': TEST})
        construction = {'law_id': config['law_id'], 'cell_id': config['cell_id'],
                        'actor': config['actor'], 'case_id': case_id,
                        'entrypoint': 'runner.py', 'diagnostic_only': True,
                        'recording_description': recording_description,
                        'files': [{'path': name, 'content': content}
                                  for name, content in files.items()]}
        path = HERE / ('construction-' + suffix + '.json')
        path.write_text(json.dumps(construction, indent=2) + '\n', encoding='utf-8')
        rows.append({'case_id': case_id, 'construction': path.name,
                     'construction_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                     'candidate_risk': item['physical_risk_assessment']})
    (HERE / 'execution-manifest.draft.json').write_text(json.dumps({
        'assignment_id': ASSIGNMENT, 'status': 'diagnostic_original_sources_pending',
        'cases': rows}, indent=2) + '\n', encoding='utf-8')
    print('built', len(rows), 'exact C109171 diagnostic constructions')


if __name__ == '__main__':
    build()

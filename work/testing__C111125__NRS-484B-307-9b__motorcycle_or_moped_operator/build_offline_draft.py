"""Build exact C111125 diagnostic bundles from the source-bound case plan."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
SOURCES = ('signal_exception.py', 'original_capture.py', 'native_session.py', 'camera_capture.py', 'saved_measurement.py',
           'comparison_audit.py', 'prove_comparison.py', 'delivery_audit.py', 'media_decode.py',
           'operator_native_adapter.py', 'analysis.py')


def recording_description():
    channels = [
        ('motorcycle subtype and live actor identity', 'Native actor/blueprint readback'),
        ('official composite red and turn-arrow aspect', 'reviewed Native head observer'),
        ('source-ranked stop reference and ego front station', 'source survey and Native body vertices'),
        ('complete aspect-return cycle frame bounds', '20 Hz original head history'),
        ('malfunction or failed-detection causal record', 'original detector or device fault source'),
        ('crosswalk pedestrian and lawful traffic tracks', '20 Hz original participant readback'),
        ('four synchronized original camera views', 'four Native RGB camera sensors'),
    ]
    return {
        'channels': [{'name': name, 'unit': 'source observation', 'sampling_rate_hz': 20,
                      'method': method, 'time_window': 'original 45-second episode',
                      'reference_frame': 'same original Native frame and simulation time',
                      'uncertainty': 'Physical visibility, device authority and participant lawfulness await independent original-source review'}
                     for name, method in channels],
        'context_inputs': [{'name': 'reviewed map, route, head, stop hierarchy, causal device and participant authority',
                            'unit': 'source record', 'method': 'SHA-256-sealed original site packet and Native readback'}],
        'limitations': ['A fixed straight cell does not exercise the opposite-arrow turn branch.',
                        'Unchanged signal state alone does not establish malfunction or failed detection.',
                        'Diagnostic CPU fixtures do not establish physical camera visibility or lawful status.']}

RUNNER = '''"""C111125 exact diagnostic preflight; unsourced Native launch is refused."""
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path


def check():
    root = Path(__file__).resolve().parent
    config = json.loads((root / "config.json").read_text(encoding="utf-8"))
    source = (root / "case-plan.json").read_bytes()
    if hashlib.sha256(source).hexdigest() != config["plan_sha256"]:
        raise ValueError("C111125 exact case plan changed")
    case_id = config["selected_case_id"]
    if not case_id.startswith(config["assignment_id"] + "__"):
        raise ValueError("C111125 foreign exact case")
    matches = [row for row in json.loads(source)["cases"] if row["case_id"] == case_id]
    if len(matches) != 1 or matches[0]["scenario_parameters"] != config["case_parameters"]:
        raise ValueError("C111125 exact case construction changed")
    if config["fps"] != 20 or config["frame_count"] != 900 or config["duration_s"] != 45:
        raise ValueError("C111125 original timebase changed")
    if config["cameras"] != ["overview", "approach", "reference_corner", "driver_reference"]:
        raise ValueError("C111125 pinned camera profile changed")
    if config["required_sources"] != ["loaded_map", "official_composite_head", "stopping_reference", "causal_detector_or_malfunction", "participant_tracks", "original_camera_media"]:
        raise ValueError("C111125 required originals changed")
    return case_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--site-packet", default=os.environ.get("SCENARIO_SITE_PACKET"))
    parser.add_argument("--native-adapter", default=os.environ.get("SCENARIO_NATIVE_ADAPTER"))
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    case_id = check()
    if args.check:
        print("diagnostic C111125 case passed: " + case_id)
        return
    if not args.output_dir or not args.site_packet or not args.native_adapter:
        raise ValueError("Reviewed original C111125 map, composite head, detector and camera sources required")
    adapter = importlib.import_module(args.native_adapter)
    if not hasattr(adapter, "open_session"):
        raise ValueError("Operator-owned Native adapter lacks open_session")
    from native_session import capture_events
    try:
        with adapter.open_session(case_id, args.site_packet, args.host, args.port) as session:
            capture_events(session, args.site_packet, case_id, args.output_dir)
        if not session.restoration_verified:
            raise ValueError("Original Native sensor/world restoration unverified")
        from worker_exchange.native_output import seal_capture
        seal_capture(args.output_dir, frames=900,
                     restoration={"restored": True, "scope": "operator adapter closed four sensors and verified unchanged world settings"},
                     errors=[])
    except Exception as error:
        Path(args.output_dir, "native-run-status.json").write_text(json.dumps({
            "errors": [str(error)], "case_id": case_id, "capture_sealed": False}, indent=2) + "\\n")
        raise


if __name__ == "__main__":
    main()
'''

TEST = '''import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import MagicMock, patch
import runner


class BundleTests(unittest.TestCase):
    def test_exact_case_binding(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(runner.check(), json.loads((root / "config.json").read_text())["selected_case_id"])

    def test_unsourced_capture_rejected(self):
        with patch("sys.argv", ["runner.py", "--output-dir", "."]):
            with self.assertRaisesRegex(ValueError, "Reviewed original C111125"):
                runner.main()

    def test_pinned_capture_dispatch_to_operator_session(self):
        case_id = runner.check()
        session = types.SimpleNamespace(restoration_verified=True)
        context = MagicMock()
        context.__enter__.return_value = session
        adapter = types.SimpleNamespace(open_session=MagicMock(return_value=context))
        exchange = types.ModuleType("worker_exchange")
        output = types.ModuleType("worker_exchange.native_output")
        output.seal_capture = MagicMock()
        env = {"SCENARIO_SITE_PACKET": "/reviewed/site.json", "SCENARIO_NATIVE_ADAPTER": "test_native_adapter"}
        args = ["runner.py", "--output-dir", "/materialized/attempt",
                "--host", "localhost", "--port", "2000"]
        with patch.dict("os.environ", env), patch.dict(sys.modules, {"test_native_adapter": adapter,
                "worker_exchange": exchange, "worker_exchange.native_output": output}), \\
                patch("native_session.capture_events") as capture, patch("sys.argv", args):
            runner.main()
        adapter.open_session.assert_called_once_with(case_id, "/reviewed/site.json", "localhost", 2000)
        capture.assert_called_once_with(session, "/reviewed/site.json", case_id, "/materialized/attempt")
        output.seal_capture.assert_called_once()


if __name__ == "__main__":
    unittest.main()
'''


def build():
    source = (HERE / 'case-plan.json').read_bytes()
    plan = json.loads(source)
    cases = plan['cases']
    if len(cases) != 7 or len({row['case_id'] for row in cases}) != 7:
        raise ValueError('Seven distinct C111125 exact cases required')
    output_rows = []
    for row in cases:
        case_id = row['case_id']
        if not case_id.startswith(AID + '__'):
            raise ValueError('Foreign C111125 exact case')
        suffix = case_id.removeprefix(AID + '__')
        config = {'assignment_id': AID, 'law_id': 'NRS-484B-307-9b',
                  'cell_id': 'C111125', 'actor': 'motorcycle_or_moped_operator',
                  'selected_case_id': case_id,
                  'case_parameters': row['scenario_parameters'],
                  'case': {'case_id': case_id,
                           'recording_description': recording_description()},
                  'plan_sha256': hashlib.sha256(source).hexdigest(),
                  'fps': 20, 'frame_count': 900, 'duration_s': 45,
                  'cameras': ['overview', 'approach', 'reference_corner',
                              'driver_reference'], 'required_atoms': [],
                  'required_sources': ['loaded_map', 'official_composite_head',
                                       'stopping_reference', 'causal_detector_or_malfunction',
                                       'participant_tracks', 'original_camera_media'],
                  'diagnostic_only': True}
        files = {name: (HERE / name).read_text(encoding='utf-8') for name in SOURCES}
        files.update({'runner.py': RUNNER, 'case-plan.json': source.decode('utf-8'),
                      'config.json': json.dumps(config, indent=2) + '\n',
                      'tests/test_bundle.py': TEST})
        construction = {'law_id': config['law_id'], 'cell_id': config['cell_id'],
                        'actor': config['actor'], 'case_id': case_id,
                        'entrypoint': 'runner.py', 'diagnostic_only': True,
                        'recording_description': recording_description(),
                        'files': [{'path': name, 'content': content}
                                  for name, content in files.items()]}
        path = HERE / ('construction-' + suffix + '.json')
        path.write_text(json.dumps(construction, indent=2) + '\n', encoding='utf-8')
        output_rows.append({'case_id': case_id, 'construction': path.name,
                            'construction_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                            'candidate_risk': row['physical_risk_assessment']})
    (HERE / 'execution-manifest.draft.json').write_text(json.dumps({
        'assignment_id': AID, 'status': 'diagnostic_original_sources_pending',
        'cases': output_rows}, indent=2) + '\n', encoding='utf-8')
    print('built', len(output_rows), 'exact C111125 diagnostic constructions')


if __name__ == '__main__':
    build()

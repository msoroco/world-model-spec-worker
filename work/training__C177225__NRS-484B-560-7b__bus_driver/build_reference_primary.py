"""Deterministically package the current reference primary for pinned offline checks.

This draft has an unverified generic prop as a rail visual proxy. It is not a
delivery-ready physical crossing construction or compatibility receipt.
"""
import hashlib
import json
from pathlib import Path

from native_scene import VIEWS
from native_runner import ASSIGNMENT, FRAMES, RATE_HZ


ROOT = Path(__file__).resolve().parent
CONSTRUCTION = ROOT / 'constructions' / 'reference-primary.json'
MANIFEST = ROOT / 'execution-manifest.json'
SOURCE_FILES = ('native_runner.py', 'camera_recorder.py', 'measure_direction.py',
                'native_scene.py', 'officer_direction.py', 'officer_pose.py',
                'rail_road.py', 'finalize_direction.py')
CASE_ID = ASSIGNMENT + '__reference'


def encode(value):
    return json.dumps(value, indent=2, sort_keys=True) + '\n'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def make():
    config = {
        'case_id': CASE_ID, 'selected_case_id': CASE_ID,
        'case_suffix': 'reference', 'direction': 1,
        'law_id': 'NRS-484B-560-7b', 'cell_id': 'C177225',
        'actor': 'bus_driver', 'rate_hz': RATE_HZ,
        'duration_s': FRAMES / RATE_HZ, 'frames': FRAMES,
        'cameras': list(VIEWS),
        'rail_asset_blueprint': 'static.prop.ironplank',
        'rail_asset_scope': 'generic visual proxy; railroad crossing not physically verified',
        'required_atoms': [], 'source_packets': [], 'weather': 'ClearNoon',
        'authored_test_context': {'core_assumptions': [
            'Named officer role and authorization are authored scenario assumptions.',
            'Installed prop shape, driver comprehension and crossing status are unverified.']},
        'comparison_variable': 'bus_obeys_officer_direction',
        'comparison_requested_value': True,
        'physical_acceptance_claimed': False, 'legal_verdict': None,
    }
    test = '''import json\nimport unittest\nfrom pathlib import Path\nfrom runner import check\nfrom rail_road import validate_authored_road\nfrom officer_direction import Crossing\n\nclass BundleTest(unittest.TestCase):\n    def test_exact_materialized_reference(self):\n        config=json.loads(Path('config.json').read_text())\n        result=check(config['case_suffix'],config['direction'],config)\n        self.assertEqual(config['case_id'],result['case_id'])\n        self.assertEqual([-1,1],validate_authored_road()['driving_lane_ids'])\n        self.assertLess(Crossing().stop_station(1),Crossing().exit_station(1))\n        self.assertFalse(result['physical_success_claimed'])\n'''
    files = [{'path': 'runner.py', 'content': (ROOT / 'native_runner.py').read_text()}]
    files.extend({'path': name, 'content': (ROOT / name).read_text()}
                 for name in SOURCE_FILES if name != 'native_runner.py')
    files.extend([{'path': 'tests/test_bundle.py', 'content': test},
                  {'path': 'config.json', 'content': encode(config)}])
    construction = {
        'case_id': CASE_ID, 'cell_id': 'C177225',
        'law_id': 'NRS-484B-560-7b', 'actor': 'bus_driver',
        'entrypoint': 'runner.py', 'files': files,
        'recording_description': {
            'rate_hz': RATE_HZ, 'duration_s': FRAMES / RATE_HZ,
            'source_cameras': list(VIEWS),
            'raw_sources': ['bus_native_rows.jsonl', 'officer_signal_rows.jsonl',
                            'video_frames.jsonl', 'capture/manifest.json']},
        'mechanisms': ['authored two-way road', 'bus', 'officer arm pose',
                       'four RGB cameras', 'generic rail visual proxy pending physical review'],
        'termination_rules': {'planned_frames': FRAMES,
                              'early_failure': 'source, actor, frame, or world restoration error'},
        'status': 'selected_cpu_preparation_incomplete',
    }
    CONSTRUCTION.parent.mkdir(parents=True, exist_ok=True)
    CONSTRUCTION.write_text(encode(construction))
    runtime_manifest = ROOT.parents[1] / 'runtime' / 'pipeline' / 'SOURCE-MANIFEST.json'
    manifest = {
        'format': 'worker-execution-manifest',
        'assignment_id': ASSIGNMENT,
        'runtime_manifest_sha256': sha(runtime_manifest),
        'status': 'selected_cpu_preparation_incomplete',
        'cases': [{'case_id': CASE_ID, 'kind': 'delivery',
                   'candidate_risk': {'status': 'physical',
                                      'reason': 'Generic rail proxy and officer visibility require original Native review'},
                   'construction': str(CONSTRUCTION.relative_to(ROOT)),
                   'construction_sha256': sha(CONSTRUCTION),
                   'candidates': []}],
    }
    MANIFEST.write_text(encode(manifest))
    return manifest


if __name__ == '__main__':
    print(json.dumps(make()))

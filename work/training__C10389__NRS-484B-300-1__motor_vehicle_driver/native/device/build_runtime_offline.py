"""Pin eight exact C10389 candidates to the existing offline runtime."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.parent.parent
NAMES = ('assignment-source.json', 'case-plan.json', 'alley-stop.xodr',
         'config.json', 'requested-tracks.jsonl', 'build.py', 'check.py',
         'capture.py', 'measurement-contract.json', 'saved.py',
         'fixture_raw.py', 'route_fallbacks.py')

TEST = '''import tempfile
import unittest
from pathlib import Path
from check import check
from fixture_raw import build as fixture
from saved import prepare, measure
from route_fallbacks import route

class ExactDevice(unittest.TestCase):
    def test_exact_source_and_unverified_authority(self):
        result = check(Path.cwd())
        self.assertFalse(result['official_placement_verified'])
        self.assertFalse(result['delivery_ready'])
        self.assertIsNone(result['observed_device_obedience'])

    def test_distinct_stop_request(self):
        result = check(Path.cwd())
        if result['candidate_id'] == 'fallback3':
            self.assertFalse(result['requested_crossing'])
            self.assertGreater(result['requested_stopped_frames'], 0)
        else:
            self.assertTrue(result['requested_crossing'])
            self.assertEqual(result['requested_stopped_frames'],
                             20 if result['requested_obey'] else 0)

    def test_synthetic_raw_to_saved_and_routing(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            fixture(Path.cwd(), root/'raw')
            receipt = prepare(Path.cwd(), root/'raw', root/'saved', True)
            measured = measure(Path.cwd(), root/'saved')
            routed = route(Path.cwd(), root/'saved')
            self.assertEqual(receipt['source_kind'], 'synthetic_cpu')
            self.assertFalse(measured['authored_signal_is_official_placement'])
            self.assertFalse(measured['delivery_ready'])
            self.assertIsNone(routed['selected_fallback'])
'''


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    cases = []
    for suffix in ('probe_1', 'probe_2'):
        choices = []
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            bundle = HERE / 'offline' / 'bundles' / suffix / candidate
            files = [{'path': name, 'content': (bundle / name).read_text()}
                     for name in NAMES]
            files.append({'path': 'tests/test_exact.py', 'content': TEST})
            construction = {'case_id': CASE.name + '__' + suffix,
                'cell_id': 'C10389', 'law_id': 'NRS-484B-300-1',
                'actor': 'motor_vehicle_driver', 'entrypoint': 'capture.py',
                'files': files, 'status': 'unselected_cpu_diagnostic',
                'recording_description': 'Authored alley stop-device pair; official placement, original stopping and police-direction review unverified.'}
            path = HERE / 'runtime-drafts' / suffix / candidate / 'construction.json'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(construction, indent=2, allow_nan=False) + '\n')
            choices.append({'id': candidate,
                            'construction': str(path.relative_to(HERE)),
                            'construction_sha256': sha(path)})
        cases.append({'case_id': CASE.name + '__' + suffix,
            'construction': choices[0]['construction'],
            'construction_sha256': choices[0]['construction_sha256'],
            'candidates': choices[1:],
            'candidate_risk': {'status': 'physical',
                'reason': 'Original Native device, official placement, stop/body and legal evidence absent.'}})
    manifest = {'format': 'worker-unselected-draft-construction-manifest-v1',
        'assignment_id': CASE.name, 'status': 'draft_not_selected',
        'cases': cases, 'original_native_observed': False,
        'delivery_ready': False}
    (HERE / 'draft-execution-manifest.json').write_text(
        json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    result = build()
    print(json.dumps({'cases': len(result['cases']), 'constructions': 8}))

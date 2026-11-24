"""Build five exact diagnostic bundles without inventing a reviewed Native site."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name
SOURCES = ('runner.py', 'native_crossing.py', 'pedestrian_control.py',
           'native_capture.py', 'saved_measurement.py', 'saved_media_audit.py',
           'delivery_audit.py', 'comparison_audit.py')
CAMERAS = [('overview', 1920, 1080), ('approach', 1280, 720),
           ('reference_corner', 1280, 720), ('driver_reference', 1280, 720)]
TEST_SOURCE = '''import json
import unittest
from pathlib import Path
from runner import check

class MaterializedBundleTest(unittest.TestCase):
    def test_exact_diagnostic_identity_and_contract(self):
        root = Path(__file__).resolve().parents[1]
        scene = check(root)
        self.assertEqual(json.loads((root / "config.json").read_text())["case"], scene)
        self.assertTrue(scene["diagnostic_only"])
'''


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def build():
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    cases = plan['cases']
    if len(cases) != 5 or len({case['case_id'] for case in cases}) != 5:
        raise ValueError('five distinct exact cases required')
    manifest = {'format': 'worker-diagnostic-case-index', 'assignment_id': ASSIGNMENT,
                'diagnostic_only': True, 'cases': []}
    for case in cases:
        suffix = case['case_id'].removeprefix(ASSIGNMENT + '__')
        if suffix not in {'marked_cross', 'unmarked_cross', 'other_device_stop',
                          'other_device_cross', 'outside_cross'}:
            raise ValueError('unknown exact pedestrian case')
        scene = {'case_id': case['case_id'], 'case_suffix': suffix,
                 'law_id': plan['law_id'], 'cell_id': plan['cell_id'],
                 'actor': plan['actor'], 'diagnostic_only': True,
                 'source_status': 'reviewed Native site missing',
                 'requested_crossing': suffix != 'other_device_stop',
                 'scenario_parameters': case['scenario_parameters']}
        config = {'law_id': plan['law_id'], 'cell_id': plan['cell_id'],
                  'actor': plan['actor'], 'selected_case_id': case['case_id'],
                  'supported_case_ids': [item['case_id'] for item in cases],
                  'case': scene, 'rate_hz': 20, 'duration_s': 45,
                  'required_atoms': [], 'source_packets': [],
                  'cameras': [{'name': name, 'width': width, 'height': height,
                               'pose_strategy': 'reviewed original site required'}
                              for name, width, height in CAMERAS]}
        files = [{'path': name, 'content': (ROOT / name).read_text()} for name in SOURCES]
        files += [{'path': 'scene.json', 'content': json.dumps(scene, indent=2) + '\n'},
                  {'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'},
                  {'path': 'tests/test_bundle.py', 'content': TEST_SOURCE}]
        construction = {'law_id': plan['law_id'], 'cell_id': plan['cell_id'],
                        'actor': plan['actor'], 'case_id': case['case_id'],
                        'diagnostic_only': True, 'entrypoint': 'runner.py',
                        'files': files,
                        'mechanisms': ['source-bound Native walker and four-camera capture components; reviewed site absent'],
                        'measurement_plan': ['original frame, signal, device, crosswalk and camera source joins'],
                        'static_checks': ['exact diagnostic identity and capture contract'],
                        'termination_rules': ['no Native dispatch before reviewed site binding']}
        rel = Path('cases') / suffix / 'construction.json'
        write(ROOT / rel, construction)
        manifest['cases'].append({'case_id': case['case_id'], 'kind': 'diagnostic',
                                  'construction': str(rel),
                                  'construction_sha256': sha(ROOT / rel),
                                  'candidate_risk': {'status': 'physical',
                                      'reason': case['physical_risk_assessment']['risk']},
                                  'candidates': []})
    write(ROOT / 'diagnostic-manifest.json', manifest)
    return manifest


if __name__ == '__main__':
    print(json.dumps({'cases': len(build()['cases']), 'diagnostic_only': True}))

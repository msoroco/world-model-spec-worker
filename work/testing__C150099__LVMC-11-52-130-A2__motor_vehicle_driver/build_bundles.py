"""Build source-hashed exact-case diagnostic bundles for the pinned offline CLI."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fire_lane import CASES

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = ROOT.name


def write(path: Path, value: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def camera(name: str, width: int, height: int, purpose: str) -> dict:
    return {'name': name, 'width': width, 'height': height, 'fov_deg': 75,
            'pose_strategy': purpose}


CAMERAS = [camera('overview', 1920, 1080, 'whole curb, posted extent and traffic'),
           camera('approach', 1280, 720, 'one-way ego approach'),
           camera('reference_corner', 1280, 720, 'physical sign and curb boundary'),
           camera('driver_reference', 1280, 720, 'driver view toward posted sign')]

CHANNELS = [
    {'name': name, 'method': method, 'unit': unit,
     'reference_frame': 'source-sealed original Native frame map',
     'sampling_rate_hz': 20, 'time_window': 'full 45-second episode',
     'uncertainty': 'original physical realization and law require independent review'}
    for name, method, unit in (
        ('designation_and_posting', 'reviewed City Fire Code and sign sources', 'source record'),
        ('curb_adjacency', 'original body footprint against reviewed posted interval', 'metres'),
        ('activity', 'original speed and purpose/phase source', 'source record'),
        ('attendance', 'original occupant/driver source', 'source record'),
        ('property_status', 'reviewed public or private parcel source', 'source record'),
        ('necessity_exceptions', 'original traffic, police or device direction source', 'source record'),
    )]

RECORDING = {
    'channels': CHANNELS,
    'context_inputs': [{'name': 'reviewed_fire_lane_packet',
                        'method': 'byte-hashed City designation, posting, parcel, curb and map records',
                        'unit': 'source record'}],
    'limitations': ['Diagnostic offline construction is not City designation evidence.',
                    'Physical sign pixels, activity and statutory exception remain unconfirmed.'],
}

TEST = '''import json
import unittest
from pathlib import Path
from runner import check

class BundleTests(unittest.TestCase):
    def test_exact_case_and_four_cameras(self):
        root = Path(__file__).resolve().parents[1]
        case_id = check(root)
        config = json.loads((root / 'config.json').read_text())
        self.assertEqual(config['selected_case_id'], case_id)
        self.assertEqual(len(config['cameras']), 4)
        self.assertEqual(config['frame_count'], 900)

if __name__ == '__main__':
    unittest.main()
'''


def build() -> dict:
    plan_bytes = (ROOT / 'case-plan.json').read_bytes()
    plan_sha = hashlib.sha256(plan_bytes).hexdigest()
    plan = json.loads(plan_bytes)
    expected = {row['case_id'] for row in plan['cases']}
    entries = []
    for case in CASES:
        case_id = ASSIGNMENT + '__' + case.id
        if case_id not in expected:
            raise ValueError('planned exact fire-lane case missing: ' + case_id)
        config = {
            'assignment_id': ASSIGNMENT, 'law_id': plan['law_id'],
            'cell_id': plan['cell_id'], 'actor': plan['actor'],
            'selected_case_id': case_id, 'supported_case_ids': sorted(expected),
            'case': vars(case), 'plan_sha256': plan_sha,
            'rate_hz': 20, 'frame_count': 900, 'duration_s': 45,
            'cameras': CAMERAS, 'required_atoms': [], 'source_packets': [],
            'diagnostic_only': True, 'recording_description': RECORDING,
        }
        config_text = json.dumps(config, indent=2, sort_keys=True) + '\n'
        files = [{'path': 'config.json', 'content': config_text},
                 {'path': 'case-plan.json', 'content': plan_bytes.decode(),
                  'source': f'work/{ASSIGNMENT}/case-plan.json'},
                 {'path': 'tests/test_bundle.py', 'content': TEST}]
        for name in ('runner.py', 'fire_lane.py', 'source_packet.py',
                     'native_capture.py', 'saved_audit.py', 'comparison_audit.py'):
            files.append({'path': name, 'content': (ROOT / name).read_text(),
                          'source': f'work/{ASSIGNMENT}/{name}'})
        construction = {
            'case_id': case_id, 'cell_id': plan['cell_id'],
            'law_id': plan['law_id'], 'actor': plan['actor'],
            'candidate_id': 'primary', 'entrypoint': 'runner.py',
            'files': files,
            'measurement_plan': {'case_id': case_id, 'original_frames': 900,
                                 'procedure': 'saved_audit.py',
                                 'legal_judgment': 'unresolved',
                                 'source_packets': ['reviewed_fire_lane_packet',
                                                    'frame_map', 'history', 'four_camera_png']},
            'recording_description': RECORDING,
            'static_checks': ['exact law/cell/case identity',
                              'source-hashed original City designation and posting',
                              'four-profile camera joins and 20 Hz history'],
            'termination_rules': ['900 original frames at 20 Hz',
                                  'fail closed on absent site, sign or Native source'],
            'mechanisms': ['reviewed site packet', 'one-way curb approach and sign readback',
                           'four camera original PNG capture',
                           'original-history measurement and comparison audit'],
        }
        rel = f'cases/{case.id}/construction.json'
        digest = write(ROOT / rel, construction)
        (ROOT / f'cases/{case.id}/config.json').write_text(config_text)
        entries.append({
            'case_id': case_id, 'kind': 'delivery', 'construction': rel,
            'construction_sha256': digest,
            'candidate_risk': {'status': 'physical',
                'reason': 'Sign or curb target may not be present or visible in loaded map; '
                          'source review and physical attempt are required.'},
            'candidates': [], 'diagnostic_only': True,
            'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                               'host_env_var': 'CARLA_HOST',
                               'port_env_var': 'CARLA_PORT'},
        })
    if len(entries) != len(expected):
        raise ValueError('case-plan and diagnostic bundle coverage differ')
    first = json.loads((ROOT / entries[0]['construction']).read_text())
    write(ROOT / 'construction.json', first)
    (ROOT / 'config.json').write_text(next(item['content'] for item in first['files']
                                           if item['path'] == 'config.json'))
    runtime_sha = hashlib.sha256((REPO / 'runtime/SOURCE-MANIFEST.json').read_bytes()).hexdigest()
    manifest = {'format': 'worker-execution-manifest',
                'assignment_id': ASSIGNMENT,
                'runtime_manifest_sha256': runtime_sha,
                'diagnostic_only': True, 'cases': entries}
    write(ROOT / 'execution-manifest.json', manifest)
    return manifest


if __name__ == '__main__':
    manifest = build()
    print('built exact diagnostic constructions:', len(manifest['cases']))

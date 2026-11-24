"""Build five exact timing-probe diagnostic constructions."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
SUFFIXES = ('precedence', 'advance', 'timing_below', 'timing_inside', 'timing_above')
CAMERAS = ('front', 'rear', 'left', 'right')

RUNNER = '''"""Exact median-crossing timing diagnostic bundle."""
import argparse
import hashlib
import json
from pathlib import Path


def check():
    root = Path(__file__).resolve().parent
    config = json.loads((root / 'config.json').read_text())
    raw = (root / 'case-plan.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != config['plan_sha256']:
        raise ValueError('Exact timing case plan changed')
    plan = json.loads(raw)
    selected = [row for row in plan['cases'] if row['case_id'] == config['selected_case_id']]
    if len(selected) != 1 or not config['selected_case_id'].startswith(config['assignment_id']+'__'):
        raise ValueError('Exact timing case missing')
    if (config['requested_ego_response'] != selected[0]['requested_ego_response'] or
            config['requested_entry_difference_s'] != selected[0]['requested_entry_difference_s']):
        raise ValueError('Timing or response construction target changed')
    if (config['law_id'] != 'NRS-484B-250-2' or config['cell_id'] != 'C125751' or
            config['crossing_kind'] != 'median_opening_roadway_crossing' or
            config['governing_device'] != 'official_traffic_light'):
        raise ValueError('Crossing/device context changed')
    if (config['rate_hz'] != 20 or config['frame_count'] != 900 or
            config['duration_s'] != 45 or config['cameras'] != ['front','rear','left','right']):
        raise ValueError('Original timing/camera source contract changed')
    return config['selected_case_id']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    args = parser.parse_args()
    case = check()
    if args.check:
        print('diagnostic entry-timing bundle passed: '+case)
        return
    raise ValueError('Reviewed original crossing, governing device and actor sources required')


if __name__ == '__main__':
    main()
'''

TEST = '''import json
from pathlib import Path
import unittest
from unittest.mock import patch
import runner


class BundleTests(unittest.TestCase):
    def test_exact_case(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(runner.check(), json.loads((root/'config.json').read_text())['selected_case_id'])

    def test_unsourced_launch_rejected(self):
        with patch('sys.argv', ['runner.py','--output-dir','.']):
            with self.assertRaisesRegex(ValueError, 'Reviewed original crossing'):
                runner.main()


if __name__ == '__main__':
    unittest.main()
'''


def build():
    raw = (HERE/'case-plan.json').read_bytes()
    plan = json.loads(raw)
    if {row['case_id'] for row in plan['cases']} != {AID+'__'+s for s in SUFFIXES}:
        raise ValueError('five exact timing cases required')
    semantic = json.loads((HERE/'proposals/cases.json').read_text())
    descriptions = {row['case_id']:row['recording_description'] for row in semantic['cases']}
    if set(descriptions) != {AID+'__baseline'} | {row['case_id'] for row in plan['cases']}:
        raise ValueError('canonical semantic cases differ from exact timing cases')
    rows = []
    for item in plan['cases']:
        case = item['case_id']
        config = {'assignment_id': AID, 'law_id': 'NRS-484B-250-2',
                  'cell_id': 'C125751', 'actor': 'motor_vehicle_driver',
                  'selected_case_id': case, 'plan_sha256': hashlib.sha256(raw).hexdigest(),
                  'crossing_kind': 'median_opening_roadway_crossing',
                  'governing_device': 'official_traffic_light',
                  'requested_ego_response': item['requested_ego_response'],
                  'requested_entry_difference_s': item['requested_entry_difference_s'],
                  'rate_hz': 20, 'frame_count': 900, 'duration_s': 45,
                  'cameras': list(CAMERAS), 'required_atoms': [],
                  'diagnostic_only': True}
        files = {'runner.py': RUNNER, 'entry_timing.py': (HERE/'entry_timing.py').read_text(),
                 'analysis.py': (HERE/'analysis.py').read_text(),
                 'native_capture.py': (HERE/'native_capture.py').read_text(),
                 'saved_delivery.py': (HERE/'saved_delivery.py').read_text(),
                 'saved_finalizer.py': (HERE/'saved_finalizer.py').read_text(),
                 'delivery_audit.py': (HERE/'delivery_audit.py').read_text(),
                 'comparison_audit.py': (HERE/'comparison_audit.py').read_text(),
                 'carla_native_adapter.py': (HERE/'carla_native_adapter.py').read_text(),
                 'runtime_source_bridge.py': (HERE/'runtime_source_bridge.py').read_text(),
                 'case-plan.json': raw.decode(), 'config.json': json.dumps(config,indent=2)+'\n',
                 'tests/test_bundle.py': TEST}
        construction = {'law_id': config['law_id'], 'cell_id': config['cell_id'],
                        'actor': config['actor'], 'case_id': case,
                        'entrypoint': 'runner.py', 'diagnostic_only': True,
                        'recording_description': descriptions[case],
                        'files': [{'path': name, 'content': body} for name,body in files.items()]}
        suffix = case.removeprefix(AID+'__')
        path = HERE/('construction-'+suffix+'.json')
        path.write_text(json.dumps(construction,indent=2)+'\n')
        rows.append({'case_id': case, 'construction': path.name,
                     'construction_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                     'candidate_risk': {'status': 'physical', 'reason': item['physical_risk']['risk']}})
    (HERE/'execution-manifest.draft.json').write_text(json.dumps({
        'assignment_id': AID, 'status': 'diagnostic_offline_only_original_sources_pending',
        'cases': rows},indent=2)+'\n')
    print('built five exact entry-timing diagnostic constructions')


if __name__ == '__main__':
    build()

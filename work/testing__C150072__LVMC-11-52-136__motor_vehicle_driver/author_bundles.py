"""Deterministically author five exact inline access-aisle Native constructions."""
from __future__ import annotations

import json
from pathlib import Path

from access_aisle import CASES
from author_semantics import RECORDING

ROOT = Path(__file__).resolve().parent
AID = ROOT.name
LAW = 'LVMC-11-52-136'
CAMERAS = [{'name': name, 'width': width, 'height': height,
            'pose_strategy': strategy, 'fov_deg': 90}
           for name, width, height, strategy in (
               ('overview', 1920, 1080, 'fixed marked aisle, adjacent space and vehicle body'),
               ('approach', 1280, 720, 'fixed one-way approach and terminal activity'),
               ('reference_corner', 1280, 720, 'fixed aisle/space boundary and vehicle body'),
               ('driver_reference', 1280, 720, 'vehicle mounted forward approach view'))]
SOURCE_FILES = ('runner.py', 'native_aisle.py', 'access_aisle.py', 'site_review.py', 'analysis.py',
                'tests/test_access_aisle.py')


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def main():
    for i, item in enumerate(CASES):
        cid = AID + '__' + item.case_id
        config = {'assignment_id': AID, 'selected_case_id': cid,
                  'supported_case_ids': [AID + '__' + x.case_id for x in CASES],
                  'law_id': LAW, 'cell_id': 'C150072', 'actor': 'motor_vehicle_driver',
                  'rate_hz': 20, 'duration_s': 45,
                  'required_atoms': [], 'source_packets': [], 'cameras': CAMERAS,
                  'physical_completion': {'criterion': 'travel_progress',
                                          'motion_source': 'trace.jsonl',
                                          'position_key': 'position_m',
                                          'minimum_progress_m': 4, 'minimum_samples': 2,
                                          'engineering_tolerances_not_legal': True},
                  'case': {'case_id': cid, 'requested_footprint': item.target,
                           'requested_activity': item.requested_activity,
                           'recording_description': RECORDING}}
        files = [{'path': name, 'source': str((ROOT / name).relative_to(ROOT.parents[1])),
                  'content': (ROOT / name).read_text(encoding='utf-8')}
                 for name in SOURCE_FILES]
        files.append({'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'})
        construction = {'law_id': LAW, 'cell_id': 'C150072', 'actor': 'motor_vehicle_driver',
                        'case_id': cid, 'entrypoint': 'runner.py', 'files': files,
                        'measurement_plan': [{'name': 'access_aisle_footprint_activity',
                                              'method': 'analysis.analyze',
                                              'sources': ['access-aisle-history.jsonl',
                                                          'access-aisle-site.json', 'video_frames.jsonl',
                                                          'trace.jsonl']}],
                        'recording_description': RECORDING,
                        'static_checks': ['exact case and reviewed original site source identities',
                                          'vehicle body/aisle polygon overlap and activity readback'],
                        'termination_rules': ['45 seconds of original 20 Hz one-way approach and terminal activity'],
                        'mechanisms': ['reviewed access-aisle map and markings',
                                       'ego route and activity controller',
                                       'body polygon readback', 'four synchronized cameras',
                                       'saved-only source-bound finalizer']}
        where = ROOT if i == 0 else ROOT / 'cases' / item.case_id
        write(where / 'config.json', config)
        write(where / 'construction.json', construction)


if __name__ == '__main__':
    main()

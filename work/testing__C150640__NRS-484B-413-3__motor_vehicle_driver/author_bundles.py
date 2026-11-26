"""Materialize five exact source-gated rear-signal Native constructions."""
from __future__ import annotations

import json
from pathlib import Path

from rear_signal import CASES
from author_semantics import RECORDING

ROOT = Path(__file__).resolve().parent
AID = ROOT.name
LAW = 'NRS-484B-413-3'
CAMERAS = [{'name': name, 'width': width, 'height': height,
            'pose_strategy': strategy, 'fov_deg': 90}
           for name, width, height, strategy in (
               ('overview', 1920, 1080, 'fixed one-way route and two vehicles'),
               ('approach', 1280, 720, 'fixed ego stop/decrease and displayed signal'),
               ('reference_corner', 1280, 720, 'fixed rear gap and lateral relation'),
               ('driver_reference', 1280, 720, 'rear driver mounted view toward ego signal'))]
SOURCE_FILES = ('runner.py', 'native_signal.py', 'rear_signal.py', 'scene_review.py',
                'analysis.py', 'tests/test_rear_signal.py')


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def main():
    for i, item in enumerate(CASES):
        cid = AID + '__' + item.case_id
        config = {'assignment_id': AID, 'selected_case_id': cid,
                  'supported_case_ids': [AID + '__' + x.case_id for x in CASES],
                  'law_id': LAW, 'cell_id': 'C150640', 'actor': 'motor_vehicle_driver',
                  'rate_hz': 20, 'duration_s': 45,
                  'required_atoms': [], 'source_packets': [], 'cameras': CAMERAS,
                  'physical_completion': {'criterion': 'travel_progress',
                                          'motion_source': 'trace.jsonl',
                                          'position_key': 'position_m',
                                          'minimum_progress_m': 4, 'minimum_samples': 2,
                                          'engineering_tolerances_not_legal': True},
                  'case': {'case_id': cid, 'maneuver': item.maneuver,
                           'signal_policy': item.signal_policy,
                           'rear_driver_present': item.rear_driver,
                           'recording_description': RECORDING}}
        files = [{'path': name, 'source': str((ROOT / name).relative_to(ROOT.parents[1])),
                  'content': (ROOT / name).read_text(encoding='utf-8')}
                 for name in SOURCE_FILES]
        files.append({'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'})
        construction = {'law_id': LAW, 'cell_id': 'C150640', 'actor': 'motor_vehicle_driver',
                        'case_id': cid, 'entrypoint': 'runner.py', 'files': files,
                        'measurement_plan': [{'name': 'rear_signal_order_and_recipient',
                                              'method': 'analysis.analyze',
                                              'sources': ['rear-signal-history.jsonl',
                                                          'rear-signal-scene.json',
                                                          'video_frames.jsonl', 'trace.jsonl']}],
                        'recording_description': RECORDING,
                        'static_checks': ['exact case and reviewed original scene identities',
                                          'two actor IDs, rear driver, signal device and source hashes'],
                        'termination_rules': ['45 seconds of original 20 Hz approach, signal onset and stop/decrease'],
                        'mechanisms': ['reviewed one-way map and rear vehicle',
                                       'ego and rear motion controllers',
                                       'physical signal light readback',
                                       'rear-mounted view and four synchronized cameras',
                                       'saved-only source-bound finalizer']}
        where = ROOT if i == 0 else ROOT / 'cases' / item.case_id
        write(where / 'config.json', config)
        write(where / 'construction.json', construction)


if __name__ == '__main__':
    main()

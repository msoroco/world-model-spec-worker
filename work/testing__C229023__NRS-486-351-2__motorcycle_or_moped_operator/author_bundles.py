"""Materialize all five exact same-lane/abreast Native constructions."""
from __future__ import annotations

import json
from pathlib import Path

from author_semantics import RECORDING


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
AID = ROOT.name
LAW = 'NRS-486-351-2'
SOURCE_FILES = ('runner.py', 'scene_review.py', 'original_capture.py',
                'analysis.py', 'same_lane_pass.py',
                'tests/test_same_lane_pass.py', 'tests/test_bundle.py')
CAMERAS = [
    {'name': name, 'width': width, 'height': height,
     'pose_strategy': strategy, 'fov_deg': 90}
    for name, width, height, strategy in (
        ('overview', 1920, 1080, 'fixed wide lane, full participants and pass route'),
        ('approach', 1280, 720, 'upstream original behind-to-ahead view'),
        ('reference_corner', 1280, 720, 'lateral body footprints and lane boundary'),
        ('driver_reference', 1280, 720, 'ego-mounted forward participant view'),
    )
]


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n',
                    encoding='utf8')


def bundle(case, ids, shift_m):
    cid = case['case_id']
    config = {
        'assignment_id': AID, 'selected_case_id': cid,
        'supported_case_ids': ids, 'law_id': LAW, 'cell_id': 'C229023',
        'actor': 'motorcycle_or_moped_operator', 'rate_hz': 20,
        'duration_s': 45, 'required_atoms': [], 'source_packets': [],
        'cameras': CAMERAS,
        'engineering': {'start_station_shift_m': shift_m},
        'physical_completion': {
            'criterion': 'travel_progress', 'motion_source': 'trace.jsonl',
            'position_key': 'position_m', 'minimum_progress_m': 3,
            'minimum_samples': 2, 'engineering_tolerances_not_legal': True,
        },
        'recording_description': RECORDING,
        'case': {
            'case_id': cid,
            'requested_same_lane': case['requested_same_lane'],
            'requested_pass': case['requested_pass'],
            'requested_driver_consent': case['requested_driver_consent'],
            'requested_two_wheeler_count': case['requested_two_wheeler_count'],
            'recording_description': RECORDING,
        },
    }
    files = [
        {'path': name, 'source': str((ROOT / name).relative_to(REPO)),
         'content': (ROOT / name).read_text(encoding='utf8')}
        for name in SOURCE_FILES
    ]
    files.append({'path': 'config.json',
                  'content': json.dumps(config, indent=2) + '\n'})
    construction = {
        'law_id': LAW, 'cell_id': 'C229023',
        'actor': 'motorcycle_or_moped_operator', 'case_id': cid,
        'entrypoint': 'runner.py', 'files': files,
        'recording_description': RECORDING,
        'measurement_plan': [{
            'name': 'same_lane_passage_and_abreast',
            'method': 'analysis.analyze',
            'sources': ['same-lane-history.jsonl', 'same-lane-scene.json',
                        'trace.jsonl', 'video_frames.jsonl'],
        }],
        'static_checks': [
            'source reviewed original map and monotone route stations',
            'full motorcycle footprints fit surveyed traffic lane where requested',
            'three participant layout and actor identities preserved',
            'consent and subsection 3 kept separate from motion geometry',
        ],
        'termination_rules': ['45 seconds at 20 Hz, or original Native failure with restoration'],
        'mechanisms': [
            'reviewed map and lane survey, source-hashed participant classifications',
            'two or three independently spawned and controlled Native vehicles',
            'original lane and body readback each frame',
            'four synchronized RGB cameras with original frame map',
            'saved-only source-bound analysis and independent delivery audit',
        ],
    }
    return config, construction


def main():
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    ids = [item['case_id'] for item in plan['cases']]
    for index, case in enumerate(plan['cases']):
        suffix = case['case_id'].removeprefix(AID + '__')
        primary = ROOT if index == 0 else ROOT / 'cases' / suffix
        config, construction = bundle(case, ids, 0)
        write(primary / 'config.json', config)
        write(primary / 'construction.json', construction)
        fallback = ROOT / 'cases' / suffix / 'fallback1'
        config, construction = bundle(case, ids, -3)
        write(fallback / 'config.json', config)
        write(fallback / 'construction.json', construction)


if __name__ == '__main__':
    main()

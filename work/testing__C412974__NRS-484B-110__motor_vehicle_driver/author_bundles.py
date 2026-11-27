"""Materialize four exact source-gated NRS 484B.110 constructions."""
from __future__ import annotations

import json
from pathlib import Path

from author_plan import CHANNELS
from zone_motion import CASES

ROOT = Path(__file__).resolve().parent
AID = ROOT.name
LAW = 'NRS-484B-110'
FILES = ('runner.py', 'native_zone.py', 'site_review.py', 'zone_motion.py', 'analysis.py',
         'tests/test_zone_motion.py')
CAMERAS = [
    {'name': name, 'width': width, 'height': height, 'pose_strategy': strategy, 'fov_deg': 90}
    for name, width, height, strategy in (
        ('overview', 1920, 1080, 'fixed entire sourced zone and vehicle route'),
        ('approach', 1280, 720, 'fixed entry and vehicle footprint'),
        ('reference_corner', 1280, 720, 'fixed physical boundary marking and sign'),
        ('driver_reference', 1280, 720, 'ego-mounted zone marking and sign view'),
    )
]
CONTEXT = ('highway_status', 'official_designation', 'visible_marking',
           'driver_identity', 'vehicle_class')


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def recording() -> dict:
    return {
        'channels': [
            {'name': name, 'unit': 'structured original record', 'sampling_rate_hz': 20,
             'method': 'Original Native frame acquisition and saved-only extraction',
             'time_window': 'whole 45 s zone encounter',
             'reference_frame': 'original CARLA world frame and timestamp',
             'uncertainty': '20 Hz sampling and original actor bounding-box vertices'}
            for name in CHANNELS
        ],
        'context_inputs': [
            {'name': name, 'unit': 'reviewed original source packet',
             'method': 'Independent highway, designation, marking, vehicle and driver source binding'}
            for name in CONTEXT
        ],
        'limitations': [
            'Physical markers and fixture fields alone do not establish an officially designated pedestrian-only safety zone.',
            'Any overlap frame is a geometric observation, not a legal determination.',
            'Actual marking visibility, motion and camera pixels require independent original review.',
        ],
    }


def main() -> None:
    ids = [AID + '__' + case.name for case in CASES]
    description = recording()
    for index, case in enumerate(CASES):
        cid = ids[index]
        config = {
            'assignment_id': AID, 'selected_case_id': cid, 'supported_case_ids': ids,
            'law_id': LAW, 'cell_id': 'C412974', 'actor': 'motor_vehicle_driver',
            'rate_hz': 20, 'duration_s': 45, 'engineering_throttle': .25,
            'engineering_braking_factor': 5.0, 'required_atoms': [], 'source_packets': [],
            'cameras': CAMERAS,
            'physical_completion': {
                'criterion': 'travel_progress', 'motion_source': 'trace.jsonl',
                'position_key': 'position_m', 'minimum_progress_m': 4,
                'minimum_samples': 2, 'engineering_tolerances_not_legal': True,
            },
            'case': {'case_id': cid, 'route_variant': case.route,
                     'designation_status': case.designation,
                     'recording_description': description},
        }
        files = [
            {'path': name, 'source': str((ROOT / name).relative_to(ROOT.parents[1])),
             'content': (ROOT / name).read_text(encoding='utf-8')}
            for name in FILES
        ]
        files.append({'path': 'config.json', 'content': json.dumps(config, indent=2, ensure_ascii=False) + '\n'})
        construction = {
            'law_id': LAW, 'cell_id': 'C412974', 'actor': 'motor_vehicle_driver',
            'case_id': cid, 'entrypoint': 'runner.py', 'files': files,
            'measurement_plan': [
                {'name': 'safety_zone_original_body_motion', 'method': 'analysis.analyze',
                 'sources': ['safety-zone-site.json', 'safety-zone-history.jsonl',
                             'video_frames.jsonl', 'trace.jsonl']}
            ],
            'recording_description': description,
            'static_checks': [
                'exact case, original reviewed highway and zone source hashes',
                'official designation, continuing markings or signs and map hash',
                'physical boundary markers and motor vehicle route through, within or beside zone',
                '20 Hz original vehicle body footprint, motion and time join',
            ],
            'termination_rules': [
                '45 seconds at 20 Hz through or within a fixed zone',
                'failed frame join, source readback, cleanup or restoration rejects capture',
            ],
            'mechanisms': [
                'reviewed original zone and highway source gate',
                'physical zone boundary markers and motor-vehicle controller',
                'four synchronized cameras and original frame map',
                'saved-only source-bound finalizer',
            ],
        }
        folder = ROOT if index == 0 else ROOT / 'cases' / case.name
        write(folder / 'config.json', config)
        write(folder / 'construction.json', construction)


if __name__ == '__main__':
    main()

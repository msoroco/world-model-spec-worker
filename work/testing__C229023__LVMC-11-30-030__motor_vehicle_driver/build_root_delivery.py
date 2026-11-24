"""Bind the six exact cases to a canonical, CPU-checkable capture entrypoint."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def write_json(name, value):
    (ROOT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def build():
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    plan['source_observation_mapping'] = {}
    plan['camera_plan'] = {
        'profile': 'overview1080-capability',
        'duration_s': 45,
        'composition': 'synchronized_four_view_primary',
        'coverage': [
            {'subject': 'intersection, crossing geometry, original vehicle and pedestrian trajectories',
             'interval': 'startup through clearance at 20 Hz for 45 s', 'view': 'overview'},
            {'subject': 'ego rear approach and lead passing clearance',
             'interval': 'approach through clearance at 20 Hz for 45 s', 'view': 'approach'},
            {'subject': 'markings, curbs, crossing pedestrian and lead stop',
             'interval': 'lead stop through pedestrian clearance at 20 Hz for 45 s', 'view': 'reference_corner'},
            {'subject': 'driver approach, stopped lead and crossing pedestrian',
             'interval': 'approach through final observation at 20 Hz for 45 s', 'view': 'driver_reference'},
        ],
    }
    write_json('case-plan.json', plan)
    raw = (ROOT / 'case-plan.json').read_bytes()
    ids = sorted(row['case_id'] for row in plan['cases'])
    cameras = [
        {'name': 'overview', 'width': 1920, 'height': 1080,
         'pose_strategy': 'elevated fixed intersection view including both vehicles, crosswalk and pedestrian',
         'fov_deg': 90},
        {'name': 'approach', 'width': 1280, 'height': 720,
         'pose_strategy': 'fixed rear approach view including ego and lead vehicle body extents',
         'fov_deg': 80},
        {'name': 'reference_corner', 'width': 1280, 'height': 720,
         'pose_strategy': 'fixed corner view across crossing markings and opposite sidewalks',
         'fov_deg': 75},
        {'name': 'driver_reference', 'width': 1280, 'height': 720,
         'pose_strategy': 'fixed driver reference view toward stopped lead and crossing pedestrian',
         'fov_deg': 75},
    ]
    config = {
        'assignment_id': plan['assignment_id'], 'law_id': plan['law_id'],
        'cell_id': plan['cell_id'], 'actor': plan['actor'],
        'supported_case_ids': ids, 'plan_sha256': hashlib.sha256(raw).hexdigest(),
        'rate_hz': 20, 'frame_count': 900, 'duration_s': 45,
        'cameras': cameras, 'required_atoms': [], 'source_packets': [],
    }
    write_json('config.json', config)
    source_names = [entry['path'] for entry in json.loads(
        (ROOT / 'construction-unmarked_wait.json').read_text())['files']]
    source_names = [name for name in source_names if (ROOT / name).is_file()]
    source_names.extend(['runner.py', 'build_root_delivery.py', 'delivery_audit.py'])
    files = [{'path': name, 'content': (ROOT / name).read_text()}
             for name in sorted(set(source_names))]
    source = json.loads((ROOT / 'construction-unmarked_wait.json').read_text())
    recording = source['recording_description']
    for observation in plan['observations']:
        recording['channels'].append({
            'name': observation['name'], 'unit': 'structured original observation',
            'sampling_rate_hz': 20,
            'method': observation['source'] + '; ' + observation['measurement'],
            'time_window': '45 s original approach through clearance',
            'reference_frame': 'source-hashed original Native map, actor and camera packets',
            'uncertainty': 'Synthetic CPU fixture does not establish physical or legal outcome',
        })
    construction = {
        'law_id': plan['law_id'], 'cell_id': plan['cell_id'], 'actor': plan['actor'],
        'entrypoint': 'runner.py', 'files': files,
        'recording_description': recording,
        'measurement_plan': {
            'source': 'Original 20 Hz actor bodies, crossing geometry, independent stop-purpose packet and four synchronized camera views',
            'case_contracts': [entry['measurement_contract'] for entry in
                               json.loads((ROOT / 'execution-manifest.json').read_text())['cases']],
            'comparisons': plan['comparisons'],
        },
        'static_checks': [
            'runner.py --case EXACT_ID --check verifies plan digest and selection',
            'source packets identify road intersection, crossing geometry and independent stop-purpose statement',
            'all six exact selected cases retain 900 aligned Native and camera frames',
        ],
        'termination_rules': [
            'complete 45 s original trace or explicitly return incomplete physical result',
            'reject missing camera frames, actor histories, geometry or stop-purpose source',
        ],
        'mechanisms': [
            'construct lead vehicle stopped at reviewed crossing and pedestrian crossing that geometry',
            'construct ego rear approach with selected pass or wait maneuver',
            'retain fixed geometry and actor trajectories across each declared comparison',
        ],
    }
    write_json('construction.json', construction)
    print('canonical root delivery bundle bound', len(ids), 'cases', len(files), 'files')


if __name__ == '__main__':
    build()

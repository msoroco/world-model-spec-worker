"""Independent source-hashed comparison of private-way yield and early entry."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRATCH = ROOT.parents[1] / '.runtime-work/c177626-entry'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def require(value, message):
    if not value:
        raise ValueError(message)


def audit():
    configurations, sources, measured, actors = [], [], [], []
    for suffix in ('a', 'b'):
        attempt = SCRATCH / f'compat-{suffix}-primary-v4'
        saved = SCRATCH / f'saved-{suffix}-v1/v0001'
        config = read(attempt / 'config.json')
        processing = read(saved / 'processing.json')
        report = read(saved / 'analysis/analysis-report.json')
        episode = report['measurements']['private_way_entry']
        require(processing['passed'] and processing['recorded_only'] and
                processing['originals_preserved'] and not processing['missing_evidence'],
                'Recorded-only source processing absent')
        value = episode['value']
        require(value['frame_count'] == 600 and value['highway_vehicle_count'] == 2 and
                value['legal_verdict_claimed'] is False,
                'Source-bound all-approaching-vehicle episode differs')
        require(all(sha(attempt / name) == digest for name, digest in episode['sources'].items()),
                'Saved measured source hash differs from diagnostic')
        configurations.append(config)
        sources.append({'case_id': config['case_id'], 'road.xodr': sha(attempt / 'road.xodr'),
                        'private-entry-actors.jsonl': sha(attempt / 'private-entry-actors.jsonl'),
                        'processing.json': sha(saved / 'processing.json')})
        measured.append(value)
        actors.append(rows(attempt / 'private-entry-actors.jsonl'))
    fixed = ('law_id', 'cell_id', 'actor', 'cameras', 'rate_hz',
             'duration_s', 'required_atoms', 'source_packets')
    require(all(configurations[0][key] == configurations[1][key] for key in fixed),
            'Fixed source construction changed')
    require(sources[0]['road.xodr'] == sources[1]['road.xodr'] and
            sources[0]['private-entry-actors.jsonl'] != sources[1]['private-entry-actors.jsonl'],
            'Road changed or deliberate ego entry phase did not change')
    for before, after in zip(*actors):
        for name in ('approach_1', 'approach_2'):
            require(before['actors'][name] == after['actors'][name],
                    'Highway approach trajectories changed across comparison')
    require(measured[0]['highway_vehicles_before_ego'] == 2 and
            measured[1]['highway_vehicles_before_ego'] == 1,
            'Selected source-shaped arrival-order contrast absent')
    return {'format': 'c177626-synthetic-comparison-audit-v1',
            'comparison_id': ROOT.name + '__comparison',
            'case_ids': [row['case_id'] for row in sources],
            'source_sha256': sources,
            'measured_episode': [{'ego_conflict_frame': item['ego_conflict_frame'],
                                  'highway_vehicles_before_ego': item['highway_vehicles_before_ego']}
                                 for item in measured],
            'checks': {'fixed_road_camera_duration_actor': True,
                       'identical_both_highway_trajectories': True,
                       'saved_original_source_hashes': True,
                       'different_measured_entry_order': True,
                       'all_approaching_vehicles_inventoried': True,
                       'no_legal_cutoff_inference': True},
            'diagnostic_fixture': True,
            'accepted_membership_equivalence_claimed': False,
            'physical_or_legal_acceptance': False, 'passed': True}


if __name__ == '__main__':
    result = audit()
    path = ROOT / 'native/proofs/comparison.json'
    path.write_text(json.dumps(result, indent=2).rstrip() + '\n')
    print(json.dumps({'passed': True, 'measured_episode': result['measured_episode']}))

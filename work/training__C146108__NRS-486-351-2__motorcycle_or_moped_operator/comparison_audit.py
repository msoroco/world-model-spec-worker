"""Independently compare two source-joined saved-only motorcycle diagnostics."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRATCH = ROOT.parents[1] / '.runtime-work/c146108-moto'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def require(value, message):
    if not value:
        raise ValueError(message)


def audit():
    configs, sources, values = [], [], []
    for i in (1, 2):
        attempt = SCRATCH / f'compat-{i}-v3'
        saved = SCRATCH / f'saved-{i}-v1/v0001'
        config = read(attempt / 'config.json')
        processing = read(saved / 'processing.json')
        report = read(saved / 'analysis/analysis-report.json')
        measured = report['measurements']['same_lane_episode']
        law = report['measurements']['statutory_alternatives']['value']
        value = measured['value']
        require(processing['passed'] and processing['recorded_only'] and
                processing['originals_preserved'] and not processing['missing_evidence'],
                'Recorded-only source processing absent')
        require(value['frame_count'] == 600 and
                law['subsection_3_pair_eligible'] is False and
                law['legal_verdict_claimed'] is False,
                'Source-bound same-lane or statutory alternative review differs')
        require(all(sha(attempt / name) == digest
                    for name, digest in measured['sources'].items()),
                'Saved measured source hash differs from original diagnostic')
        if i == 1:
            require(value['same_lane_all_frames'] and
                    value['longitudinal_overlap_frames'] == 0,
                    'Controlled following source has overlap')
        else:
            require(value['first_behind_frame'] < value['first_overlap_frame'] <
                    value['first_clear_ahead_frame'], 'Controlled passing order absent')
        configs.append(config)
        sources.append({'case_id': config['case_id'],
                        'road.xodr': sha(attempt / 'road.xodr'),
                        'participant-poses.jsonl': sha(attempt / 'participant-poses.jsonl'),
                        'processing.json': sha(saved / 'processing.json')})
        values.append(value)
    fixed = ('law_id', 'cell_id', 'actor', 'cameras',
             'rate_hz', 'duration_s', 'required_atoms', 'rider_class')
    require(all(configs[0][key] == configs[1][key] for key in fixed),
            'Fixed source construction changed')
    require(sources[0]['road.xodr'] == sources[1]['road.xodr'] and
            sources[0]['participant-poses.jsonl'] != sources[1]['participant-poses.jsonl'],
            'Road changed or deliberate rider motion did not change')
    return {'format': 'c146108-synthetic-comparison-audit-v1',
            'comparison_id': ROOT.name + '__comparison',
            'case_ids': [row['case_id'] for row in sources],
            'source_sha256': sources,
            'measured_episode': [{'following_overlap_frames': values[0]['longitudinal_overlap_frames']},
                                 {'first_behind_frame': values[1]['first_behind_frame'],
                                  'first_overlap_frame': values[1]['first_overlap_frame'],
                                  'first_clear_ahead_frame': values[1]['first_clear_ahead_frame']}],
            'checks': {'fixed_road_camera_duration_actor': True,
                       'saved_original_source_hashes': True,
                       'different_measured_episode': True,
                       'subsection_3_car_pair_excluded': True,
                       'no_legal_cutoff_inference': True},
            'diagnostic_fixture': True,
            'accepted_membership_equivalence_claimed': False,
            'physical_or_legal_acceptance': False,
            'passed': True}


if __name__ == '__main__':
    result = audit()
    path = ROOT / 'native/proofs/comparison.json'
    path.write_text(json.dumps(result, indent=2).rstrip() + '\n')
    print(json.dumps({'passed': True, 'measured_episode': result['measured_episode']}))

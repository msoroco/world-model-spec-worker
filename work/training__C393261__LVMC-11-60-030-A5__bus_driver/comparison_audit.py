"""Independently compare source-joined synthetic bus dwell recordings."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRATCH = ROOT.parents[1] / '.runtime-work/c393261-proof'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def require(value, message):
    if not value:
        raise ValueError(message)


def audit():
    configs, sources, dwells = [], [], []
    for i, expected in ((1, 8.0), (2, 18.0)):
        attempt = SCRATCH / f'saved-attempt-0{i}'
        saved = SCRATCH / f'saved-v3-0{i}/v0001'
        config = read(attempt / 'config.json')
        processing = read(saved / 'processing.json')
        report = read(saved / 'analysis/analysis-report.json')
        measured = report['measurements']['bus_dwell']
        value = measured['value']
        require(processing['passed'] and processing['recorded_only'] and
                processing['originals_preserved'] and not processing['missing_evidence'],
                'Recorded-only source processing absent')
        require(value['longest_complete_interval_s'] == expected and
                value['frames'] == 600 and len(value['parking_intervals']) == 1,
                'Measured dwell does not match source-shaped diagnostic interval')
        require(value['designated_period_s'] is None and
                value['dwell_exceeds_verified_period'] is None and
                value['legal_conclusion'] is None and
                value['activity_classification_unverified'] is True,
                'Unsourced authority or legal conclusion claimed')
        require(all(sha(attempt / name) == digest
                    for name, digest in measured['sources'].items()),
                'Saved measured source hash differs from original')
        configs.append(config)
        sources.append({'case_id': config['case_id'],
                        'road.xodr': sha(attempt / 'road.xodr'),
                        'terminus-history.jsonl': sha(attempt / 'terminus-history.jsonl'),
                        'terminus-context.json': sha(attempt / 'terminus-context.json'),
                        'processing.json': sha(saved / 'processing.json')})
        dwells.append(expected)
    fixed = ('law_id', 'cell_id', 'actor', 'cameras',
             'rate_hz', 'duration_s', 'required_atoms')
    require(all(configs[0][key] == configs[1][key] for key in fixed),
            'Fixed source construction changed')
    require(sources[0]['road.xodr'] == sources[1]['road.xodr'] and
            sources[0]['terminus-context.json'] == sources[1]['terminus-context.json'],
            'Road or authority context changed')
    return {'format': 'c393261-synthetic-comparison-audit-v1',
            'comparison_id': ROOT.name + '__planned_comparison',
            'case_ids': [row['case_id'] for row in sources],
            'source_sha256': sources,
            'measured_bus_dwell_s': dwells,
            'checks': {'fixed_road_camera_duration_actor': True,
                       'saved_original_source_hashes': True,
                       'same_unsourced_authority_context': True,
                       'different_measured_dwell': True,
                       'no_legal_cutoff_inference': True},
            'diagnostic_fixture': True,
            'accepted_membership_equivalence_claimed': False,
            'physical_or_legal_acceptance': False,
            'passed': True}


if __name__ == '__main__':
    result = audit()
    path = ROOT / 'native/proofs/comparison.json'
    path.write_text(json.dumps(result, indent=2).rstrip() + '\n')
    print(json.dumps({'passed': True, 'measured_bus_dwell_s': result['measured_bus_dwell_s']}))

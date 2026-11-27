"""Independent CPU comparison of three saved synthetic approach-speed cases."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / '.runtime-work/c229398-check'
SPEEDS = (75.0, 79.5, 85.0)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def require(value, message):
    if not value:
        raise ValueError(message)


def audit():
    sources, values, configs = [], [], []
    for index, requested in enumerate(SPEEDS, 1):
        suffix = f'probe_0{index}'
        attempt = SCRATCH / ('saved-attempt-' + suffix + '-v1')
        saved = SCRATCH / ('saved-' + suffix + '-v1/v0001')
        config = read(attempt / 'config.json')
        processing = read(saved / 'processing.json')
        report = read(saved / 'analysis/analysis-report.json')
        measured = report['measurements']['approach_speed']['value']
        require(processing['passed'] is True and processing['recorded_only'] is True and
                processing['originals_preserved'] is True and
                processing['missing_evidence'] is False,
                'Recorded-only positive source processing missing')
        require(config['requested_approach_speed_mph'] == requested and
                measured['requested_speed_used_for_measurement'] is False,
                'Controller request substituted for measurement')
        require(measured['approach_frame_range'] == [0,399] and
                measured['parked_frame_range'] == [520,599] and
                measured['max_parked_speed_mph'] <= .5,
                'Driving and parked phases not isolated')
        original = report['measurements']['approach_speed']['sources']
        require(all(sha(attempt / name) == digest for name,digest in original.items()),
                'Saved source hash differs')
        sources.append({'case_id': config['case_id'],
                        'config.json': sha(attempt / 'config.json'),
                        'road.xodr': sha(attempt / 'road.xodr'),
                        'native-speed.jsonl': sha(attempt / 'native-speed.jsonl'),
                        'processing.json': sha(saved / 'processing.json')})
        values.append(measured['max_approach_speed_mph'])
        configs.append(config)
    fixed = ('law_id','cell_id','actor','frozen_cell','cameras','ego_blueprint',
             'rate_hz','duration_s','frames','required_atoms','recording_description')
    require(all(configs[0][key] == config[key] for config in configs[1:]
                for key in fixed), 'Fixed source construction changed')
    require(len({entry['road.xodr'] for entry in sources}) == 1,
            'Exact road/curb source changed')
    require(values[0] < 80 and values[1] < 80 and values[2] > 80,
            'Diagnostic measured contrast does not straddle strict threshold')
    return {'format': 'c229398-synthetic-comparison-audit-v1',
            'comparison_id': ROOT.name + '__planned_comparison',
            'case_ids': [entry['case_id'] for entry in sources],
            'source_sha256': sources,
            'measured_max_approach_speed_mph': values,
            'checks': {'fixed_road_camera_duration_actor': True,
                       'saved_original_source_hashes': True,
                       'driving_vs_parked_phase_isolation': True,
                       'requested_speed_not_used_as_measurement': True,
                       'strict_greater_than_80_diagnostic_contrast': True},
            'diagnostic_fixture': True,
            'accepted_membership_equivalence_claimed': False,
            'physical_or_legal_acceptance': False,
            'passed': True}


if __name__ == '__main__':
    report = audit()
    path = ROOT / 'native/proofs/comparison.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': report['passed'],
                      'measured_max_approach_speed_mph': report['measured_max_approach_speed_mph']}))

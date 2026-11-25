"""Independently compare exact selected synthetic source chains without a verdict."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c394300-selected-public/output'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def audit():
    manifest = read(HERE / 'selected-probe-manifest.json')
    fixed = None
    records = []
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        choices = {'primary': entry, **{item['id']: item for item in entry['candidates']}}
        if set(choices) != {'primary', 'fallback1', 'fallback3'}:
            raise ValueError('Selected candidate set differs')
        for ident, selected in choices.items():
            key = suffix + '-' + ident
            attempt = SCRATCH / key
            config, report, result = (read(attempt / name) for name in
                                      ('config.json', 'analysis-report.json', 'result.json'))
            compatibility = read(HERE / 'selected-public' / (key + '-compatibility.json'))
            processing = read(HERE / 'selected-public' / (key + '-processing.json'))
            if compatibility['construction_sha256'] != selected['construction_sha256'] or not compatibility['passed']:
                raise ValueError('Changed selected compatibility construction')
            if not (processing['passed'] and processing['recorded_only'] and
                    processing['timestamp_joins']['frames'] == 480 and
                    processing['physical_acceptance_claimed'] is False):
                raise ValueError('Selected saved receipt changed')
            if result['provenance_kind'] != 'synthetic_local_diagnostic' or result['accepted'] or result['legal_verdict_claimed']:
                raise ValueError('Diagnostic inference improperly promoted')
            measured = report['measurements']['center_turn_purpose_and_movement']
            for rel, digest in measured['sources'].items():
                if sha(attempt / rel) != digest:
                    raise ValueError('Original source changed: ' + rel)
            movement = measured['value']['movement']
            conditions = (config['cell_id'], config['actor'], config['law_id'],
                          config['duration_s'], config['rate_hz'], config['required_atoms'],
                          config['mandatory_channels'], config['recording_description'],
                          config['cameras'])
            if fixed is None:
                fixed = conditions
            elif conditions != fixed:
                raise ValueError('Controlled fixed conditions differ')
            if suffix == 'controlled_1':
                if not (movement['first_left_connector_frames'] > 0 and
                        movement['first_left_exit_frames'] > 0 and
                        movement['later_left_connector_frames'] == 0 and
                        measured['value']['declared_purpose'] == 'left_turn_from_center_at_first_opportunity'):
                    raise ValueError('First movement diagnostic differs')
            else:
                if not (movement['first_opportunity_center_through_frames'] > 0 and
                        movement['later_through_full_body_frames'] > 0 and
                        movement['later_left_connector_frames'] > 0 and
                        measured['value']['declared_purpose'] == 'through_travel_then_later_left_from_through_lane'):
                    raise ValueError('Second movement diagnostic differs')
            records.append({'case_id': entry['case_id'], 'candidate': ident,
                            'construction_sha256': selected['construction_sha256'],
                            'source_report_sha256': sha(attempt / 'analysis-report.json'),
                            'center_full_body_frames': movement['center_full_body_frames'],
                            'compatibility_sha256': sha(HERE / 'selected-public' / (key + '-compatibility.json')),
                            'processing_sha256': sha(HERE / 'selected-public' / (key + '-processing.json'))})
    if len(records) != 6:
        raise ValueError('Selected comparison lacks all six chains')
    return {'format': 'c394300-selected-source-comparison-v1', 'passed': True,
            'fixed_conditions_verified': True, 'cases': 2, 'candidate_packages': 6,
            'physical_or_legal_acceptance_claimed': False, 'records': records}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))

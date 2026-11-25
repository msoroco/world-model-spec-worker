"""Independently compare nine selected source chains without a legal verdict."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c3943003c-selected-public/attempt'
EXPECTED = {'below_50_ft': 'within_50_feet', 'at_50_ft': 'unresolved_at_50_feet',
            'above_50_ft': 'exceeds_50_feet'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def enforce_fixed(reference, current):
    if reference != current:
        raise ValueError('Controlled fixed conditions differ')


def audit():
    manifest = read(HERE / 'selected-probe-manifest.json')
    fixed = None
    records = []
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        choices = {'primary': entry, **{item['id']: item for item in entry['candidates']}}
        if set(choices) != {'primary', 'fallback1', 'fallback2'}:
            raise ValueError('Selected candidate set differs')
        for ident, selected in choices.items():
            key = suffix + '-' + ident
            attempt = SCRATCH / key
            config, report, result = (read(attempt / name) for name in
                                      ('config.json', 'analysis-report.json', 'result.json'))
            compat = read(HERE / 'selected-public' / (key + '-compatibility.json'))
            processing = read(HERE / 'selected-public' / (key + '-processing.json'))
            if compat['construction_sha256'] != selected['construction_sha256'] or not compat['passed']:
                raise ValueError('Changed selected compatibility construction')
            if not (processing['passed'] and processing['recorded_only'] and
                    processing['timestamp_joins']['frames'] == 600 and
                    processing['physical_acceptance_claimed'] is False):
                raise ValueError('Selected saved receipt changed')
            if result['provenance_kind'] != 'synthetic_local_diagnostic' or result['accepted'] or result['legal_verdict_claimed']:
                raise ValueError('Diagnostic inference improperly promoted')
            measured = report['measurements']['after_left_turn_distance_interval']
            for rel, digest in measured['sources'].items():
                if sha(attempt / rel) != digest:
                    raise ValueError('Original synthetic source changed: ' + rel)
            value = measured['value']
            if value['threshold_relation'] != EXPECTED[suffix]:
                raise ValueError('Distance interval diagnostic differs: ' + suffix)
            conditions = (config['cell_id'], config['actor'], config['law_id'],
                          config['duration_s'], config['rate_hz'], config['required_atoms'],
                          config['mandatory_channels'], config['recording_description'],
                          config['cameras'], sha(attempt / 'road.xodr'))
            if fixed is None:
                fixed = conditions
            else:
                enforce_fixed(fixed, conditions)
            records.append({'case_id': entry['case_id'], 'candidate': ident,
                            'construction_sha256': selected['construction_sha256'],
                            'source_report_sha256': sha(attempt / 'analysis-report.json'),
                            'interval_m': value['distance_interval_m'],
                            'threshold_relation': value['threshold_relation'],
                            'compatibility_sha256': sha(HERE / 'selected-public' / (key + '-compatibility.json')),
                            'processing_sha256': sha(HERE / 'selected-public' / (key + '-processing.json'))})
    if len(records) != 9:
        raise ValueError('Selected comparison lacks all nine chains')
    try:
        enforce_fixed(fixed, fixed[:-1] + ('changed-road-source',))
    except ValueError:
        pass
    else:
        raise ValueError('Fixed-map drift negative was accepted')
    return {'format': 'c394300-3c-selected-source-comparison-v1', 'passed': True,
            'fixed_conditions_verified': True, 'changed_map_rejected': True,
            'cases': 3, 'candidate_packages': 9,
            'physical_or_legal_acceptance_claimed': False, 'records': records}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))

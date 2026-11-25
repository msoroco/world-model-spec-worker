"""Audit one source-bound pedestrian entry intervention across selected packages."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c2281333079c-selected-public-through-v2/attempt'
CASES = ('reference', 'contrast')
CANDIDATES = ('primary', 'fallback1', 'fallback2')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def audit():
    manifest = read(HERE / 'selected-probe-manifest.json')
    if {e['case_id'].rsplit('__', 1)[-1] for e in manifest['cases']} != set(CASES):
        raise ValueError('Selected comparison case roster differs')
    records = []
    fixed = None
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        choices = {'primary': entry, **{item['id']: item for item in entry['candidates']}}
        if set(choices) != set(CANDIDATES):
            raise ValueError('Selected candidate roster differs')
        for candidate, selected in choices.items():
            key = suffix + '-' + candidate
            attempt = SCRATCH / key
            config, report, result = (read(attempt / name) for name in
                                      ('config.json', 'analysis-report.json', 'result.json'))
            compat = read(HERE / 'selected-public' / (key + '-compatibility.json'))
            processing = read(HERE / 'selected-public' / (key + '-processing.json'))
            if not compat['passed'] or compat['construction_sha256'] != selected['construction_sha256']:
                raise ValueError('Selected compatibility construction differs')
            if not (processing['passed'] and processing['recorded_only'] and
                    processing['timestamp_joins']['frames'] == 600 and
                    processing['physical_acceptance_claimed'] is False):
                raise ValueError('Recorded-only proof differs')
            if result['provenance_kind'] != 'synthetic_local_diagnostic' or result['accepted'] or result['legal_verdict_claimed']:
                raise ValueError('Diagnostic accepted as physical or legal evidence')
            value = report['measurements']['road_entry']['value']
            expected = [] if suffix == 'reference' else [80]
            if value['potential_9c_entry_frames'] != expected:
                raise ValueError('Source-bound road entry differs')
            for rel, checksum in report['measurements']['road_entry']['sources'].items():
                if sha(attempt / rel) != checksum:
                    raise ValueError('Source-bound measurement hash differs: ' + rel)
            conditions = (config['cell_id'], config['actor'], config['law_id'],
                          config['duration_s'], config['rate_hz'],
                          config['required_atoms'], config['recording_description'],
                          config['cameras'], sha(attempt / 'road.xodr'),
                          sha(attempt / 'native-signal-frames.jsonl'),
                          sha(attempt / 'native-pedestrian-device-frames.jsonl'),
                          sha(attempt / 'road-boundary.json'),
                          sha(attempt / 'governing-device-authority.json'),
                          sha(attempt / 'highway-authority.json'))
            if fixed is None:
                fixed = conditions
            elif fixed != conditions:
                raise ValueError('Controlled indication, authority, road or capture conditions differ')
            records.append({'case_id': entry['case_id'], 'candidate': candidate,
                            'construction_sha256': selected['construction_sha256'],
                            'entry_frames': expected,
                            'compatibility_sha256': sha(HERE / 'selected-public' / (key + '-compatibility.json')),
                            'saved_sha256': sha(HERE / 'selected-public' / (key + '-processing.json'))})
    if len(records) != 6:
        raise ValueError('Incomplete selected comparison')
    if fixed == fixed[:-1] + ('changed-highway-source',):
        raise ValueError('Changed authority source accepted')
    return {'format': 'c228133-307-9c-selected-comparison-v1', 'passed': True,
            'cases': 2, 'candidate_packages': 6, 'intervention': 'pedestrian_enters_highway',
            'fixed_conditions_verified': True, 'physical_or_legal_acceptance_claimed': False,
            'records': records}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))

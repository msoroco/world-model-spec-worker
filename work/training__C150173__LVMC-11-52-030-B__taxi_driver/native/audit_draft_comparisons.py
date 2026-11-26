"""Audit four taxi request constructions and identical-risk fallbacks."""
import hashlib
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent
PAIRS = (('probe_a', 'probe_b', 'civil_start_local'),
         ('probe_a', 'probe_c', 'requested_purpose'),
         ('probe_a', 'probe_d', 'requested_purpose'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def embedded(construction, name):
    return next(item['content'] for item in construction['files'] if item['path'] == name)


def audit():
    manifest = json.loads((PACKAGE / 'native-draft-manifest.json').read_text())
    if manifest.get('delivery_ready') is not False or len(manifest.get('cases', [])) != 4:
        raise ValueError('Four unselected exact taxi cases required')
    cases = {}
    for entry in manifest['cases']:
        suffix = entry['case_id'].split('__')[-1]
        path = PACKAGE / entry['construction']
        if sha(path) != entry['construction_sha256']:
            raise ValueError('Changed exact construction: ' + suffix)
        construction = json.loads(path.read_text())
        config = json.loads(embedded(construction, 'config.json'))
        if (construction['case_id'] != entry['case_id'] or
                config['case_id'] != entry['case_id'] or
                config['selected_case_id'] != entry['case_id'] or
                config['case']['case_id'] != entry['case_id']):
            raise ValueError('Case identity differs')
        candidate = entry['candidates']
        if len(candidate) != 1 or candidate[0]['id'] != 'fallback1':
            raise ValueError('Risk fallback missing')
        fallback_path = PACKAGE / candidate[0]['construction']
        if sha(fallback_path) != candidate[0]['construction_sha256']:
            raise ValueError('Changed fallback construction')
        fallback = json.loads(fallback_path.read_text())
        fallback_config = json.loads(embedded(fallback, 'config.json'))
        changed = {key for key in config.keys() | fallback_config.keys()
                   if config.get(key) != fallback_config.get(key)}
        if changed != {'taxi_stop_x_m', 'candidate_id'} or fallback_config['taxi_stop_x_m'] != 4.75:
            raise ValueError('Fallback changes an unapproved comparison variable')
        if config['taxi_stop_x_m'] != 5.25:
            raise ValueError('Primary taxi stop differs')
        if embedded(construction, 'yellow-road.xodr') != embedded(fallback, 'yellow-road.xodr'):
            raise ValueError('Fallback road differs')
        primary_rows = [json.loads(row) for row in embedded(construction, 'requested-track.jsonl').splitlines()]
        fallback_rows = [json.loads(row) for row in embedded(fallback, 'requested-track.jsonl').splitlines()]
        if len(primary_rows) != 600 or len(fallback_rows) != 600:
            raise ValueError('Fallback source duration differs')
        for primary_row, fallback_row in zip(primary_rows, fallback_rows):
            if (primary_row.get('requested_stop_xy_m') != [5.25, 10.0] or
                    fallback_row.get('requested_stop_xy_m') != [4.75, 10.0] or
                    any(primary_row.get(key) != fallback_row.get(key)
                        for key in primary_row if key != 'requested_stop_xy_m')):
                raise ValueError('Fallback request changes more than taxi stop')
        cases[suffix] = (config, construction)
    if set(cases) != {'probe_a', 'probe_b', 'probe_c', 'probe_d'}:
        raise ValueError('Taxi waiting/loading/unloading case set incomplete')
    for left, right, variable in PAIRS:
        a, construction_a = cases[left]
        b, construction_b = cases[right]
        if a[variable] == b[variable]:
            raise ValueError('Declared comparison difference absent')
        fixed = {key for key in a if key not in
                 ('case_id', 'selected_case_id', 'case', variable)}
        if any(a[key] != b[key] for key in fixed):
            raise ValueError('Controlled taxi comparison condition differs')
        if embedded(construction_a, 'yellow-road.xodr') != embedded(construction_b, 'yellow-road.xodr'):
            raise ValueError('Controlled taxi road differs')
    return {'format': 'c150173-request-comparison-audit-v1',
            'cases': sorted(cases), 'comparisons': [list(pair) for pair in PAIRS],
            'fallbacks_checked': 4, 'selected': False,
            'physical_or_legal_verdict': None}


if __name__ == '__main__':
    print(json.dumps(audit(), sort_keys=True))

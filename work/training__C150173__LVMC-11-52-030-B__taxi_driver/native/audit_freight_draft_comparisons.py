"""Audit the same-cell freight transfer controls and stop-pose fallback."""
import hashlib
import json
from pathlib import Path

from freight_plan import PURPOSES


PACKAGE = Path(__file__).resolve().parent.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def embedded(construction, name):
    return next(item['content'] for item in construction['files'] if item['path'] == name)


def audit():
    manifest = json.loads((PACKAGE / 'native-freight-draft-manifest.json').read_text())
    cases = {}
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[1]
        if suffix not in PURPOSES:
            raise ValueError('Unexpected freight case')
        path = PACKAGE / entry['construction']
        if sha(path) != entry['construction_sha256']:
            raise ValueError('Freight construction changed: ' + suffix)
        construction = json.loads(path.read_text())
        config = json.loads(embedded(construction, 'config.json'))
        if (config['case_id'] != entry['case_id'] or
                config['requested_purpose'] != PURPOSES[suffix] or
                config['taxi_stop_x_m'] != 5.25):
            raise ValueError('Exact freight identity or purpose differs')
        fallback = entry['candidates'][0]
        fallback_path = PACKAGE / fallback['construction']
        if sha(fallback_path) != fallback['construction_sha256']:
            raise ValueError('Freight fallback construction changed')
        secondary = json.loads(fallback_path.read_text())
        fallback_config = json.loads(embedded(secondary, 'config.json'))
        changes = {key for key in config.keys() | fallback_config.keys()
                   if config.get(key) != fallback_config.get(key)}
        if changes != {'taxi_stop_x_m', 'candidate_id'} or fallback_config['taxi_stop_x_m'] != 4.75:
            raise ValueError('Freight fallback changed the purpose or cell')
        primary_rows = [json.loads(row) for row in embedded(construction, 'requested-track.jsonl').splitlines()]
        fallback_rows = [json.loads(row) for row in embedded(secondary, 'requested-track.jsonl').splitlines()]
        if (len(primary_rows) != 600 or len(fallback_rows) != 600 or
                any(a.get('requested_stop_x_m') != 5.25 or b.get('requested_stop_x_m') != 4.75 or
                    any(a.get(key) != b.get(key) for key in a if key != 'requested_stop_x_m')
                    for a, b in zip(primary_rows, fallback_rows))):
            raise ValueError('Freight fallback track changed more than taxi stop')
        cases[suffix] = (config, construction)
    if set(cases) != set(PURPOSES):
        raise ValueError('Freight load/unload/no-transfer set incomplete')
    fixed = ('assignment_id', 'cell_id', 'law_id', 'actor', 'duration_s',
             'rate_hz', 'frames', 'civil_start_local', 'timezone',
             'cargo_blueprint_filter', 'taxi_stop_x_m', 'commercial_classification',
             'sign_source_status', 'legal_verdict', 'cameras')
    reference = cases['freight_wait'][0]
    for suffix in ('freight_load', 'freight_unload'):
        config = cases[suffix][0]
        if any(config[key] != reference[key] for key in fixed):
            raise ValueError('Freight purpose comparison changed fixed condition')
        if embedded(cases[suffix][1], 'yellow-freight-road.xodr') != embedded(cases['freight_wait'][1], 'yellow-freight-road.xodr'):
            raise ValueError('Freight comparison changed authored curb or sign')
    return {'format': 'c150173-freight-request-comparison-audit-v1',
            'cases': sorted(cases), 'comparisons': [['freight_wait', 'freight_load'],
                                                   ['freight_wait', 'freight_unload']],
            'fallbacks_checked': 3, 'selected': False,
            'original_commercial_or_sign_status_verified': False,
            'physical_or_legal_verdict': None}


if __name__ == '__main__':
    print(json.dumps(audit(), sort_keys=True))

"""Independent CPU audit of the two U-turn safety construction points."""

import json
from pathlib import Path


def _read(path):
    return json.loads(Path(path).read_text())


def _configuration(construction):
    entries = [item for item in construction['files'] if item['path'] == 'config.json']
    if len(entries) != 1:
        raise ValueError('Comparison needs one exact config')
    return json.loads(entries[0]['content'])


def audit(clear_construction, conflict_construction,
          clear_diagnostic, conflict_diagnostic):
    clear, conflict = (_read(path) for path in
                       (clear_construction, conflict_construction))
    if not (clear['case_id'].endswith('__safety_clear') and
            conflict['case_id'].endswith('__safety_conflict')):
        raise ValueError('Wrong U-turn safety case identities')
    a, b = _configuration(clear), _configuration(conflict)
    for key in ('law_id', 'cell_id', 'actor', 'rate_hz', 'frames',
                'duration_s', 'cameras', 'required_atoms', 'source_packets'):
        if a[key] != b[key]:
            raise ValueError('Fixed U-turn comparison changed: ' + key)
    if a['case']['recording_description'] != b['case']['recording_description']:
        raise ValueError('Fixed U-turn measurement contract changed')
    if a['engineering'].get('oncoming_distance_m') != 24 or b['engineering'].get('oncoming_distance_m') != 12:
        raise ValueError('Oncoming distance comparison request differs')
    a_engineering = dict(a['engineering'])
    b_engineering = dict(b['engineering'])
    a_engineering.pop('oncoming_distance_m')
    b_engineering.pop('oncoming_distance_m')
    if a_engineering != b_engineering:
        raise ValueError('Fixed U-turn engineering changed')
    source_a = {item['path']: item['content'] for item in clear['files']}
    source_b = {item['path']: item['content'] for item in conflict['files']}
    if set(source_a) != set(source_b) or any(
            source_a[name] != source_b[name] for name in source_a if name != 'config.json'):
        raise ValueError('Fixed U-turn implementation changed')
    diag_a, diag_b = _read(clear_diagnostic), _read(conflict_diagnostic)
    if diag_a['graphs'] != diag_b['graphs'] or diag_a['videos'] != diag_b['videos']:
        raise ValueError('Fixed source graphs or camera media changed')
    files_a, files_b = diag_a['files'], diag_b['files']
    if set(files_a) != set(files_b) or any(
            files_a[name] != files_b[name] for name in files_a if name != 'u_turn_motion.jsonl'):
        raise ValueError('Fixed original fixture source changed')
    rows_a = [json.loads(x) for x in files_a['u_turn_motion.jsonl'].splitlines()]
    rows_b = [json.loads(x) for x in files_b['u_turn_motion.jsonl'].splitlines()]
    if len(rows_a) != len(rows_b) or len(rows_a) < 3:
        raise ValueError('Original U-turn comparison frames differ')
    oncoming_shift = []
    for x, y in zip(rows_a, rows_b):
        p, q = x['participants']['2'], y['participants']['2']
        oncoming_shift.append(p['x_m']-q['x_m'])
        x = json.loads(json.dumps(x))
        y = json.loads(json.dumps(y))
        x['participants']['2']['x_m'] = y['participants']['2']['x_m']
        if x != y:
            raise ValueError('Uncontrolled original U-turn actor difference')
    if any(abs(shift-8) > 1e-8 for shift in oncoming_shift):
        raise ValueError('Original oncoming distance separation differs')
    return {'comparison_id': 'safety_clearance',
            'case_ids': [clear['case_id'], conflict['case_id']],
            'fixed_conditions_verified': True,
            'requested_oncoming_distance_m': [24, 12],
            'diagnostic_oncoming_x_separation_m': 8,
            'physical_safety_verdict': None, 'legal_safety_verdict': None}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', required=True)
    args = parser.parse_args()
    root = Path(args.package)
    result = audit(root/'construction.json', root/'construction-safety_conflict.json',
                   root/'diagnostic-safety_clear.json',
                   root/'diagnostic-safety_conflict.json')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()

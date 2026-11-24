"""Source-bound CPU comparison of selected diagnostic histories."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FIELD = {
    'device_effective_time': 'device_effective',
    'traffic_conflict_exception': 'traffic_conflict',
    'law_direction_exception': 'law_direction',
    'police_direction_exception': 'police_direction',
    'device_direction_exception': 'device_direction',
}


def source(short, filename):
    path = ROOT / 'cases' / short / 'diagnostic-sources' / filename
    return json.loads(path.read_text()), hashlib.sha256(path.read_bytes()).hexdigest()


def audit(comparison_id, negative=False):
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    entry = next((x for x in plan['comparisons'] if x['comparison_id'] == comparison_id), None)
    if entry is None:
        raise ValueError('unknown exact comparison')
    left, right = [case.rsplit('__', 1)[-1] for case in entry['case_ids']]
    sites = [source(short, 'site-source.json') for short in (left, right)]
    if sites[0][0]['parking_polygon'] != sites[1][0]['parking_polygon']:
        raise ValueError('matched governed place differs')
    rows = [source(short, 'actor_rows.json') for short in (left, right)]
    if len(rows[0][0]) != 900 or len(rows[1][0]) != 900:
        raise ValueError('incomplete original frame histories')
    if [x['frame'] for x in rows[0][0]] != [x['frame'] for x in rows[1][0]]:
        raise ValueError('matched frame cadence differs')
    if [x['subject_id'] for x in rows[0][0]] != [x['subject_id'] for x in rows[1][0]]:
        raise ValueError('matched vehicle identity differs')
    field = FIELD[comparison_id]
    relevant = [(a, b) for a, b in zip(rows[0][0], rows[1][0])
                if a['halt_activity'] in ('park', 'stop', 'stand')]
    if not relevant:
        raise ValueError('no compared halt frames')
    if negative:
        for a, b in relevant:
            b[field] = a[field]
    changed = sum(a[field] != b[field] for a, b in relevant)
    if changed == 0:
        raise ValueError('deliberate source difference absent: ' + field)
    return {'comparison_id': comparison_id, 'case_ids': entry['case_ids'],
            'matched_halt_frames': len(relevant), 'different_halt_frames': changed,
            'deliberate_field': field, 'site_sha256': [s[1] for s in sites],
            'actor_rows_sha256': [r[1] for r in rows],
            'physical_acceptance': False, 'legal_judgment': None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.comparison, args.negative), separators=(',', ':')))


if __name__ == '__main__':
    main()

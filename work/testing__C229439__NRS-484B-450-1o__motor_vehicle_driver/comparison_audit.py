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
    'prohibited_halt_mode': 'prohibited_halt_mode',
}
EXCEPTIONS = ('traffic_conflict', 'law_direction', 'police_direction', 'device_direction')


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
                if a['halt_activity'] in ('park', 'stop', 'stand') and
                b['halt_activity'] in ('park', 'stop', 'stand')]
    if not relevant:
        raise ValueError('no compared halt frames')
    if comparison_id == 'prohibited_halt_mode':
        devices = [source(short, 'device-source.json') for short in (left, right)]
        for a, b in zip(rows[0][0], rows[1][0]):
            for fixed in ('device_effective', *EXCEPTIONS):
                if a[fixed] != b[fixed]:
                    raise ValueError('non-deliberate condition differs: ' + fixed)
        for row in (relevant[0][0], relevant[0][1]):
            action = row['halt_activity']
            if row['prohibited_actions'] != [action]:
                raise ValueError('halt and prohibited instruction do not match')
        left_instruction = relevant[0][0]['device_instruction']
        right_instruction = relevant[0][1]['device_instruction']
        if (left_instruction != devices[0][0]['exact_instruction'] or
                right_instruction != devices[1][0]['exact_instruction']):
            raise ValueError('device instruction source join differs')
        if negative:
            for a, b in relevant:
                b['halt_activity'] = a['halt_activity']
                b['prohibited_actions'] = a['prohibited_actions']
                b['device_instruction'] = a['device_instruction']
            right_instruction = left_instruction
        changed = sum(a['halt_activity'] != b['halt_activity'] and
                      a['prohibited_actions'] != b['prohibited_actions'] and
                      a['device_instruction'] != b['device_instruction']
                      for a, b in relevant)
        if changed != len(relevant):
            raise ValueError('deliberate source difference absent: ' + field)
    else:
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

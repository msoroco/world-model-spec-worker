"""Source-backed diagnostic comparison without physical or legal labeling."""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ATTEMPTS = REPO / '.runtime-work/c229452-saved-v1'
FIELDS = ('vehicle_kind', 'sign', 'activity', 'purpose', 'mail_dropbox_adjacent', 'duration_s')
ALLOWED = {
    'tour_below_vs_at': ('duration_s',),
    'tour_at_vs_above': ('duration_s',),
    'ordinary_vs_tour': ('vehicle_kind', 'sign', 'purpose', 'duration_s'),
    'tour_vs_shuttle': ('vehicle_kind', 'purpose'),
    'tour_vs_limo': ('vehicle_kind',),
    'tour_vs_rtc': ('vehicle_kind', 'sign'),
    'armored_vs_emergency': ('vehicle_kind',),
    'ordinary_stop_vs_mail': ('mail_dropbox_adjacent', 'purpose', 'duration_s'),
    'ordinary_stop_vs_stand': ('activity', 'duration_s'),
    'signed_ordinary_vs_tour': ('vehicle_kind', 'purpose', 'duration_s'),
    'tour_sign': ('sign',),
    'tour_purpose': ('purpose',),
    'rtc_below_vs_at': ('duration_s',),
    'rtc_at_vs_above': ('duration_s',),
    'armored_business_purpose': ('purpose',),
    'emergency_business_purpose': ('purpose',),
    'mail_deposit_purpose': ('purpose',),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source(short):
    folder = ATTEMPTS / short / 'attempt'
    context_path = folder / 'red-curb-context.json'
    events_path = folder / 'original-red-curb-events.jsonl'
    context = json.loads(context_path.read_text())
    events = [json.loads(line) for line in events_path.read_text().splitlines()]
    if len(events) < 2 or context['source_kind'] != 'synthetic_diagnostic_fixture':
        raise ValueError('diagnostic source history missing')
    scene = context['scene']
    if not scene['red_curb_paint'] or not scene['municipal_jurisdiction']:
        raise ValueError('governed red curb changed')
    values = {key: scene[key] for key in FIELDS if key != 'duration_s'}
    values['duration_s'] = events[-1]['original_time_s'] - events[0]['original_time_s']
    return values, {'context_sha256': sha(context_path), 'events_sha256': sha(events_path),
                    'curb_segment_id': scene['curb_segment_id'], 'parking_route_xy': scene['parking_route_xy']}


def audit(name, negative=False):
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    comparison = next((item for item in plan['comparisons'] if item['comparison_id'] == name), None)
    if comparison is None or name not in ALLOWED:
        raise ValueError('unknown exact comparison')
    left, right = [cid.rsplit('__', 1)[-1] for cid in comparison['case_ids']]
    left_values, left_source = source(left)
    right_values, right_source = source(right)
    if (left_source['curb_segment_id'] != right_source['curb_segment_id'] or
            left_source['parking_route_xy'] != right_source['parking_route_xy']):
        raise ValueError('matched curb/route differs')
    if negative:
        for key in ALLOWED[name]:
            right_values[key] = left_values[key]
    differences = [key for key in FIELDS if left_values[key] != right_values[key]]
    if not differences:
        raise ValueError('deliberate source difference absent')
    if not set(differences) <= set(ALLOWED[name]):
        raise ValueError('uncontrolled source difference: ' + ','.join(differences))
    return {'comparison_id': name, 'case_ids': comparison['case_ids'],
            'deliberate_source_fields': differences,
            'sources': [left_source, right_source],
            'physical_acceptance': False, 'legal_judgment': None,
            'diagnostic_only': True}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--comparison', required=True)
    p.add_argument('--negative', action='store_true')
    args = p.parse_args()
    print(json.dumps(audit(args.comparison, args.negative), separators=(',', ':')))


if __name__ == '__main__':
    main()

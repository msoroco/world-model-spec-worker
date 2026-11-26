"""Independent exact-case source comparison of speed and four exception branches."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def value(receipt, key):
    item = receipt['measurement_examples'].get(key)
    if not item or not item.get('value'):
        raise ValueError('Missing comparison source measurement: ' + key)
    return item['value']


def audit(comparison_id, drop_last=False):
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    comparison = next((item for item in plan['comparisons']
                       if item['comparison_id'] == comparison_id), None)
    if comparison is None:
        raise ValueError('Unknown exact comparison')
    entries = {item['case_id']: item for item in manifest['cases']}
    ids = comparison['case_ids'][:-1] if drop_last else comparison['case_ids']
    if len(ids) != len(comparison['case_ids']):
        raise ValueError('Missing comparison source receipt')
    receipts = []
    for case in ids:
        entry = entries[case]
        path = ROOT / entry['compatibility']['receipt']
        if sha(path) != entry['compatibility']['sha256']:
            raise ValueError('Comparison source receipt hash changed')
        receipt = json.loads(path.read_text())
        if (receipt.get('passed') is not True or receipt.get('case_id') != case or
                receipt.get('construction_sha256') != entry['construction_sha256'] or
                value(receipt, 'source_topic_0').get('review_kind') != 'synthetic_diagnostic'):
            raise ValueError('Comparison source identity/provenance differs')
        receipts.append(receipt)
    speeds = [value(receipt, 'source_topic_0')['maximum_observed_mph_in_zone']
              for receipt in receipts]
    observations = [value(receipt, 'source_topic_0') for receipt in receipts]
    common_sources = ('video_frames.jsonl', 'children_context.jsonl',
                      'overview.mkv', 'approach.mkv',
                      'reference_corner.mkv', 'driver_reference.mkv')
    for source in common_sources:
        if len({item['sources'][source] for item in observations}) != 1:
            raise ValueError('Comparison changed fixed source: ' + source)
    for field in ('sample_count', 'sample_span_s', 'civil_start_iso',
                  'civil_end_iso', 'review_kind'):
        if len({item[field] for item in observations}) != 1:
            raise ValueError('Comparison changed fixed observation: ' + field)
    if any(item['sample_count'] != 600 or item['review_kind'] != 'synthetic_diagnostic'
           for item in observations):
        raise ValueError('Comparison lacks exact diagnostic sampling')
    suffix = comparison_id.rsplit('__', 1)[-1]
    if suffix == 'speed_boundary':
        passed = speeds == [20, 25, 30] and all(
            not any(value(receipt, 'source_topic_0')['reviewed_exception_facts'].values())
            for receipt in receipts)
        changed = 'measured_speed_mph'
    else:
        if speeds != [30, 30]:
            raise ValueError('Exception comparison changed measured speed')
        if len({item['sources']['native_motion.jsonl'] for item in observations}) != 1:
            raise ValueError('Exception comparison changed fixed motion source')
        key, field = {
            'no_school_day': ('source_topic_1', 'school_session_day'),
            'half_hour_window': ('source_topic_2', 'half_hour_window_exception'),
            'beacon_flash': ('source_topic_3', 'beacon_flashing'),
            'nonbeacon_sign': ('source_topic_4', 'nonbeacon_sign_in_effect'),
        }[suffix]
        states = [value(receipt, key)[field] for receipt in receipts]
        passed = states[0] != states[1]
        fact_key = {'no_school_day': 'school_not_in_session',
                    'half_hour_window': 'half_hour_window',
                    'beacon_flash': 'operational_beacon_nonflashing_class_hours',
                    'nonbeacon_sign': 'nonbeacon_sign_off'}[suffix]
        facts = [item['reviewed_exception_facts'] for item in observations]
        if any(any(value for name, value in row.items() if name != fact_key)
               for row in facts) or facts[0][fact_key] == facts[1][fact_key]:
            raise ValueError('Exception comparison changed another statutory branch')
        changed = field
    if not passed:
        raise ValueError('Comparison did not isolate the selected source variable')
    return {'comparison_id': comparison_id, 'case_ids': ids, 'measured_speeds_mph': speeds,
            'isolated_variable': changed, 'source_receipt_sha256': {
                case: entry['compatibility']['sha256'] for case, entry in
                ((case, entries[case]) for case in ids)},
            'passed': True, 'scope': 'synthetic source comparison only; no legal verdict'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--negative-drop-last', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.comparison, args.negative_drop_last), sort_keys=True))


if __name__ == '__main__':
    main()

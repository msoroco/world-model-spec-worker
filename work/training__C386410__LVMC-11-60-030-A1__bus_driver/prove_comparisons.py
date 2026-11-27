"""CPU comparison proof across seven source-joined synthetic Native samples."""
import hashlib
import json
from pathlib import Path
from comparison_audit import audit

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / 'proofs' / 'comparisons'
SAVED = ROOT / '.runtime-work' / 'c386410-saved'
VARIANT = ROOT / '.runtime-work' / 'c386410-variant-saved'
ROOTS = {name: VARIANT / name / 'attempt' for name in ('bus_stop', 'bus_stand', 'route_origin', 'transient_stop', 'parking_other_street', 'tour_bus_other_street')}
ROOTS['designated_terminus'] = SAVED / 'designated-attempt-r2'
ROOTS['undesignated_street'] = SAVED / 'undesignated-attempt-r1'
PAIRS = (
    ('location_terminus', 'designated_terminus', 'undesignated_street'),
    ('location_bus_stop', 'bus_stop', 'undesignated_street'),
    ('location_bus_stand', 'bus_stand', 'undesignated_street'),
    ('location_origin', 'route_origin', 'undesignated_street'),
    ('standing_event', 'undesignated_street', 'transient_stop'),
    ('parking_event', 'parking_other_street', 'transient_stop'),
    ('tour_bus_exclusion', 'undesignated_street', 'tour_bus_other_street'),
)

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, left, right in PAIRS:
        positive = audit(ROOTS[left], ROOTS[right], name, source_kind='synthetic_native_sample')
        assert positive['passed'] and positive['legal_judgment'] == 'unresolved'
        try:
            audit(ROOTS[right], ROOTS[left], name, source_kind='synthetic_native_sample')
        except ValueError as exc:
            negative = str(exc)
            assert 'difference absent or reversed' in negative
        else:
            raise AssertionError('reversed difference accepted: ' + name)
        record = {'format': 'bus-comparison-proof-v1', 'comparison_id': name,
                  'case_ids': [left, right], 'source_kind': 'synthetic_native_sample',
                  'positive': {'passed': True, 'difference': positive['deliberate_difference'],
                               'context_sha256': positive['context_sha256'],
                               'source_sha256': [m['source_sha256'] for m in positive['measurements']]},
                  'negative': {'reversed_pair_rejected': True, 'error': negative},
                  'physical_acceptance_claimed': False, 'legal_judgment': 'unresolved'}
        path = OUT / (name + '.json')
        path.write_text(json.dumps(record, indent=2) + '\n')
        print(name, hashlib.sha256(path.read_bytes()).hexdigest())

if __name__ == '__main__':
    main()

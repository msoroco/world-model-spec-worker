"""Author source-bound measurement contracts for the sixteen long cases."""
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PLAN = json.loads((ROOT / 'case-plan.json').read_text())
SLUGS = tuple(f'{service}_{boundary}' for service in (
    'tour_bus', 'shuttle_bus', 'limo', 'rtc_bus') for boundary in (
    'below', 'at', 'above', 'no_loading'))


def main():
    out = ROOT / 'selected-measurement-contracts'
    out.mkdir(exist_ok=True)
    cases = {case['case_id']: case for case in PLAN['cases']}
    for slug in SLUGS:
        case_id = ROOT.name + '__' + slug
        if case_id not in cases:
            raise ValueError('Long case absent from selected plan: ' + slug)
        index = 5 if slug.startswith('rtc_bus_') else 4
        clause = PLAN['requirement_dispositions'][index]
        if case_id not in clause['case_ids']:
            raise ValueError('Long case has another clause: ' + slug)
        participant = ('native-passenger-inventory.jsonl' if slug.endswith('_no_loading')
                       else 'native-passenger-actors.jsonl')
        contract = {
            'format': 'worker-measurement-contract', 'case_id': case_id,
            'requirements': [{
                'source': clause['source'], 'disposition_index': index,
                'requirement': clause['requirement'],
                'output_key': 'signed_curb_observation',
                'method': 'signed_context', 'value_type': 'object',
                'kind': 'measured',
                'inputs': ['native-raw-actors.jsonl', 'native-map-readback.json',
                           participant]}],
            'negative': {'remove': [participant],
                         'error_contains': 'Missing required source: ' + participant},
            'scope': ('Measured synthetic curb duration, source-bound sign and '
                      'passenger activity; actual service identity, boarding, '
                      'physical acceptance and legal verdict unverified')}
        (out / (slug + '.json')).write_text(
            json.dumps(contract, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'long_cases': len(SLUGS), 'source_kind': 'synthetic_native_sample'}))


if __name__ == '__main__':
    main()

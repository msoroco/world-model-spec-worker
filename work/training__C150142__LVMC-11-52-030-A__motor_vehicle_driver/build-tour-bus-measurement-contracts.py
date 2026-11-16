"""Bind each authored text-4 tour-bus probe to retained Native source channels."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CASES = ('tour_bus_below', 'tour_bus_at', 'tour_bus_above',
         'tour_bus_no_loading')


def build():
    for suffix in CASES:
        no_loading = suffix == 'tour_bus_no_loading'
        passenger_source = ('native-passenger-inventory.jsonl' if no_loading else
                            'native-passenger-actors.jsonl')
        sources = ['native-raw-actors.jsonl', 'native-map-readback.json',
                   passenger_source]
        contract = {
            'format': 'worker-measurement-contract',
            'case_id': ROOT.name + '__' + suffix,
            'requirements': [{
                'disposition_index': 4,
                'requirement': 'text-4',
                'source': 'inputs/coverage/branch-sources.json',
                'output_key': 'signed_curb_observation',
                'method': 'signed_context',
                'value_type': 'object',
                'kind': 'measured',
                'inputs': sources,
            }],
            'negative': {'remove': [passenger_source],
                         'error_contains': 'Missing required source: ' + passenger_source},
            'scope': ('Observed tour-bus, signed red curb, 20 Hz stopped interval and ' +
                      ('absence of passenger actor' if no_loading else
                       'source-derived passenger approach') +
                      '; no physical acceptance or legal verdict'),
        }
        target = (ROOT / 'selected-primary' / suffix /
                  'selected-measurement-contracts' / (suffix + '.json'))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(contract, indent=2) + '\n')
    return CASES


if __name__ == '__main__':
    print(json.dumps(build()))

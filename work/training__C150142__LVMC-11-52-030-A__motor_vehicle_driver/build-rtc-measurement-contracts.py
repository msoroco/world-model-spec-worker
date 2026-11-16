"""Bind signed RTC bus boundary probes to retained Native source rows."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def build():
    outputs = []
    for boundary in ('below', 'at', 'above', 'no_loading'):
        case = 'rtc_bus_' + boundary
        passenger = ('native-passenger-inventory.jsonl' if boundary == 'no_loading'
                     else 'native-passenger-actors.jsonl')
        contract = {
            'format': 'worker-measurement-contract',
            'case_id': ROOT.name + '__' + case,
            'requirements': [{
                'disposition_index': 5,
                'requirement': 'text-5',
                'source': 'inputs/coverage/branch-sources.json',
                'output_key': 'signed_curb_observation',
                'method': 'signed_context',
                'value_type': 'object',
                'kind': 'measured',
                'inputs': ['native-raw-actors.jsonl', 'native-map-readback.json',
                           passenger],
            }],
            'negative': {'remove': [passenger],
                         'error_contains': 'Missing required source: ' + passenger},
            'scope': ('Observed bus chassis with authored RTC service identity, '
                      'RTC-only sign and 20 Hz stopped interval; '
                      'no physical acceptance or legal verdict'),
        }
        target = (ROOT / 'selected-primary' / case /
                  'selected-measurement-contracts' / (case + '.json'))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(contract, indent=2) + '\n')
        outputs.append(str(target.relative_to(ROOT)))
    return outputs


if __name__ == '__main__':
    print(json.dumps(build()))

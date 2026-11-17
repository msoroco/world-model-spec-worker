"""Draft text-4 measurement contracts for provisional limo-service cases."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def build():
    records = []
    for boundary in ('below', 'at', 'above', 'no_loading'):
        source = (ROOT / 'selected-primary' / ('shuttle_bus_' + boundary) /
                  'selected-measurement-contracts' /
                  ('shuttle_bus_' + boundary + '.json'))
        contract = json.loads(source.read_text())
        if (contract['requirements'][0]['requirement'] != 'text-4' or
                contract['requirements'][0]['disposition_index'] != 4):
            raise ValueError('Source text-4 measurement contract changed')
        case = 'limo_' + boundary
        contract['case_id'] = ROOT.name + '__' + case
        contract['scope'] = (
            'Source-derived red curb, sign, sedan motion and passenger activity '
            'with authored provisional limo-service identity; the Lincoln MKZ '
            'does not establish a limousine body, licensing or service. '
            'No physical acceptance or legal verdict.')
        output = ROOT / 'selected-primary' / case / 'selected-measurement-contracts' / (case + '.json')
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(contract, indent=2, allow_nan=False) + '\n')
        records.append({'case_id': contract['case_id'],
                        'contract': str(output.relative_to(ROOT)),
                        'sha256': hashlib.sha256(output.read_bytes()).hexdigest()})
    return records


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))

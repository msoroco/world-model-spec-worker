"""Author slower risk-triggered fallback for each exact towing sweep case."""
import copy
import hashlib
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
MANIFEST = PACKAGE / 'towing-sweep-diagnostic-manifest.json'


def build():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        primary = json.loads((PACKAGE / entry['construction']).read_text())
        fallback = copy.deepcopy(primary)
        config_file = next(item for item in fallback['files'] if item['path'] == 'config.json')
        config = json.loads(config_file['content'])
        old_cap = config.get('target_speed_cap_mps')
        if old_cap != 4:
            raise ValueError('Expected exact primary 4 m/s cap')
        config['target_speed_cap_mps'] = 2.5
        config_file['content'] = json.dumps(config, indent=2) + '\n'
        path = PACKAGE / 'cases' / (entry['case_id'] + '-fallback1-construction.json')
        path.write_text(json.dumps(fallback, indent=2) + '\n')
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        entry['candidate_risk'] = {
            'status': 'physical',
            'reason': 'The entrant may contact the drawn unit or brake abruptly before the selected gap.'}
        entry['candidates'] = [{
            'id': 'fallback1', 'construction': 'cases/' + path.name,
            'construction_sha256': digest,
            'changed_knobs': ['target_speed_cap_mps: 4 to 2.5'],
            'trigger': {'source': 'original Native per-frame control and drawn-body history',
                        'metric': 'entrant contact or emergency brake before selected gap',
                        'failure_condition': 'contact with drawn unit or abrupt full brake before planned approach'}}]
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'fallback_count': len(manifest['cases'])}))


if __name__ == '__main__':
    build()

"""Author a slower exact towing candidate without changing capture identity."""
import hashlib
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
PRIMARY = PACKAGE / 'cases/towed_entrant_can_occupy_gap-construction.json'
FALLBACK = PACKAGE / 'cases/towed_entrant_can_occupy_gap-fallback1-construction.json'
MANIFEST = PACKAGE / 'towing-diagnostic-manifest.json'


def main():
    construction = json.loads(PRIMARY.read_text())
    config_file = next(item for item in construction['files'] if item['path'] == 'config.json')
    config = json.loads(config_file['content'])
    config['target_speed_cap_mps'] = 2.5
    config_file['content'] = json.dumps(config, indent=2) + '\n'
    FALLBACK.write_text(json.dumps(construction, indent=2) + '\n')
    digest = hashlib.sha256(FALLBACK.read_bytes()).hexdigest()
    manifest = json.loads(MANIFEST.read_text())
    entry = manifest['cases'][0]
    entry['candidate_risk'] = {'status': 'physical',
                               'reason': 'The entrant may contact the drawn unit or brake abruptly during entry.'}
    entry['candidates'] = [{
        'id': 'fallback1', 'construction': 'cases/' + FALLBACK.name,
        'construction_sha256': digest,
        'changed_knobs': ['target_speed_cap_mps: absent to 2.5'],
        'trigger': {'source': 'original Native per-frame control and drawn-body history',
                    'metric': 'entrant contact or emergency brake before gap approach',
                    'failure_condition': 'contact with drawn unit or abrupt full brake before planned merge'}}]
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'fallback1_construction_sha256': digest,
                      'same_case_id': construction['case_id']}))


if __name__ == '__main__':
    main()

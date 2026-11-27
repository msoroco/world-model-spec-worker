"""Author one measurable traffic-spacing fallback for each exact entry case."""
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
manifest_path = ROOT / 'execution-manifest.json'
manifest = json.loads(manifest_path.read_text())
for entry in manifest['cases']:
    suffix = entry['case_id'][-1]
    source = ROOT / entry['construction']
    alternate = json.loads(source.read_text())
    for item in alternate['files']:
        if item['path'] == 'config.json':
            config = json.loads(item['content'])
            assert config['candidate_id'] == 'near_80'
            config['candidate_id'] = 'near_90'
            item['content'] = json.dumps(config, indent=2) + '\n'
    target = ROOT / 'cases' / ('condition_' + suffix) / 'fallback1.json'
    target.write_text(json.dumps(alternate, indent=2, ensure_ascii=False) + '\n')
    entry['candidates'] = [{
        'id': 'fallback1', 'construction': target.relative_to(ROOT).as_posix(),
        'construction_sha256': sha256(target.read_bytes()).hexdigest(),
        'trigger': {'source': 'original Native actor and camera history',
                    'metric': 'through-vehicle overlap or camera loss at the proposed merge',
                    'failure_condition': 'primary near_80 vehicle placement prevents complete physical entry or visible original capture'},
        'changed_knobs': ['near_80 to near_90 initial through-vehicle placement; same controller setting, route, participants, duration and four cameras'],
    }]
manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps({e['case_id']: e['candidates'][0]['construction_sha256'] for e in manifest['cases']}))

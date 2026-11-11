"""Three distinct source-triggered alternatives per exact C10364 alley case."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path


root = Path(__file__).resolve().parent
manifest_path = root / 'probe-compatibility-manifest.json'
manifest = json.loads(manifest_path.read_text())
fallbacks = [
    ('fallback1', 'alley_direction', 'west',
     'select opposite travel direction inside the same sourced polygon',
     {'source': 'road.xodr and construction-probe.json',
      'metric': 'connected eastbound route selection',
      'failure_condition': 'No eastbound connected route remains inside the selected alley polygon'}),
    ('fallback2', 'route_lookahead_steps', 3,
     'reduce controller lookahead by one 2.5 m waypoint',
     {'source': 'trace.jsonl and participant_footprints.jsonl',
      'metric': 'original subject lane tracking error',
      'failure_condition': 'Subject leaves the mapped alley corridor before passing the participant'}),
    ('fallback3', 'overview_height_delta_m', 2,
     'raise overview camera mount by 2 m',
     {'source': 'overview.mkv and video_frames.jsonl',
      'metric': 'original pedestrian/property visibility in overview frames',
      'failure_condition': 'Relevant person or property is occluded or outside the original overview camera field'})]
for entry in manifest['cases']:
    primary = json.loads((root / entry['construction']).read_text())
    suffix = entry['case_id'].split('__')[-1]
    entry['candidate_risk'] = {'status': 'physical',
        'reason': 'Alley route connectivity, lane tracking and original overview visibility may fail on the selected Native map.'}
    entry['candidates'] = []
    for ident, knob, value, change, trigger in fallbacks:
        candidate = deepcopy(primary)
        config = json.loads(next(item['content'] for item in candidate['files']
                                 if item['path'] == 'config.json'))
        config[knob] = value
        next(item for item in candidate['files'] if item['path'] == 'config.json')['content'] = (
            json.dumps(config, indent=2) + '\n')
        path = root / 'cases' / ('construction-' + suffix + '-' + ident + '.json')
        path.write_text(json.dumps(candidate, indent=2) + '\n')
        entry['candidates'].append({'id': ident,
            'construction': str(path.relative_to(root)),
            'construction_sha256': sha256(path.read_bytes()).hexdigest(),
            'changed_knobs': [change], 'trigger': trigger})
manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
print('Built three distinct alternatives for each of ' + str(len(manifest['cases'])) + ' exact alley cases')

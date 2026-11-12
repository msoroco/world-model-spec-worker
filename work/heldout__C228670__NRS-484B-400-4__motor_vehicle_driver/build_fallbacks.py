"""Bind three distinct physical-risk alternatives for each exact turn case."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / 'probe-compatibility-manifest.json'
FALLBACKS = (
    ('fallback1', 'route_step_m', 1.0, 'Use one-meter connected route sampling',
     {'source': 'road.xodr and original route/trace readback',
      'metric': 'connected junction and destination route at one-meter waypoint spacing',
      'failure_condition': 'Two-meter sampling skips the intended connected left-turn route'}),
    ('fallback2', 'turn_throttle', .16, 'Lower turn throttle to 0.16',
     {'source': 'trace.jsonl and body_footprints.jsonl',
      'metric': 'original departure completion and body-corner side after turn',
      'failure_condition': 'Primary turn speed overshoots the intended right-of-centerline departure'}),
    ('fallback3', 'overview_height_delta_m', 2.0, 'Raise the overview camera by two meters',
     {'source': 'overview.mkv and video_frames.jsonl',
      'metric': 'original left curb and entered-road centerline visibility',
      'failure_condition': 'Primary overview hides the source curb or entered centerline'}),
)


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    (ROOT / 'cases').mkdir(exist_ok=True)
    probe = []
    for entry in manifest['cases']:
        primary = json.loads((ROOT / entry['construction']).read_text())
        entry['candidate_risk'] = {'status': 'physical',
            'reason': 'Native route connectivity, turn speed and original curb/centerline camera visibility may fail.'}
        entry['candidates'] = []
        probe.append({'case_id': entry['case_id'], 'construction': entry['construction'],
                      'construction_sha256': entry['construction_sha256']})
        slug = entry['case_id'].split('__')[-1]
        for identifier, knob, value, changed, trigger in FALLBACKS:
            candidate = deepcopy(primary)
            config_item = next(row for row in candidate['files'] if row['path'] == 'config.json')
            config_item.pop('source', None)
            config = json.loads(config_item['content'])
            config[knob] = value
            config_item['content'] = json.dumps(config, indent=2) + '\n'
            path = ROOT / 'cases' / ('construction-' + slug + '-' + identifier + '.json')
            write(path, candidate)
            entry['candidates'].append({'id': identifier,
                'construction': str(path.relative_to(ROOT)),
                'construction_sha256': digest(path),
                'changed_knobs': [changed], 'trigger': trigger})
    write(MANIFEST, manifest)
    write(ROOT / 'construction-probe-manifest.json', {
        'format': 'worker-construction-cases', 'assignment_id': ROOT.name,
        'cases': probe})
    print('Bound three primary turns and nine distinct physical-risk fallbacks')


if __name__ == '__main__':
    main()

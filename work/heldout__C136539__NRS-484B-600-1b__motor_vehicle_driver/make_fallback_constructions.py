"""Build three distinct physical-risk fallback probes for each exact exposure case.

The alternatives keep the case, requested speed, exposed body and capture
contract fixed. They only change route search, steering lookahead or the
overview camera mount to address a failed construction observation.
"""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VARIANTS = (
    ('fallback1', 'native_exposure_cases.py',
     'select_route(world.get_map(), steps=40)',
     'select_route(world.get_map(), steps=36)',
     'shorten connected route search to 90 m',
     {'source': 'construction-probe.json', 'metric': 'connected route selection',
      'failure_condition': 'No connected 100 m narrow-road route at the selected spawn point'}),
    ('fallback2', 'native_exposure_cases.py',
     'min(4 + index // 4, len(route) - 1)',
     'min(3 + index // 4, len(route) - 1)',
     'reduce controller lookahead by one 2.5 m waypoint',
     {'source': 'trace.jsonl and exposed_actor_footprints.jsonl',
      'metric': 'original subject path tracking error',
      'failure_condition': 'Subject drifts from the selected driving lane before the exposure window'}),
    ('fallback3', 'exposure_camera.py',
     '"overview": ((-8, 0, 8),',
     '"overview": ((-8, 0, 10),',
     'raise overview mount by 2 m',
     {'source': 'overview.mkv and video_frames.jsonl',
      'metric': 'exposed actor visibility in original overview frames',
      'failure_condition': 'Exposed actor is occluded or outside the original overview camera field'}),
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    primary = json.loads((ROOT / 'probe-compatibility-manifest.json').read_text())
    manifest_path = ROOT / 'fallback-constructions-manifest.json'
    previous = json.loads(manifest_path.read_text()) if manifest_path.is_file() else {'cases': []}
    previous_cases = {entry['case_id']: entry for entry in previous['cases']}
    for entry in primary['cases']:
        source = json.loads((ROOT / entry['construction']).read_text())
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        entry['candidate_risk'] = {
            'status': 'physical',
            'reason': 'Connected narrow-road spawn, subject tracking and original camera visibility can fail in Native simulation.'}
        entry['candidates'] = []
        for ident, file_name, old, new, change, trigger in VARIANTS:
            construction = json.loads(json.dumps(source))
            target = next(item for item in construction['files'] if item['path'] == file_name)
            if target['content'].count(old) != 1:
                raise ValueError(f'Expected one engineering knob in {file_name}')
            target['content'] = target['content'].replace(old, new)
            if file_name == 'native_exposure_cases.py':
                next(item for item in construction['files'] if item['path'] == 'runner.py')['content'] = target['content']
            construction['mechanisms'].append(change)
            construction_path = ROOT / 'cases' / f'construction-{suffix}-{ident}.json'
            construction_path.write_text(json.dumps(construction, indent=2) + '\n')
            candidate = {
                'id': ident, 'construction': str(construction_path.relative_to(ROOT)),
                'construction_sha256': sha(construction_path), 'changed_knobs': [change],
                'trigger': trigger}
            for prior in previous_cases.get(entry['case_id'], {}).get('candidates', []):
                if prior.get('id') == ident and prior.get('construction_sha256') == candidate['construction_sha256']:
                    for proof in ('offline', 'compatibility'):
                        if proof in prior:
                            candidate[proof] = prior[proof]
            entry['candidates'].append(candidate)
    manifest_path.write_text(json.dumps(primary, indent=2) + '\n')
    return manifest_path


if __name__ == '__main__':
    print(build())

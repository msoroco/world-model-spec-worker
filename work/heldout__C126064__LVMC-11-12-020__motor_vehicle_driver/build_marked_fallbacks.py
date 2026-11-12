"""Build three physically distinct marked-turn candidates for both exact cases."""
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CANDIDATES = (
    ('fallback1', 'native_runner.py', 'waypoint.transform.location.z + .5',
     'waypoint.transform.location.z + .7',
     'spawn_height_offset_m', .7,
     'Original Native ego spawn readback', 'spawn success at selected road point',
     'Primary 0.5 m height offset intersects the road or fails actor spawn'),
    ('fallback2', 'marked_course_native.py', 'target_speed_mps=4.):',
     'target_speed_mps=3.5):',
     'target_speed_mps', 3.5,
     'Original Native turn body and controller history', 'target overshoot or turn completion',
     'Primary 4 m/s target overshoots a marked course target before the fixed capture ends'),
    ('fallback3', 'marked_course_native.py', "'overview': ((-8, 0, 8)",
     "'overview': ((-10, 0, 8)",
     'overview_x_m', -10,
     'Original overview camera frames', 'physical marker pixel visibility',
     'Primary overview mount does not show the physical indicated marker'),
)


def put(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')
    return sha256(path.read_bytes()).hexdigest()


def build():
    manifest_path = ROOT / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest['cases']:
        base = json.loads((ROOT / entry['construction']).read_text())
        short = entry['case_id'].rsplit('__', 1)[-1]
        existing = {item['id']: item for item in entry.get('candidates', [])}
        candidates = []
        for candidate_id, module, before, after, knob, value, source, metric, failure in CANDIDATES:
            proposal = json.loads(json.dumps(base))
            files = {item['path']: item for item in proposal['files']}
            text = files[module]['content']
            if text.count(before) != 1:
                raise ValueError('Candidate source edit is ambiguous: ' + candidate_id)
            files[module]['content'] = text.replace(before, after)
            config = json.loads(files['config.json']['content'])
            config['engineering'][knob] = value
            files['config.json']['content'] = json.dumps(config, indent=2) + '\n'
            path = ROOT / f'{short}-{candidate_id}-construction.json'
            digest = put(path, proposal)
            prior = existing.get(candidate_id, {})
            if prior.get('construction_sha256') != digest:
                prior = {'id': candidate_id, 'construction': path.name,
                         'construction_sha256': digest,
                         'changed_knobs': [f'{knob}={value}'],
                         'trigger': {'source': source, 'metric': metric,
                                     'failure_condition': failure}}
            candidates.append(prior)
        entry['candidates'] = candidates
    put(manifest_path, manifest)
    return {entry['case_id']: {item['id']: item['construction_sha256']
                               for item in entry['candidates']}
            for entry in manifest['cases']}


if __name__ == '__main__':
    print(build())

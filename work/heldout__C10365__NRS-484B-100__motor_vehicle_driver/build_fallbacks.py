"""Bind current source and three physical-risk alternatives to each officer case."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / 'probe-compatibility-manifest.json'
SOURCES = ('runner.py', 'officer_native_runner.py', 'officer_camera_capture.py',
           'officer_response.py', 'officer_finalizer.py',
           'tests/test_officer_finalizer.py', 'tests/test_officer_native_runner.py',
           'tests/test_officer_response.py', 'officer_comparison_audit.py')
FALLBACKS = (
    ('fallback1', 'route_distance_m', 12.0, 'Use a 12 m connected alley segment',
     {'source': 'road.xodr and original trace.jsonl',
      'metric': 'connected nonjunction alley segment length and subject route',
      'failure_condition': 'The selected 18 m segment cannot be connected inside the Native alley'}),
    ('fallback2', 'pose_pitch_delta_deg', 20.0, 'Raise the original officer arm pose by 20 degrees',
     {'source': 'officer_direction.json and all four original camera streams',
      'metric': 'officer arm visibility and command distinction in actual pixels',
      'failure_condition': 'The primary arm pose is obscured or indistinct at the captured frame'}),
    ('fallback3', 'overview_height_delta_m', 2.0, 'Raise the overview camera mount by 2 m',
     {'source': 'overview.mkv and video_frames.jsonl',
      'metric': 'officer and subject visibility in original overview frames',
      'failure_condition': 'The officer or subject is occluded or outside the original overview field'}),
)


def write(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def bind_source(bundle):
    for item in bundle['files']:
        if item['path'] in SOURCES:
            item['content'] = (ROOT / item['path']).read_text()


def main():
    manifest = json.loads(MANIFEST.read_text())
    root = ROOT / 'construction.json'
    root_bundle = json.loads(root.read_text())
    bind_source(root_bundle)
    write(root, root_bundle)
    probes = []
    for entry in manifest['cases']:
        primary_path = ROOT / entry['construction']
        primary = json.loads(primary_path.read_text())
        bind_source(primary)
        write(primary_path, primary)
        entry['construction_sha256'] = digest(primary_path)
        probes.append({'case_id': entry['case_id'], 'construction': entry['construction'],
                       'construction_sha256': entry['construction_sha256']})
        suffix = entry['case_id'].split('__')[-1]
        entry['candidate_risk'] = {
            'status': 'physical',
            'reason': 'Native alley connectivity, actual officer gesture visibility and original overview coverage may fail.'}
        entry['candidates'] = []
        for ident, knob, value, change, trigger in FALLBACKS:
            candidate = deepcopy(primary)
            config_item = next(row for row in candidate['files'] if row['path'] == 'config.json')
            config = json.loads(config_item['content'])
            config[knob] = value
            config_item['content'] = json.dumps(config, indent=2) + '\n'
            path = ROOT / 'cases' / f'construction-{suffix}-{ident}.json'
            write(path, candidate)
            entry['candidates'].append({'id': ident,
                'construction': str(path.relative_to(ROOT)),
                'construction_sha256': digest(path),
                'changed_knobs': [change], 'trigger': trigger})
    write(MANIFEST, manifest)
    write(ROOT / 'construction-probe-manifest.json', {
        'format': 'worker-construction-cases', 'assignment_id': ROOT.name, 'cases': probes})
    print('Bound seven primaries and twenty-one distinct officer fallback constructions')


if __name__ == '__main__':
    main()

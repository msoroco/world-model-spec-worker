"""Source-shaped device-candidate fixtures; no official or legal finding."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
REPO = HERE.parent.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def build():
    manifest = json.loads((HERE / 'device-execution-manifest.json').read_text())
    for state in ('absent', 'present'):
        name = 'official_device_' + state
        source = HERE / 'diagnostic-source' / name
        source.mkdir(parents=True, exist_ok=True)
        previous = HERE / 'diagnostic-source' / ('officer_direction_' + state)
        authority = json.loads((previous / 'authority-context.json').read_text())
        authority = {
            'source_kind': 'synthetic_cpu',
            'device_presence_requested': state == 'present',
            'device_trace_source': 'device-trace.jsonl',
            'device_candidate_trajectory': {
                'source': 'device-trace.jsonl',
                'candidate_present_requested': state == 'present',
                'identity_and_direction_independently_verified': False},
            'official_status_verified': False,
            'direction_observed': None,
            'direction_time_window_s': None,
            'other_law_authority': None,
            'officer_direction': None,
            'official_device_direction': None,
            'exception_independently_verified': False,
            'exception_authority_context': {
                'source': 'synthetic traffic-device prop request shape; official status and direction unreviewed',
                'independently_verified': False}}
        dump(source / 'authority-context.json', authority)
        lines = []
        for line in (previous / 'officer-trace.jsonl').read_text().splitlines():
            row = json.loads(line)
            if state == 'present':
                row['blueprint_id'] = 'static.prop.trafficwarning.synthetic'
                row['position_m'] = [37.0, -5.0, 0.5]
            row['official_status_verified'] = False
            row.pop('identity_verified')
            lines.append(json.dumps(row, sort_keys=True))
        (source / 'device-trace.jsonl').write_text('\n'.join(lines) + '\n')
        recipe = json.loads((HERE / ('diagnostic-recipe-officer_direction_' + state + '.json')).read_text())
        recipe['sources'] = [item for item in recipe['sources']
                             if item['path'] not in ('authority-context.json', 'officer-trace.jsonl')]
        for filename in ('authority-context.json', 'device-trace.jsonl'):
            path = source / filename
            recipe['sources'].append({'path': filename,
                'source': str(path.relative_to(REPO)), 'sha256': sha(path)})
        dump(HERE / ('diagnostic-recipe-' + name + '.json'), recipe)
        entry = next(item for item in manifest['cases'] if item['case_id'].endswith('__' + name))
        entry['fixture_recipe'] = str((HERE / ('diagnostic-recipe-' + name + '.json')).relative_to(REPO))
    dump(HERE / 'device-execution-manifest.json', manifest)


if __name__ == '__main__':
    build()

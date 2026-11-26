"""Build source-shaped officer candidate fixtures without claiming authority."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def build(suffix):
    present = suffix.endswith('_present')
    source = HERE / 'diagnostic-source' / suffix
    authority = {
        'source_kind': 'synthetic_cpu',
        'officer_presence_requested': present,
        'officer_trace_source': 'officer-trace.jsonl',
        'officer_candidate_trajectory': {
            'source': 'officer-trace.jsonl',
            'candidate_present_requested': present,
            'identity_and_direction_independently_verified': False},
        'officer_identity_verified': False,
        'direction_observed': None,
        'direction_time_window_s': None,
        'other_law_authority': None,
        'officer_direction': None,
        'official_device_direction': None,
        'exception_independently_verified': False,
        'exception_authority_context': {
            'source': 'synthetic officer-presence request shape',
            'independently_verified': False}}
    dump(source / 'authority-context.json', authority)
    lines = []
    for frame in range(600):
        row = {'frame': frame, 'native_frame': 100 + frame,
               'time_s': frame / 20, 'actor_id': 108 if present else None,
               'blueprint_id': 'walker.pedestrian.synthetic' if present else None,
               'position_m': [37.0, -5.0, 1.0] if present else None,
               'identity_verified': False, 'direction_observed': None,
               'source_kind': 'synthetic_cpu'}
        lines.append(json.dumps(row, separators=(',', ':')))
    (source / 'officer-trace.jsonl').write_text('\n'.join(lines) + '\n')
    original = json.loads((HERE / 'diagnostic-recipe-probe_2.json').read_text())
    sources = [item for item in original['sources']
               if item['path'] != 'authority-context.json']
    for name in ('authority-context.json', 'officer-trace.jsonl'):
        path = source / name
        sources.append({'path': name, 'source': str(path.relative_to(REPO)),
                        'sha256': sha(path)})
    recipe = {'format': 'worker-fixture-recipe',
              'sources': sources, 'generator': original['generator']}
    output = HERE / ('diagnostic-recipe-' + suffix + '.json')
    dump(output, recipe)
    return {'recipe': str(output.relative_to(REPO)), 'sha256': sha(output)}


if __name__ == '__main__':
    print(json.dumps([build(suffix) for suffix in (
        'officer_direction_absent', 'officer_direction_present')]))

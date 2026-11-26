"""Inventory synthetic trace shapes for the selected traffic comparison."""
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
        'traffic_conflict_requested': present,
        'traffic_conflict_source': 'traffic-trace.jsonl',
        'traffic_conflict_independently_verified': False,
        'other_traffic_trajectory': {
            'source': 'traffic-trace.jsonl',
            'participant_present_requested': present,
            'independently_verified': False},
        'other_law_authority': None,
        'officer_direction': None,
        'official_device_direction': None,
        'exception_independently_verified': False,
        'exception_authority_context': {
            'source': 'synthetic other-traffic request shape',
            'independently_verified': False}}
    dump(source / 'authority-context.json', authority)
    rows = []
    for frame in range(600):
        row = {'frame': frame, 'native_frame': 100 + frame,
               'time_s': frame / 20}
        if present:
            row.update(actor_id=108, blueprint_id='vehicle.synthetic.other',
                       position_m=[38.0, -1.75, 0.0], speed_mps=0.0,
                       actor_pose_source='synthetic_post_tick_shape')
        else:
            row['traffic_actor_present'] = False
        rows.append(json.dumps(row, separators=(',', ':')))
    (source / 'traffic-trace.jsonl').write_text('\n'.join(rows) + '\n')
    original = json.loads((HERE / 'diagnostic-recipe-probe_2.json').read_text())
    sources = [item for item in original['sources']
               if item['path'] != 'authority-context.json']
    for name in ('authority-context.json', 'traffic-trace.jsonl'):
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
        'traffic_conflict_absent', 'traffic_conflict_present')]))

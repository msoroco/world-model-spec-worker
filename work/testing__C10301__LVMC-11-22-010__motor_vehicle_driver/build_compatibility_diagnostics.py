"""Create explicit diagnostic-only text, graph and video recipes for both alley cases."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BASE = json.loads((REPO / 'runtime/fixtures/example.json').read_text())
SCRATCH = REPO / '.runtime-work/c10301-010-nov24b'

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def build(kind: str) -> None:
    case = HERE.name + '__' + kind
    source = SCRATCH / ('full900-attempt' if kind == 'steady_travel' else 'full900-variation-attempt')
    spec = json.loads(json.dumps(BASE))
    example_case = json.loads(spec['files']['capture/manifest.json'])['case_id']
    spec['files'] = {key: value.replace(example_case, case) for key, value in spec['files'].items()}
    manifest = json.loads(spec['files']['capture/manifest.json'])
    manifest['source_run'] = 'CPU diagnostic fixture; no original alley recording'
    spec['files']['capture/manifest.json'] = json.dumps(manifest, sort_keys=True) + '\n'
    spec['files']['fixture-provenance.json'] = json.dumps({
        'scope': 'CPU diagnostic only; source-shaped example graph and generated FFV1 video; no original Native pixels or legal finding',
        'example_source_sha256': sha(REPO / 'runtime/fixtures/example.json'),
        'case_id': case}, sort_keys=True) + '\n'
    spec['files']['acquisition-provenance.json'] = json.dumps({
        'provenance_kind': 'fixture', 'diagnostic_fixture': True,
        'source': 'source-shaped CPU example plus exact alley operation rows; no original Native pixels'}, sort_keys=True) + '\n'
    frames = [json.loads(s) for s in spec['files']['trace.jsonl'].splitlines()]
    rows = {}
    for name in ('ego.jsonl', 'context.jsonl', 'operation.jsonl'):
        rows[name] = [json.loads(s) for s in (source / name).read_text().splitlines()[:len(frames)]]
    for index, frame in enumerate(frames):
        for name in ('ego.jsonl', 'context.jsonl'):
            rows[name][index]['native_frame'] = frame['frame']
            rows[name][index]['native_time_s'] = frame['time_s']
        rows['operation.jsonl'][index]['case_id'] = case
        rows['operation.jsonl'][index]['frame'] = index
        rows['operation.jsonl'][index]['time_s'] = frame['time_s']
    for name, values in rows.items():
        spec['files'][name] = ''.join(json.dumps(v, sort_keys=True) + '\n' for v in values)
    camera_rows = [{'native_frame': f['frame'], 'native_time_s': f['time_s'],
                    'cameras': {camera: {'source_kind': 'generated_diagnostic_video', 'video': video}
                                for camera, video in [('overview','overview.mkv'),('alley_approach','approach.mkv'),
                                                       ('access_aisle','reference_corner.mkv'),('driver_reference','driver_reference.mkv')]}}
                   for f in frames]
    spec['files']['camera-frame-map.jsonl'] = ''.join(json.dumps(v, sort_keys=True) + '\n' for v in camera_rows)
    path = HERE / ('diagnostic-' + kind + '.json')
    path.write_text(json.dumps(spec, separators=(',', ':'), ensure_ascii=False) + '\n')
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('diagnostic specification exceeds returned file limit')
    recipe = {'format': 'worker-fixture-recipe', 'sources': [{
        'path': 'diagnostic-alley-scene.json',
        'source': 'work/' + HERE.name + '/alley-scene.json',
        'sha256': sha(HERE / 'alley-scene.json')}],
        'generator': {'source': 'work/' + HERE.name + '/' + path.name,
                      'sha256': sha(path)}}
    (HERE / ('fixture-recipe-' + kind + '.json')).write_text(json.dumps(recipe, indent=2) + '\n')
    print(kind, path.stat().st_size, sha(path))

if __name__ == '__main__':
    for kind in ('steady_travel', 'steering_variation'):
        build(kind)

"""Construct source-bound 30-second synthetic park-control candidates."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))


def vertices(body):
    return [[float(x), float(y), z] for x, y in body for z in (0, 1.5)]


def source_bundle(state, selected):
    source = selected / 'source'
    shutil.copytree(ROOT / 'rider-30s-primary/source', source, dirs_exist_ok=True)
    draft = read_rows(ROOT / 'draft-facility/probe_b/native_samples.jsonl')
    assert len(draft) == 480
    rider = read_rows(source / 'rider_native_samples.jsonl')
    motion = read_rows(source / 'native_samples.jsonl')
    history = read_rows(source / 'body_history.jsonl')
    trace = read_rows(source / 'trace.jsonl')
    evidence = read_rows(source / 'capture/evidence.jsonl')
    assert all(len(rows) == 600 for rows in (rider, motion, history, trace, evidence))
    last_center = None
    for i in range(600):
        row = dict(draft[min(i, 479)])
        row['native_frame'] = rider[i]['native_frame']
        row['time_s'] = rider[i]['time_s']
        body, center = row['native_body_xy_m'], row['native_center_xy_m']
        speed = 0.0 if last_center is None else round((center[0] - last_center[0]) * 20, 5)
        last_center = center
        rider[i]['ego_body_xy'] = body
        rider[i]['ego_speed_mps'] = speed
        motion[i]['native_body_xy_m'] = body
        motion[i]['native_center_xy_m'] = center
        motion[i].update(row)
        motion[i]['speed_mps'] = speed
        history[i]['body_vertices_m'] = vertices(body)
        trace[i]['position'] = {'x': center[0], 'y': center[1], 'z': 0.5}
        trace[i]['position_m'] = [center[0], center[1], 0.5]
        trace[i]['speed_mps'] = speed
        trace[i]['speed_mph'] = speed * 2.2369362921
        trace[i]['velocity_mps'] = [speed, 0, 0]
        evidence[i]['ego']['body_vertices_m'] = vertices(body)
        evidence[i]['ego']['position_m'] = [center[0], center[1], 0.5]
        evidence[i]['ego']['speed_mps'] = speed
        ego = next(p for p in evidence[i]['original_observations']['participants']
                   if p['actor_id'] == 107)
        ego.update({'body_vertices_m': vertices(body), 'position_m': [*center, 0],
                    'speed_mps': speed, 'velocity_mps': [speed, 0, 0]})
        graph_path = source / 'capture/native/graphs/base' / f"{row['native_frame']:08d}.adapter.json"
        graph = json.loads(graph_path.read_text())
        next(p for p in graph['metadata']['observed_evidence']['participants']
             if p['actor_id'] == 107).update(ego)
        graph_path.write_text(json.dumps(graph, separators=(',', ':')) + '\n')
    for name, rows in (('rider_native_samples.jsonl', rider), ('native_samples.jsonl', motion),
                       ('body_history.jsonl', history), ('trace.jsonl', trace),
                       ('capture/evidence.jsonl', evidence)):
        write_rows(source / name, rows)
    rider_manifest = source / 'rider-source-manifest.json'
    rider_data = json.loads(rider_manifest.read_text())
    rider_data['samples_sha256'] = sha(source / 'rider_native_samples.jsonl')
    write(rider_manifest, rider_data)
    write(source / 'entry-sources.json', {'format':'c10052-entry-sources-v1',
        'source_kind':'synthetic_cpu_fixture', 'sha256':{'native_samples.jsonl':sha(source/'native_samples.jsonl'),
        'road_geometry.json':sha(source/'road_geometry.json')}})
    controls = [{'native_frame': row['native_frame'], 'time_s': row['time_s'],
                 'throttle': 0.0, 'brake': 0.5 if 132 <= i < 599 else 0.0,
                 'hand_brake': state == 'probe_park_held' and 160 <= i < 560,
                 'control_source': 'synthetic_fixture', 'synthetic_diagnostic': True}
                for i, row in enumerate(motion)]
    write_rows(source / 'native_controls.jsonl', controls)
    write(source / 'park-act-sources.json', {'format': 'c10052-park-act-sources-v1',
        'source_kind': 'synthetic_cpu_fixture',
        'sha256': {name: sha(source/name) for name in
                   ('native_samples.jsonl', 'native_controls.jsonl', 'road_geometry.json')}})
    capture_manifest = source / 'capture/manifest.json'
    capture = json.loads(capture_manifest.read_text())
    capture['sources']['trace.jsonl'] = sha(source / 'trace.jsonl')
    write(capture_manifest, capture)
    shutil.copy2(ROOT / 'rider-30s-primary/diagnostic-spec.json', selected / 'diagnostic-spec.json')
    write(selected / 'fixture-recipe.json', {
        'format': 'worker-fixture-recipe',
        'generator': {'source': str((selected / 'diagnostic-spec.json').relative_to(REPO)),
                      'sha256': sha(selected / 'diagnostic-spec.json')},
        'sources': [{'path': str(path.relative_to(source)),
                     'source': str(path.relative_to(REPO)), 'sha256': sha(path)}
                    for path in sorted(source.rglob('*')) if path.is_file()]})


def constructions(state, selected):
    spec = importlib.util.spec_from_file_location('rider_30s_builder', ROOT / 'build-rider-30s-primary.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        draft = ROOT / f'draft-park-cases/{state}/{candidate}/construction.json'
        target = selected / candidate / 'construction.json'
        module.convert(draft, target)
        construction = json.loads(target.read_text())
        for item in construction['files']:
            name, content = item['path'], item['content']
            if name == 'runner.py':
                content = content.replace("config['duration_s']!=24", "config['duration_s']!=30")
                content = content.replace('frames!=480', 'frames!=600').replace('frames==480', 'frames==600')
                content = content.replace("'expected_frames':480", "'expected_frames':600")
            elif name == 'measure_entry.py':
                content = content.replace('len(samples)!=480', 'len(samples)!=600')
            elif name == 'measure_facility.py':
                content = content.replace('len(samples) != 480', 'len(samples) != 600').replace('len(samples)!=480','len(samples)!=600')
            elif name == 'measure_park_act.py':
                content = content.replace('len(poses) != 480', 'len(poses) != 600')
            elif name == 'finalize.py':
                content = (ROOT/'native/finalize.py').read_text()
                content = content.replace('count != 480', 'count != 600')
                content = content.replace("('overview', 'approach', 'facility', 'driver_reference')", "('overview', 'approach', 'reference_corner', 'driver_reference')")
                rider_finalizer=(ROOT/'native/finalize_rider.py').read_text()
                derive=rider_finalizer[rider_finalizer.index('def derive_channels('):rider_finalizer.index('def finalize(')]
                content=content.replace('def finalize_full_attempt(',derive+'def finalize_full_attempt(')
                content=content.replace("    recording_evidence = []", "    derive_channels(attempt,description,rows(attempt/'native_samples.jsonl'),rows(attempt/'rider_native_samples.jsonl'),rows(attempt/'video_frames.jsonl'))\n    recording_evidence = []")
                content=content.replace("{'probe_a': 0.0, 'probe_b': 9.36}", "{'probe_park_released': 9.36, 'probe_park_held': 9.36}")
                content=content.replace("'method':'original_native_pose_and_applied_control_join'", "'method':'parking_control_observation'")
                content=content.replace('        park = measure_park_act(attempt)', '        park = parking_control_observation(attempt)')
                content=content.replace('def finalize_full_attempt(', "def parking_control_observation(attempt):\n    for name in ('native_samples.jsonl', 'native_controls.jsonl', 'road_geometry.json', 'park-act-sources.json'):\n        if not (Path(attempt)/name).is_file():\n            raise ValueError('Missing required source: '+name)\n    return measure_park_act(attempt)\n\ndef finalize_full_attempt(")
            if name.endswith('.py'):
                ast.parse(content, filename=name)
            item['content'] = content
        write(target, construction)


if __name__ == '__main__':
    for state in ('probe_park_released', 'probe_park_held'):
        selected = ROOT / f'selected-park-{state}'
        selected.mkdir(exist_ok=True)
        source_bundle(state, selected)
        constructions(state, selected)
        print(state, sha(selected / 'fixture-recipe.json'))

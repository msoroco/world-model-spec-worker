"""Construct source-bound 30-second synthetic exception C candidates."""
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


def source_bundle(response, selected):
    source = selected / 'source'
    shutil.copytree(ROOT / 'rider-30s-primary/source', source, dirs_exist_ok=True)
    draft = read_rows(ROOT / f'draft-exception-c-cases/{response}/primary/source-rows.jsonl')
    assert len(draft) == 480
    rider = read_rows(source / 'rider_native_samples.jsonl')
    motion = read_rows(source / 'native_samples.jsonl')
    history = read_rows(source / 'body_history.jsonl')
    trace = read_rows(source / 'trace.jsonl')
    evidence = read_rows(source / 'capture/evidence.jsonl')
    assert all(len(rows) == 600 for rows in (rider, motion, history, trace, evidence))
    traffic = []
    last_center = None
    for i in range(600):
        row = dict(draft[min(i, 479)])
        row['native_frame'] = rider[i]['native_frame']
        row['time_s'] = rider[i]['time_s']
        row['ego_native_road_id'] = 1
        row['ego_native_lane_id'] = -2 if row['ego_center_xy'][1] < -2.5 else -1
        body = row['ego_body_xy']
        center = row['ego_center_xy']
        speed = 0.0 if last_center is None else round((center[0] - last_center[0]) * 20, 5)
        last_center = center
        rider[i]['ego_body_xy'] = body
        rider[i]['ego_speed_mps'] = speed
        motion[i]['native_body_xy_m'] = body
        motion[i]['native_center_xy_m'] = center
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
        participants = evidence[i]['original_observations']['participants']
        ego = next(p for p in participants if p['actor_id'] == 107)
        ego.update({'body_vertices_m': vertices(body), 'position_m': [*center, 0],
                    'speed_mps': speed, 'velocity_mps': [speed, 0, 0]})
        if row['conflict_actor_active']:
            actor = {'actor_id': 221, 'blueprint': 'vehicle.audi.tt',
                     'position_m': [0.0, -1.5, 0], 'heading_deg': 0,
                     'velocity_mps': [0, 0, 0], 'speed_mps': 0,
                     'acceleration_mps2': [0, 0, 0],
                     'body_vertices_m': vertices(row['conflict_actor_body_xy']),
                     'blueprint_attributes': {}, 'light_attributes': {}}
            participants.append(actor)
        graph_path = source / 'capture/native/graphs/base' / f"{row['native_frame']:08d}.adapter.json"
        graph = json.loads(graph_path.read_text())
        graph_participants = graph['metadata']['observed_evidence']['participants']
        next(p for p in graph_participants if p['actor_id'] == 107).update(ego)
        if row['conflict_actor_active']:
            graph_participants.append(actor)
        graph_path.write_text(json.dumps(graph, separators=(',', ':')) + '\n')
        traffic.append(row)
    for name, rows in (('exception_c_native_samples.jsonl', traffic),
                       ('rider_native_samples.jsonl', rider), ('native_samples.jsonl', motion),
                       ('body_history.jsonl', history), ('trace.jsonl', trace),
                       ('capture/evidence.jsonl', evidence)):
        write_rows(source / name, rows)
    for name, samples in (('rider-source-manifest.json', 'rider_native_samples.jsonl'),):
        path = source / name
        data = json.loads(path.read_text())
        data['samples_sha256'] = sha(source / samples)
        write(path, data)
    road_path = source / 'road_geometry.json'
    road = json.loads(road_path.read_text())
    write(road_path, road)
    write(source / 'exception-c-source-manifest.json', {
        'source_kind': 'synthetic_cpu_fixture', 'accepted': False,
        'samples_sha256': sha(source / 'exception_c_native_samples.jsonl'),
        'road_geometry_sha256': sha(road_path),
        'conflict_actor_id': 221 if response == 'avoid' else None,
        'conflict_actor_blueprint': 'vehicle.audi.tt' if response == 'avoid' else None})
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


def constructions(response, selected):
    spec = importlib.util.spec_from_file_location('rider_30s_builder', ROOT / 'build-rider-30s-primary.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        draft = ROOT / f'draft-exception-c-exact-cases/exception_c_{response}/{candidate}/construction.json'
        target = selected / candidate / 'construction.json'
        module.convert(draft, target)
        construction = json.loads(target.read_text())
        for item in construction['files']:
            name = item['path']
            content = item['content']
            if name == 'runner.py':
                content = content.replace("config['duration_s']!=24", "config['duration_s']!=30")
                content = content.replace('frames!=480', 'frames!=600').replace('frames==480', 'frames==600')
                content = content.replace("'expected_frames':480", "'expected_frames':600")
            elif name == 'finalize.py':
                content = content.replace('count != 480', 'count != 600').replace('480-frame', '600-frame')
            elif name == 'exception_c_engineering.py':
                content = (ROOT / 'native/exception_c_engineering.py').read_text()
                content = content.replace('FRAMES=480', 'FRAMES=600')
                content = content.replace('Expected 480 source rows', 'Expected 600 source rows')
                content = content.replace("row['native_frame']!=1000+i or row['time_s']!=round(i/RATE_HZ,2)",
                                          "row['native_frame']!=100+i or row['time_s']!=round((i+1)/RATE_HZ,2)")
            elif name == 'finalize_exception_c.py':
                content = (ROOT / 'native/finalize_exception_c.py').read_text()
                rider_finalizer = (ROOT / 'native/finalize_rider.py').read_text()
                derive = rider_finalizer[rider_finalizer.index('def derive_channels('):rider_finalizer.index('def finalize(')]
                marker = "            elif name.startswith('ru.') and name[3:] in ("
                index = derive.index(marker)
                derive = derive[:index] + (
                    "            elif name == 'ru.vehicle':\n"
                    "                value = {'native_actor_id': rider['conflict_actor_id'],\n"
                    "                         'native_body_xy_m': rider['conflict_actor_body_xy'],\n"
                    "                         'active': rider['conflict_actor_active'],\n"
                    "                         'source_frame': rider['native_frame'],\n"
                    "                         'synthetic_diagnostic': True}\n") + derive[index:]
                content = content.replace('def original_measure(', derive + 'def original_measure(')
                content = content.replace('    source=json.loads((attempt/\'exception-c-source-manifest.json\').read_text())',
                    "    source_path=attempt/'exception-c-source-manifest.json'\n"
                    "    if not source_path.is_file():\n"
                    "        raise ValueError('Missing required source: exception-c-source-manifest.json')\n"
                    "    source=json.loads(source_path.read_text())")
                content = content.replace('    description=config[\'recording_description\'];recording=[]',
                    '    description=config[\'recording_description\']\n'
                    '    derive_channels(attempt, description, motion, samples, mapping)\n'
                    '    recording=[]')
                content = content.replace('!=480', '!=600').replace('480-frame', '600-frame')
                content = content.replace('verify_original_joins(attempt,480)', 'verify_original_joins(attempt,600)')
                content = content.replace('entire 24 s', 'entire 30 s').replace('[0,24]', '[0,30]')
                content = content.replace("'measurements':measured,'original_joins':original,",
                    "'measurements':{'exception_c_observation':{'method':'finalize','value':measured,"
                    "'sources':{'exception_c_native_samples.jsonl':sha(attempt/'exception_c_native_samples.jsonl'),"
                    "'road_geometry.json':sha(attempt/'road_geometry.json'),"
                    "'exception-c-source-manifest.json':sha(source_path)}}},'original_joins':original,")
            if name.endswith('.py'):
                ast.parse(content, filename=name)
            item['content'] = content
        write(target, construction)


if __name__ == '__main__':
    for response in ('avoid', 'no_conflict'):
        selected = ROOT / f'selected-exception-c-{response}'
        selected.mkdir(exist_ok=True)
        source_bundle(response, selected)
        constructions(response, selected)
        print(response, sha(selected / 'fixture-recipe.json'))

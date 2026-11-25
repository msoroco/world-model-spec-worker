"""Bind the pedestrian conflict trajectory through retained synthetic CPU rows."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SELECTED = ROOT / 'selected-pedestrian-conflict'
SOURCE = SELECTED / 'source'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def vertices(body):
    return [[float(x), float(y), z] for x, y in body for z in (0, 1.5)]


def main():
    draft = read_rows(ROOT / 'draft-pedestrian-cases/conflict/primary/source-rows.jsonl')
    pedestrian = read_rows(SOURCE / 'pedestrian_native_samples.jsonl')
    rider = read_rows(SOURCE / 'rider_native_samples.jsonl')
    motion = read_rows(SOURCE / 'native_samples.jsonl')
    history = read_rows(SOURCE / 'body_history.jsonl')
    trace = read_rows(SOURCE / 'trace.jsonl')
    evidence = read_rows(SOURCE / 'capture/evidence.jsonl')
    assert all(len(rows) == 600 for rows in (pedestrian, rider, motion, history, trace, evidence))
    last_center = None
    for i in range(600):
        body = draft[min(i, 479)]['ego_body_xy']
        pedestrian[i]['ego_body_xy'] = body
        rider[i]['ego_body_xy'] = body
        center = [round(sum(point[k] for point in body) / 4, 5) for k in (0, 1)]
        speed = 0.0 if last_center is None else round((center[0] - last_center[0]) * 20, 5)
        last_center = center
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
        ego = next(row for row in participants if row['actor_id'] == 107)
        ego['body_vertices_m'] = vertices(body)
        ego['position_m'] = [center[0], center[1], 0]
        ego['speed_mps'] = speed
        ego['velocity_mps'] = [speed, 0, 0]
        ped = next(row for row in participants if row['actor_id'] == 109)
        ped['body_vertices_m'] = vertices(pedestrian[i]['pedestrian_body_xy'])
        ped['position_m'] = [*pedestrian[i]['pedestrian_xy'], 0]
        graph_path = SOURCE / 'capture/native/graphs/base' / f"{rider[i]['native_frame']:08d}.adapter.json"
        graph = json.loads(graph_path.read_text())
        graph_participants = graph['metadata']['observed_evidence']['participants']
        for actor_id, source_row in ((107, ego), (109, ped)):
            target = next(row for row in graph_participants if row['actor_id'] == actor_id)
            target.update(source_row)
        graph_path.write_text(json.dumps(graph, separators=(',', ':')) + '\n')
    for name, rows in (('pedestrian_native_samples.jsonl', pedestrian),
                       ('rider_native_samples.jsonl', rider),
                       ('native_samples.jsonl', motion), ('body_history.jsonl', history),
                       ('trace.jsonl', trace), ('capture/evidence.jsonl', evidence)):
        write_rows(SOURCE / name, rows)
    ped_manifest = SOURCE / 'pedestrian-source-manifest.json'
    data = json.loads(ped_manifest.read_text())
    data['samples_sha256'] = sha(SOURCE / 'pedestrian_native_samples.jsonl')
    write(ped_manifest, data)
    rider_manifest = SOURCE / 'rider-source-manifest.json'
    data = json.loads(rider_manifest.read_text())
    data['samples_sha256'] = sha(SOURCE / 'rider_native_samples.jsonl')
    write(rider_manifest, data)
    capture_manifest = SOURCE / 'capture/manifest.json'
    data = json.loads(capture_manifest.read_text())
    data['sources']['trace.jsonl'] = sha(SOURCE / 'trace.jsonl')
    write(capture_manifest, data)
    recipe_path = SELECTED / 'fixture-recipe.json'
    recipe = json.loads(recipe_path.read_text())
    recipe['sources'] = [{'path': str(path.relative_to(SOURCE)),
                          'source': str(path.relative_to(REPO)), 'sha256': sha(path)}
                         for path in sorted(SOURCE.rglob('*')) if path.is_file()]
    write(recipe_path, recipe)
    print(json.dumps({'source_frames': 600, 'recipe_sha256': sha(recipe_path),
                      'pedestrian_sha256': sha(SOURCE / 'pedestrian_native_samples.jsonl'),
                      'trace_sha256': sha(SOURCE / 'trace.jsonl')}))


if __name__ == '__main__':
    main()

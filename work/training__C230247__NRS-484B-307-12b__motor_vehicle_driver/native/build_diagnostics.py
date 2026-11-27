"""Build two source-shaped red-X software fixtures, never physical recordings."""
import hashlib
import json
from pathlib import Path
from prove_meter import source_rows

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = HERE.parents[2]
ASSIGNMENT = ROOT.name
TEMPLATE = REPO / 'work/training__C230247__NRS-484B-307-12a__motor_vehicle_driver/diagnostic-condition_a.json'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')

def encode(value):
    return json.dumps(value, separators=(',', ':'), sort_keys=True)

def lines(rows):
    return ''.join(encode(row) + '\n' for row in rows)

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def save(path, value):
    path.write_text(encode(value) + '\n')
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('fixture exceeds return limit: ' + str(path))

for tag, enter in (('probe_1', False), ('probe_2', True)):
    cid = ASSIGNMENT + '__' + tag
    source = source_rows(enter)
    for row in source:
        row['diagnostic_fixture'] = True
    signal_path = ROOT / ('diagnostic-' + tag + '-native-signal-rows.jsonl')
    signal_path.write_text(lines(source))
    original = json.loads(TEMPLATE.read_text())
    spec = {'files': {}, 'graphs': original['graphs'], 'videos': original['videos']}
    frames = [json.loads(line) for line in original['files']['video_frames.jsonl'].splitlines()]
    traces = [json.loads(line) for line in original['files']['trace.jsonl'].splitlines()]
    evidence = [json.loads(line) for line in original['files']['capture/evidence.jsonl'].splitlines()]
    native_frames = [json.loads(line) for line in original['files']['capture/native/frames.jsonl'].splitlines()]
    for index, row in enumerate(source):
        frame = row['native_frame']
        time_s = index / 20
        x = 10 + index * .125
        ys = [v[1] for v in row['vehicle']['body_vertices_m']]
        y = (min(ys) + max(ys)) / 2
        frames[index].update(video_frame=index, carla_frame=frame, native_frame=frame,
                             time_s=time_s, camera_native_frames={name: frame for name in CAMERAS})
        traces[index].update(frame=frame, time_s=time_s,
                             position={'x': x, 'y': y, 'z': 1}, position_m=[x, y, 1],
                             heading_deg=0, speed_mps=2.5,
                             speed_mph=2.5 / .44704,
                             velocity_mps=[2.5, .7 if enter and 200 <= index < 300 else 0, 0])
        evidence[index].update(original_frame=frame, replay_frame=frame,
                               recording_time_s=time_s, replay_simulation_time_s=time_s,
                               ego={'position_m': [x, y, 1], 'heading_deg': 0,
                                    'speed_mps': 2.5, 'body_vertices_m': row['vehicle']['body_vertices_m'],
                                    'speed_provenance': 'synthetic_native_sample'},
                               world={'road_projection': {'road_id': 1, 'section_id': 0,
                                                          'lane_id': row['vehicle']['lane_id'], 's_m': x}})
        graph = f'graphs/base/{frame:08d}.adapter.json'
        native_frames[index].update(abstract=graph, adapter_graph=graph, base=graph,
                                    frame=frame, simulation_time=time_s, time_s=time_s)
        spec['graphs'][index]['path'] = 'capture/native/' + graph
        spec['graphs'][index]['attributes']['frame'] = frame
    trace_lines = lines(traces)
    spec['files'] = {
        'video_frames.jsonl': lines(frames), 'trace.jsonl': trace_lines,
        'capture/evidence.jsonl': lines(evidence),
        'capture/native/frames.jsonl': lines(native_frames),
        'capture/manifest.json': encode({
            'frames': 600, 'extraction_confirmed': True, 'synthetic_diagnostic': True,
            'case_id': cid, 'required_observations': [],
            'sources': {'road.xodr': sha(HERE / 'road.xodr'),
                        'native-map-readback.xodr': sha(HERE / 'road.xodr'),
                        'trace.jsonl': hashlib.sha256(trace_lines.encode()).hexdigest()}}) + '\n',
        'capture/recorder_info.txt': 'Synthetic CPU diagnostic; no CARLA recording.\nCreate 71: vehicle.tesla.model3\n'
    }
    spec_path = ROOT / ('diagnostic-' + tag + '.json')
    save(spec_path, spec)
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'native-signal-rows.jsonl',
                           'source': str(signal_path.relative_to(REPO)), 'sha256': sha(signal_path)},
                          {'path': 'native-map-readback.xodr',
                           'source': str((HERE / 'road.xodr').relative_to(REPO)),
                           'sha256': sha(HERE / 'road.xodr')}],
              'generator': {'source': str(spec_path.relative_to(REPO)), 'sha256': sha(spec_path)}}
    recipe_path = ROOT / ('diagnostic-' + tag + '-recipe.json')
    save(recipe_path, recipe)
    print(encode({'case_id': cid, 'spec_bytes': spec_path.stat().st_size,
                  'recipe_sha256': sha(recipe_path), 'source_sha256': sha(signal_path)}))

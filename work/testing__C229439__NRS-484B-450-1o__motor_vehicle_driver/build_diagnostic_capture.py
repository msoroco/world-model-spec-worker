"""Generate bounded synthetic Core/video fixture specs for eight exact cases.

The road geometry is a copied unrelated CPU test map. It proves software
compatibility only and cannot establish C229439's physical sign or highway.
"""
import hashlib
import json
from pathlib import Path


def compact(value):
    return json.dumps(value, separators=(',', ':'), sort_keys=True)


def lines(rows):
    return ''.join(compact(row) + '\n' for row in rows)


def build(folder):
    repo = folder.parents[1]
    map_text = (folder / 'diagnostic-road.xodr').read_text()
    manifest = json.loads((folder / 'execution-manifest.json').read_text())
    for entry in manifest['cases']:
        short = entry['case_id'].rsplit('__', 1)[-1]
        case_dir = folder / 'cases' / short
        rows = json.loads((case_dir / 'diagnostic-sources/actor_rows.json').read_text())
        trace, mappings, evidence, native_frames, graphs = [], [], [], [], []
        for index, row in enumerate(rows):
            frame, stamp = row['frame'], row['time_s']
            position = [0, 0, 0]
            source_packet = {'frame': frame, 'time_s': stamp, 'participants': [],
                             'map_context': {'diagnostic_fixture': True}}
            graph_name = f'graphs/base/{frame:08d}.adapter.json'
            graphs.append({'path': 'capture/native/' + graph_name,
                           'attributes': {'frame': frame, 'time_s': stamp,
                                          'observed_evidence': source_packet},
                           'nodes': [], 'edges': []})
            native_frames.append({'frame': frame, 'simulation_time': stamp,
                                  'adapter_graph': graph_name})
            mappings.append({'video_frame': index, 'carla_frame': frame,
                             'native_frame': frame, 'time_s': stamp})
            trace.append({'frame': frame, 'time_s': stamp, 'position_m': position,
                          'position': {'x': 0, 'y': 0, 'z': 0}, 'heading_deg': 0,
                          'speed_mps': row['speed_mps'], 'speed_mph': row['speed_mps'] / .44704,
                          'velocity_mps': [0, 0, 0], 'control': {}})
            evidence.append({'actor_id': 7, 'original_frame': frame, 'replay_frame': frame,
                             'recording_time_s': stamp, 'replay_simulation_time_s': stamp,
                             'ego': {'body_vertices_m': [[x, y, z] for x in (-.5, .5)
                                 for y in (-.5, .5) for z in (0, 1)],
                                 'position_m': position, 'heading_deg': 0,
                                 'speed_mps': row['speed_mps'],
                                 'speed_provenance': 'synthetic_native_sample'},
                             'original_observations': source_packet, 'world': {'weather': {}}})
        trace_text = lines(trace)
        files = {'road.xodr': map_text, 'trace.jsonl': trace_text,
                 'video_frames.jsonl': lines(mappings),
                 'capture/evidence.jsonl': lines(evidence),
                 'capture/native/frames.jsonl': lines(native_frames),
                 'capture/recorder_info.txt': 'Create 7: vehicle.tesla.model3 (diagnostic) at (0, 0, 0)\n',
                 'acquisition-provenance.json': compact({'diagnostic_fixture': True,
                     'provenance_kind': 'synthetic_fixture'}) + '\n'}
        files['capture/manifest.json'] = compact({
            'acquisition': 'synthetic_fixture', 'diagnostic_fixture': True,
            'case_id': entry['case_id'], 'extraction_confirmed': True,
            'frames': len(rows), 'sources': {
                'road.xodr': hashlib.sha256(map_text.encode()).hexdigest(),
                'trace.jsonl': hashlib.sha256(trace_text.encode()).hexdigest()}}) + '\n'
        videos = [{'path': name + '.mkv', 'frames': len(rows), 'width': size[0],
                   'height': size[1], 'fps': 20, 'color': 'black'}
                  for name, size in (('overview', (1920, 1080)),
                     ('approach', (1280, 720)), ('reference_corner', (1280, 720)),
                     ('driver_reference', (1280, 720)))]
        spec_path = case_dir / 'diagnostic.json'
        spec_path.write_text(compact({'files': files, 'graphs': graphs, 'videos': videos}) + '\n')
        recipe_path = case_dir / 'fixture-recipe.json'
        recipe = json.loads(recipe_path.read_text())
        recipe['generator'] = {'source': spec_path.relative_to(repo).as_posix(),
                               'sha256': hashlib.sha256(spec_path.read_bytes()).hexdigest()}
        recipe_path.write_text(json.dumps(recipe, indent=2) + '\n')
        print(short + ': ' + str(spec_path.stat().st_size) + ' spec bytes')


if __name__ == '__main__':
    build(Path(__file__).resolve().parent)

"""Build explicit 900-frame textual right-pass compatibility diagnostics."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def vertices(x, y):
    return [[x + dx, y + dy, 0.0] for dx in (-2.0, 2.0) for dy in (-0.9, 0.9)]


def build():
    for variant in ('left_signal', 'left_turn', 'neither'):
        folder = HERE / 'cases' / variant
        native = folder / 'fixture-sources/original-attempt/native'
        saved = json.loads((native / 'trace.json').read_text())
        trace, mapping, pass_history, events, frames, graphs = [], [], [], [], [], []
        for index, original in enumerate(saved['frames']):
            frame, time_s = original['native_frame_id'], index / 20
            ego_x, target_x = original['ego_s_m'], original['target_s_m']
            ego_y = 10 - original['ego_lateral_m']
            target_y = 10 - original['target_lateral_m']
            ego_body, target_body = vertices(ego_x, ego_y), vertices(target_x, target_y)
            trace.append({'frame': frame, 'time_s': time_s,
                          'position': {'x': ego_x, 'y': ego_y, 'z': 0.0},
                          'position_m': [ego_x, ego_y, 0.0], 'heading_deg': 0.0,
                          'speed_mps': original['ego_speed_mps'],
                          'speed_mph': original['ego_speed_mps'] * 2.23693629,
                          'velocity_mps': [original['ego_speed_mps'], 0.0, 0.0],
                          'control': {}})
            mapping.append({'video_frame': index, 'carla_frame': frame, 'time_s': time_s})
            pass_history.append({'frame': frame, 'time_s': time_s,
                                 'ego_vertices_m': ego_body,
                                 'target_vertices_m': target_body,
                                 'target_left_signal': original['target_left_signal'],
                                 'target_heading_deg': original['target_heading_deg']})
            observed = {'frame': frame, 'time_s': time_s,
                        'target_actor_id': saved['target_id'],
                        'target_left_signal': original['target_left_signal'],
                        'target_heading_deg': original['target_heading_deg']}
            events.append({'actor_id': saved['ego_id'], 'original_frame': frame,
                           'replay_frame': frame, 'recording_time_s': time_s,
                           'replay_simulation_time_s': time_s,
                           'ego': {'position_m': [ego_x, ego_y, 0.0],
                                   'heading_deg': 0.0,
                                   'speed_mps': original['ego_speed_mps'],
                                   'speed_provenance': 'synthetic_native_sample',
                                   'body_vertices_m': ego_body},
                           'world': {'weather': {}}, 'original_observations': observed})
            graph_path = f'graphs/base/{frame:08d}.adapter.json'
            frames.append({'frame': frame, 'simulation_time': time_s,
                           'adapter_graph': graph_path})
            graphs.append({'path': 'capture/native/' + graph_path,
                           'attributes': {'frame': frame, 'time_s': time_s,
                                          'observed_evidence': observed},
                           'nodes': [], 'edges': []})
        files = {
            'acquisition-provenance.json': encoded({'diagnostic_fixture': True,
                                                    'provenance_kind': 'synthetic_fixture'}),
            'fixture-provenance.json': encoded({'diagnostic_fixture': True,
                                                'scope': 'CPU software only; no original camera pixels'}),
            'road.xodr': '<OpenDRIVE><header name="SyntheticRightPassDiagnostic"/></OpenDRIVE>\n',
            'trace.jsonl': ''.join(encoded(row) for row in trace),
            'video_frames.jsonl': ''.join(encoded(row) for row in mapping),
            'pass_history.jsonl': ''.join(encoded(row) for row in pass_history),
            'capture/evidence.jsonl': ''.join(encoded(row) for row in events),
            'capture/native/frames.jsonl': ''.join(encoded(row) for row in frames),
            'capture/recorder_info.txt': 'Create 10: vehicle.synthetic.ego (0) at (55, 7, 0)\n',
        }
        files['capture/manifest.json'] = encoded({
            'status': 'draft', 'acquisition': 'diagnostic_fixture',
            'case_id': HERE.name + '__' + variant, 'frames': 900,
            'extraction_confirmed': True,
            'sources': {'road.xodr': hashlib.sha256(files['road.xodr'].encode()).hexdigest(),
                        'trace.jsonl': hashlib.sha256(files['trace.jsonl'].encode()).hexdigest()},
            'required_observations': []})
        videos = [{'path': view + '.mkv', 'frames': 900,
                   'width': 1920 if view == 'overview' else 1280,
                   'height': 1080 if view == 'overview' else 720,
                   'fps': 20, 'color': 'black'} for view in VIEWS]
        specification = folder / 'diagnostic.json'
        specification.write_text(encoded({'files': files, 'graphs': graphs, 'videos': videos}))
        sources = []
        for path in sorted(native.glob('*.json')):
            relative = 'original-attempt/native/' + path.name
            sources.append({'path': relative,
                            'source': str(path.relative_to(ROOT)),
                            'sha256': sha(path)})
        manifest_source = folder / 'fixture-sources/original-attempt/source-manifest.json'
        sources.append({'path': 'original-attempt/source-manifest.json',
                        'source': str(manifest_source.relative_to(ROOT)),
                        'sha256': sha(manifest_source)})
        recipe = folder / 'fixture-recipe.json'
        recipe.write_text(encoded({'format': 'worker-fixture-recipe',
                                   'sources': sources,
                                   'generator': {'source': str(specification.relative_to(ROOT)),
                                                 'sha256': sha(specification)}}))
        if specification.stat().st_size > 2 * 1024 * 1024:
            raise ValueError('diagnostic specification exceeds 2 MiB')
        print(variant, specification.stat().st_size)


if __name__ == '__main__':
    build()

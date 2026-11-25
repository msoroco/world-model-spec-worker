"""Build explicit synthetic 600-frame sources for reference-case CPU compatibility.

The output is a diagnostic specimen, never a Native capture or legal finding.
"""

import copy
import hashlib
import json
from pathlib import Path

from stopping_reference import from_authored_site


ROOT = Path(__file__).resolve().parent
PREFIX = 'testing__C158196__NRS-484B-257-2__motor_vehicle_driver__'
SITES = {
    'stop_line_reference': 'line-reference-site.xodr',
    'crosswalk_reference': 'crosswalk-reference-site.xodr',
    'nearest_view_reference': 'nearest-view-reference-site.xodr',
}
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def _lines(rows):
    return ''.join(json.dumps(row, sort_keys=True, separators=(',', ':')) + '\n'
                   for row in rows)


def build(suffix):
    if suffix not in SITES:
        raise ValueError('Select a reference-only case')
    case_id = PREFIX + suffix
    site = ROOT / SITES[suffix]
    reference = from_authored_site(site)
    base = json.loads((ROOT / 'cases/active_signal_controls-diagnostic-sources.json').read_text())
    trace_example = json.loads(base['files']['trace.jsonl'].splitlines()[1])
    evidence_example = json.loads(base['files']['capture/evidence.jsonl'].splitlines()[1])
    native_example = json.loads(base['files']['capture/native/frames.jsonl'].splitlines()[1])
    graphs = []
    files = {}
    capture = {'format': 'worker-subsection-2-officer-native-capture',
               'case_id': case_id, 'site_sha256': hashlib.sha256(site.read_bytes()).hexdigest(),
               'fixed_delta_seconds': 0.05, 'frame_count': 600, 'rows': []}
    history, traces, evidence, frames, native_frames = [], [], [], [], []
    body = [[-16.0, -1.0], [-16.0, 1.0], [-14.0, 1.0], [-14.0, -1.0]] * 2
    for index in range(600):
        frame = 100 + index
        time_s = round(5 + index * 0.05, 6)
        refs = {name: {'carla_frame': frame, 'video_frame': index,
                       'raw_source': name + '.mkv#frame-' + str(index)}
                for name in CAMERAS}
        capture['rows'].append({'frame_index': index, 'carla_frame': frame,
                                'time_s': time_s, 'stopping_reference': reference,
                                'ego_body_vertices_xy_m': body, 'ego_front_x_m': -14.0,
                                'ego_speed_mps': 0.0, 'camera_raw_sources': refs})
        history.append({'frame': frame, 'time_s': time_s,
                        'ego_body_vertices_xy_m': body, 'ego_speed_mps': 0.0})
        trace = copy.deepcopy(trace_example)
        trace.update(frame=frame, time_s=time_s)
        traces.append(trace)
        event = copy.deepcopy(evidence_example)
        event.update(original_frame=frame, recording_time_s=time_s,
                     replay_frame=frame, replay_simulation_time_s=time_s)
        event['original_observations'] = {
            'frame': frame, 'time_s': time_s, 'participants': [],
            'devices': [], 'map_context': {}}
        evidence.append(event)
        frames.append({'video_frame': index, 'carla_frame': frame, 'time_s': time_s,
                       'camera_frames': {name: frame for name in CAMERAS}})
        native = copy.deepcopy(native_example)
        native.update(frame=frame, simulation_time=time_s)
        for kind in ('base', 'abstract'):
            path = f'capture/native/graphs/{kind}/{frame:08d}.adapter.json'
            native[kind] = path.removeprefix('capture/native/')
            if kind == 'base':
                native['adapter_graph'] = native[kind]
            graph = {'path': path,
                     'attributes': {'frame': frame, 'simulation_time_s': time_s,
                                    'units': {'position': 'm'},
                                    'observed_evidence': event['original_observations']},
                     'nodes': [], 'edges': []}
            graphs.append(graph)
        native_frames.append(native)
    files['officer-reference-capture.json'] = json.dumps(capture, separators=(',', ':')) + '\n'
    files['officer_reference_history.jsonl'] = _lines(history)
    files['trace.jsonl'] = _lines(traces)
    files['capture/evidence.jsonl'] = _lines(evidence)
    files['video_frames.jsonl'] = _lines(frames)
    files['capture/native/frames.jsonl'] = _lines(native_frames)
    files['capture/recorder_info.txt'] = base['files']['capture/recorder_info.txt']
    manifest = json.loads(base['files']['capture/manifest.json'])
    manifest.update(case_id=case_id, frames=600)
    manifest['sources'] = {
        'road.xodr': hashlib.sha256(site.read_bytes()).hexdigest(),
        'trace.jsonl': hashlib.sha256(files['trace.jsonl'].encode()).hexdigest()}
    files['capture/manifest.json'] = json.dumps(manifest, sort_keys=True) + '\n'
    spec = {'files': files, 'graphs': graphs,
            'videos': [dict(video, frames=600) for video in base['videos']]}
    path = ROOT / 'cases' / (suffix + '-officer-reference-diagnostic-sources.json')
    path.write_text(json.dumps(spec, separators=(',', ':'), sort_keys=True) + '\n')
    if path.stat().st_size > 2 * 1024 * 1024:
        path.unlink()
        raise ValueError('Returned diagnostic source exceeds 2 MiB')
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'road.xodr',
                           'source': str(site.relative_to(ROOT.parents[1])),
                           'sha256': hashlib.sha256(site.read_bytes()).hexdigest()}],
              'generator': {'source': str(path.relative_to(ROOT.parents[1])),
                            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}}
    recipe_path = ROOT / 'cases' / (suffix + '-officer-reference-fixture-recipe.json')
    recipe_path.write_text(json.dumps(recipe, indent=2, sort_keys=True) + '\n')
    return path, recipe_path


if __name__ == '__main__':
    import sys
    for name in sys.argv[1:]:
        print(*build(name))

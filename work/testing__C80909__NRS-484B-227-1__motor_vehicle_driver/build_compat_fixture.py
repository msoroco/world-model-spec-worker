"""Build a bounded, source-bound C80909 opening software fixture.

The OpenDRIVE and graph are converter scaffolds. They do not establish the
physical divided-highway site, public-authority status, or camera visibility.
"""

import hashlib
import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SUFFIX = 'left_through_opening'
SCAFFOLD = (REPO / 'work/testing__C158196__NRS-484B-257-2__motor_vehicle_driver/signal-site.xodr')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lines(rows):
    return ''.join(json.dumps(row, sort_keys=True, allow_nan=False) + '\n' for row in rows)


def body(x, y, height=False):
    corners = [[x + dx, y + dy] for dx, dy in ((-0.4, -0.4), (-0.4, 0.4),
                                               (0.4, 0.4), (0.4, -0.4))]
    if not height:
        return corners
    return [[point[0], point[1], z] for point in corners for z in (0, 1.5)]


def build(suffix=SUFFIX):
    if suffix not in ('left_through_opening', 'left_across_blocked_divider',
                      'left_at_established_crossover', 'left_right_roadway_continuation'):
        raise ValueError('Unknown exact C80909 case')
    case = ROOT.name + '__' + suffix
    case_dir = ROOT / 'cases' / suffix
    site = json.loads((case_dir / 'site-plan.json').read_text())
    diagnostic = case_dir / 'diagnostic-site.json'
    if site['selected_case_id'] != case or site['source_refs'][0]['sha256'] != digest(diagnostic):
        raise ValueError('C80909 diagnostic site source changed')
    route = site['ego_route_xy_m']
    if len(route) == 3:
        route = [*route, [29, -5]]
    if len(route) != 4:
        raise ValueError('Four sampled route points required')
    headings = (0, 0, 0, 0) if suffix == 'left_right_roadway_continuation' else (0, 0, 45, 90)
    positions = [(point[0], point[1], heading) for point, heading in zip(route, headings)]
    movements, frames, traces, evidence, native_frames, graphs = [], [], [], [], [], []
    for index, (x, y, heading) in enumerate(positions):
        frame = 100 + index
        time_s = 5 + index / 20
        ego_xy, other_xy = body(x, y), body(25, -5)
        ego = {'actor_id': 101, 'blueprint': 'vehicle.tesla.model3',
               'position_m': [x, y, 0], 'body_vertices_m': body(x, y, True),
               'heading_deg': heading, 'speed_mps': 3,
               'velocity_mps': [3, 0, 0], 'accel_longitudinal_mps2': 0}
        other = {'actor_id': 102, 'blueprint': 'vehicle.tesla.model3',
                 'position_m': [25, -5, 0], 'body_vertices_m': body(25, -5, True),
                 'heading_deg': 0, 'speed_mps': 0,
                 'velocity_mps': [0, 0, 0], 'accel_longitudinal_mps2': 0}
        observed = {'frame': frame, 'time_s': time_s,
                    'participant_inventory': 'C80909 synthetic software fixture',
                    'participants': [ego, other], 'relations': [], 'devices': [],
                    'map_context': {}}
        movements.append({'frame': frame, 'time_s': time_s,
                          'ego_body_vertices_xy_m': ego_xy,
                          'other_body_vertices_xy_m': other_xy,
                          'ego_forward_xy': [1, 0] if heading == 0 else
                                            [0, 1] if heading == 90 else [0.70710678, 0.70710678],
                          'heading_deg': heading, 'road_id': 1})
        frames.append({'video_frame': index, 'carla_frame': frame, 'native_frame': frame,
                       'time_s': time_s,
                       'camera_frames': {name: frame for name in
                                         ('overview', 'approach', 'reference_corner', 'driver_reference')}})
        traces.append({'frame': frame, 'time_s': time_s,
                       'position': {'x': x, 'y': y, 'z': 0},
                       'position_m': [x, y, 0], 'heading_deg': heading,
                       'speed_mps': 3, 'speed_mph': 6.710808876,
                       'velocity_mps': [3, 0, 0],
                       'control': {'throttle': 0.3, 'steer': 0, 'brake': 0,
                                   'hand_brake': False, 'reverse': False}})
        evidence.append({'actor_id': 101, 'original_frame': frame,
                         'recording_time_s': time_s, 'replay_frame': frame,
                         'replay_simulation_time_s': time_s, 'supporting_only': True,
                         'ego': {'body_vertices_m': ego['body_vertices_m'],
                                 'position_m': ego['position_m'], 'heading_deg': heading,
                                 'speed_mps': 3, 'speed_provenance': 'synthetic_native_sample'},
                         'original_observations': observed,
                         'world': {'road_projection': {'road_id': 1, 'lane_id': 1,
                                                       'section_id': 0, 's_m': x},
                                   'weather': {}}, 'timing': {}, 'visibility': {}})
        base = 'capture/native/graphs/base/' + f'{frame:08d}.adapter.json'
        abstract = 'capture/native/graphs/abstract/' + f'{frame:08d}.adapter.json'
        native_frames.append({'frame': frame, 'simulation_time': time_s,
                              'base': 'graphs/base/' + f'{frame:08d}.adapter.json',
                              'abstract': 'graphs/abstract/' + f'{frame:08d}.adapter.json',
                              'adapter_graph': 'graphs/base/' + f'{frame:08d}.adapter.json',
                              'nodes': 0, 'edges': 0,
                              'capture_seconds': 0, 'extraction_seconds': 0})
        for path in (base, abstract):
            graphs.append({'path': path, 'attributes': {
                'frame': frame, 'simulation_time_s': time_s,
                'units': {'position': 'm'}, 'observed_evidence': observed},
                'nodes': [], 'edges': []})
    context = site['divider_context']
    receipt = {'native_map_name': context['native_map_id'], 'case_id': case,
               'source_refs': site['source_refs'], 'diagnostic_fixture': True}
    if site.get('authority_source_ref'):
        receipt['authority_source_ref'] = site['authority_source_ref']
    barrier = {'opening_xy_m': context['opening_xy_m'],
               'barrier_footprints_xy_m': site['planned_barrier_footprints_xy_m'],
               'section_axis_offsets_m': [-10, 10], 'diagnostic_fixture': True}
    road = SCAFFOLD.read_text()
    if len(road) > 20000:
        raise ValueError('Converter scaffold changed unexpectedly')
    files = {'road.xodr': road,
             'movement_history.jsonl': lines(movements),
             'video_frames.jsonl': lines(frames),
             'trace.jsonl': lines(traces),
             'capture/evidence.jsonl': lines(evidence),
             'capture/native/frames.jsonl': lines(native_frames),
             'capture/recorder_info.txt':
                 'Version: 1\nMap: OpenDriveMap\n Create 101: vehicle.tesla.model3 (0) at (5, -5, 0)\n',
             'divider_context.json': json.dumps(context, sort_keys=True) + '\n',
             'site_source_receipt.json': json.dumps(receipt, sort_keys=True) + '\n',
             'barrier_receipt.json': json.dumps(barrier, sort_keys=True) + '\n',
             'acquisition-provenance.json': json.dumps({'diagnostic_fixture': True,
                'source_kind': 'synthetic_converter_scaffold'}, sort_keys=True) + '\n'}
    files['capture/manifest.json'] = json.dumps({
        'acquisition': 'synthetic_diagnostic', 'case_id': case,
        'frames': len(frames), 'map': 'Carla/Maps/OpenDriveMap',
        'extraction_confirmed': True, 'required_observations': [],
        'sources': {'road.xodr': hashlib.sha256(road.encode()).hexdigest(),
                    'trace.jsonl': hashlib.sha256(files['trace.jsonl'].encode()).hexdigest()},
        'status': 'draft'}, sort_keys=True) + '\n'
    videos = [{'path': name + '.mkv', 'frames': len(frames), 'width': width,
               'height': height, 'fps': 20, 'color': color}
              for name, width, height, color in (
                  ('overview', 1920, 1080, 'black'), ('approach', 1280, 720, 'green'),
                  ('reference_corner', 1280, 720, 'red'),
                  ('driver_reference', 1280, 720, 'blue'))]
    stem = 'opening' if suffix == SUFFIX else suffix
    spec_path = case_dir / (stem + '-diagnostic-sources.json')
    spec_path.write_text(json.dumps({'files': files, 'graphs': graphs,
                                     'videos': videos}, indent=2) + '\n')
    note = ROOT / 'diagnostic-fixture-note.txt'
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': note.name,
                           'source': note.relative_to(REPO).as_posix(),
                           'sha256': digest(note)}],
              'generator': {'source': spec_path.relative_to(REPO).as_posix(),
                            'sha256': digest(spec_path)}}
    (case_dir / (stem + '-fixture-recipe.json')).write_text(json.dumps(recipe, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--suffix', default=SUFFIX)
    build(parser.parse_args().suffix)

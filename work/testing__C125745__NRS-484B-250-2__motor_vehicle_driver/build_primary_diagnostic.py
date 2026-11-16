"""Generate exact C125745 stop-sign original-source CPU diagnostic inputs.

All rows, graph observations and videos are synthetic software fixtures.
"""
import hashlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE / 'tests'))
from test_simultaneous_entries import EntryTests  # noqa: E402
from runner import _context  # noqa: E402
from capture_sources import CAMERAS  # noqa: E402


def lines(rows):
    return ''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows)


def sha_text(value):
    return hashlib.sha256(value.encode()).hexdigest()


def road(ident, name, x, y, heading, junction):
    return (f'<road name="{name}" length="30" id="{ident}" junction="{junction}"><link/>'
            f'<planView><geometry s="0" x="{x}" y="{y}" hdg="{heading}" length="30"><line/>'
            '</geometry></planView><elevationProfile><elevation s="0" a="0" b="0" c="0" d="0"/>'
            '</elevationProfile><lateralProfile/><lanes><laneOffset s="0" a="0" b="0" c="0" d="0"/>'
            '<laneSection s="0"><left><lane id="1" type="driving" level="false"><width sOffset="0" '
            'a="3.5" b="0" c="0" d="0"/></lane></left><center><lane id="0" type="none" '
            'level="false"/></center><right><lane id="-1" type="driving" level="false">'
            '<width sOffset="0" a="3.5" b="0" c="0" d="0"/></lane></right></laneSection>'
            '</lanes></road>')


def build():
    case = HERE.name + '__stop_ego_left_near_time'
    config = json.loads((HERE / 'config.json').read_text())
    site = json.loads((HERE / 'site.json').read_text())
    with tempfile.TemporaryDirectory(prefix='c125745-original-shape-') as temporary:
        base = Path(temporary)
        EntryTests().fixture(base)
        crossing = [json.loads(row) for row in (base / 'crossing_history.jsonl').read_text().splitlines()]
        frame_map = [json.loads(row) for row in (base / 'video_frames.jsonl').read_text().splitlines()]
    context = _context(site)
    context['physical_acceptance_claimed'] = False
    files = {'junction_context.json': json.dumps(context, allow_nan=False) + '\n',
             'crossing_history.jsonl': lines(crossing),
             'video_frames.jsonl': lines(frame_map)}
    controls = []
    trace = []
    evidence = []
    native_frames = []
    graphs = []
    for row in crossing:
        frame, time_s = row['frame'], row['time_s']
        ego_body = row['ego']['body_vertices_xy_m']
        center = [sum(vertex[i] for vertex in ego_body) / len(ego_body) for i in (0, 1)]
        trace.append({'frame': frame, 'time_s': time_s,
                      'position': {'x': center[0], 'y': center[1], 'z': 0},
                      'position_m': [*center, 0], 'heading_deg': 0,
                      'speed_mps': 0, 'speed_mph': 0,
                      'velocity_mps': [0, 0, 0],
                      'control': {'throttle': 0, 'steer': 0, 'brake': 1,
                                  'hand_brake': False, 'reverse': False}})
        controls.append({'frame': frame, 'time_s': time_s,
                         'ego_stopped_once': True, 'other_conflict_clear': False,
                         'commands': {'ego': {'throttle': 0.0, 'brake': 1.0,
                                              'speed_mps': 0.0}}})
        participants = []
        for role, actor_id, heading in (('ego', 101, 0), ('other', 102, 90)):
            vertices = row[role]['body_vertices_xy_m']
            x = sum(vertex[0] for vertex in vertices) / len(vertices)
            y = sum(vertex[1] for vertex in vertices) / len(vertices)
            body = [[vertex[0], vertex[1], z] for vertex in vertices for z in (0, 1.5)]
            participants.append({'actor_id': actor_id, 'blueprint': 'vehicle.tesla.model3',
                                 'position_m': [x, y, 0], 'heading_deg': heading,
                                 'speed_mps': 0, 'velocity_mps': [0, 0, 0],
                                 'body_vertices_m': body, 'accel_longitudinal_mps2': 0})
        observations = {'frame': frame, 'time_s': time_s, 'participants': participants,
                        'devices': [], 'relations': [],
                        'participant_inventory': 'synthetic C125745 stop-sign two-vehicle diagnostic',
                        'map_context': {}}
        evidence.append({'original_frame': frame, 'replay_frame': frame,
                         'actor_id': 101, 'recording_time_s': time_s,
                         'replay_simulation_time_s': time_s,
                         'ego': {**{key: participants[0][key] for key in
                                     ('position_m', 'heading_deg', 'speed_mps', 'body_vertices_m')},
                                 'speed_provenance': 'synthetic_native_sample'},
                         'world': {'weather': {'cloudiness': 0, 'precipitation': 0,
                                               'precipitation_deposits': 0, 'fog_density': 0,
                                               'sun_altitude_angle': 45, 'wetness': 0},
                                   'road_projection': {'road_id': 1, 'section_id': 0,
                                                       'lane_id': -1, 's_m': center[0]}},
                         'original_observations': observations,
                         'timing': {}, 'visibility': {}, 'supporting_only': True})
        base_name = f'graphs/base/{frame:08d}.pkl'
        abstract_name = f'graphs/abstract/{frame:08d}.pkl'
        native_frames.append({'frame': frame, 'simulation_time': time_s,
                              'base': base_name, 'abstract': abstract_name,
                              'nodes': 0, 'edges': 0,
                              'extraction_seconds': 0, 'capture_seconds': 0})
        for name in (base_name, abstract_name):
            graphs.append({'path': 'capture/native/' + name,
                           'attributes': {'frame': frame, 'simulation_time_s': time_s,
                                          'units': {'position': 'm'},
                                          'observed_evidence': observations},
                           'nodes': [], 'edges': []})
    files['trace.jsonl'] = lines(trace)
    files['controller_history.jsonl'] = lines(controls)
    files['capture/evidence.jsonl'] = lines(evidence)
    files['capture/native/frames.jsonl'] = lines(native_frames)
    files['capture/recorder_info.txt'] = ('Version: 1\nMap: OpenDriveMap\n'
                                          ' Create 101: vehicle.tesla.model3 (0) at (0, 0, 0)\n')
    xodr = ('<OpenDRIVE><header revMajor="1" revMinor="4" '
            'name="synthetic C125745 stop-sign crossing" version="1" '
            'north="20" south="-20" east="30" west="0" vendor="worker"/>'
            + road(1, 'synthetic east-west highway', 0, 0, 0, -1)
            + road(2, 'synthetic north-south highway', 15, -15, 1.5707963267948966, 44)
            + '<junction name="synthetic crossing" id="44"><connection id="0" '
            'incomingRoad="1" connectingRoad="2" contactPoint="start">'
            '<laneLink from="-1" to="-1"/></connection></junction></OpenDRIVE>')
    files['road.xodr'] = xodr
    files['capture/manifest.json'] = json.dumps({
        'status': 'draft', 'acquisition': 'synthetic_diagnostic',
        'case_id': case, 'map': 'Carla/Maps/OpenDriveMap',
        'frames': len(crossing), 'required_observations': config['required_atoms'],
        'extraction_confirmed': True,
        'sources': {'road.xodr': sha_text(xodr), 'trace.jsonl': sha_text(files['trace.jsonl'])},
    }, indent=2, allow_nan=False) + '\n'
    videos = [{'path': name + '.mkv', 'frames': len(crossing),
               'width': width, 'height': height, 'fps': 20, 'color': 'black'}
              for name, (width, height) in CAMERAS.items()]
    spec = {'files': files, 'graphs': graphs, 'videos': videos}
    diagnostic = HERE / 'diagnostic.json'
    diagnostic.write_text(json.dumps(spec, indent=2, allow_nan=False) + '\n')
    site_source = HERE / 'site.json'
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'site-source.json',
                           'source': str(site_source.relative_to(REPO)),
                           'sha256': hashlib.sha256(site_source.read_bytes()).hexdigest()}],
              'generator': {'source': str(diagnostic.relative_to(REPO)),
                            'sha256': hashlib.sha256(diagnostic.read_bytes()).hexdigest()}}
    (HERE / 'diagnostic-recipe.json').write_text(json.dumps(recipe, indent=2) + '\n')
    return {'case_id': case, 'diagnostic_sha256': recipe['generator']['sha256'],
            'original_frames': len(crossing), 'graph_sources': len(graphs),
            'physical_acceptance_claimed': False}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))

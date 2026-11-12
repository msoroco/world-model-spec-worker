"""Add case-specific synthetic Native capture sources to the first diagnostic.

These rows are reconstructed from the authored crossing history for CPU checks.
They are not physical observations and cannot establish a real median crossing.
"""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
CASE = 'testing__C125697__NRS-484B-250-2__motor_vehicle_driver__off_ego_left_near_time'
HEADINGS = ((101, 'ego', 0), (102, 'other', 90))
RECORDER_START = (0, 0, 0)
EGO_ROAD_S_AXIS = 0
EGO_ROAD_S_OFFSET = 0


def lines(rows):
    return ''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows)


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
    diagnostic_path = HERE/'diagnostic.json'
    spec = json.loads(diagnostic_path.read_text())
    files = spec['files']
    crossing = [json.loads(row) for row in files['crossing_history.jsonl'].splitlines()]
    trace = [json.loads(row) for row in files['trace.jsonl'].splitlines()]
    context = json.loads(files['junction_context.json'])
    if len(crossing) != len(trace) or len(crossing) < 3:
        raise ValueError('At least three aligned diagnostic source frames required')
    for point in trace:
        position = point['position']
        point.update(position_m=[position['x'], position['y'], position['z']],
                     speed_mph=point['speed_mps']/.44704,
                     velocity_mps=point.get('velocity_mps', [0, 0, 0]),
                     control=point.get('control',
                                       {'throttle': 0, 'steer': 0, 'brake': 1,
                                        'hand_brake': False, 'reverse': False}))
    files['trace.jsonl'] = lines(trace)
    native_frames, graphs, evidence = [], [], []
    for row, point in zip(crossing, trace):
        frame, time_s = row['frame'], row['time_s']
        if (point['frame'], point['time_s']) != (frame, time_s):
            raise ValueError('Crossing and trace frame/time differ')
        participants = []
        for actor_id, role, heading in HEADINGS:
            vertices = row[role]['body_vertices_xy_m']
            x = sum(vertex[0] for vertex in vertices)/len(vertices)
            y = sum(vertex[1] for vertex in vertices)/len(vertices)
            body = [[vertex[0], vertex[1], z] for vertex in vertices for z in (0, 1.5)]
            participants.append({
                'actor_id': actor_id, 'blueprint': 'vehicle.tesla.model3',
                'position_m': [x, y, 0], 'heading_deg': heading,
                'speed_mps': row[role].get('speed_mps', 0),
                'velocity_mps': row[role].get('velocity_mps', [0, 0, 0]),
                'body_vertices_m': body, 'accel_longitudinal_mps2': 0,
            })
        observations = {
            'frame': frame, 'time_s': time_s, 'participants': participants,
            'devices': [], 'relations': [],
            'participant_inventory': 'synthetic two-vehicle median-entry diagnostic',
            'map_context': {},
        }
        evidence.append({
            'original_frame': frame, 'replay_frame': frame, 'actor_id': 101,
            'recording_time_s': time_s, 'replay_simulation_time_s': time_s,
            'ego': {**{key: participants[0][key] for key in
                        ('position_m', 'heading_deg', 'speed_mps', 'body_vertices_m')},
                    'speed_provenance': 'synthetic_native_sample'},
            'world': {'weather': {'cloudiness': 0, 'precipitation': 0,
                                  'precipitation_deposits': 0, 'fog_density': 0,
                                  'sun_altitude_angle': 45, 'wetness': 0},
                      'road_projection': {'road_id': context['ego_road_id'],
                                          'section_id': 0, 'lane_id': -1,
                                          's_m': participants[0]['position_m'][EGO_ROAD_S_AXIS]
                                                 + EGO_ROAD_S_OFFSET}},
            'original_observations': observations,
            'timing': {}, 'visibility': {}, 'supporting_only': True,
        })
        base = f'graphs/base/{frame:08d}.pkl'
        abstract = f'graphs/abstract/{frame:08d}.pkl'
        native_frames.append({'frame': frame, 'simulation_time': time_s,
                              'base': base, 'abstract': abstract,
                              'nodes': 0, 'edges': 0,
                              'extraction_seconds': 0, 'capture_seconds': 0})
        for path in (base, abstract):
            graphs.append({'path': 'capture/native/'+path,
                           'attributes': {'frame': frame, 'simulation_time_s': time_s,
                                          'units': {'position': 'm'},
                                          'observed_evidence': observations},
                           'nodes': [], 'edges': []})
    xodr = ('<OpenDRIVE><header revMajor="1" revMinor="4" '
            'name="synthetic C125697 median-entry crossing" version="1" '
            'north="20" south="-20" east="30" west="0" vendor="worker"/>'
            + road(1, 'synthetic east-west highway', 0, 0, 0, -1)
            + road(2, 'synthetic north-south highway', 15, -15, 1.5707963267948966, 44)
            + '<junction name="synthetic crossing" id="44"><connection id="0" '
            'incomingRoad="1" connectingRoad="2" contactPoint="start">'
            '<laneLink from="-1" to="-1"/></connection></junction></OpenDRIVE>')
    files['capture/evidence.jsonl'] = lines(evidence)
    files['capture/native/frames.jsonl'] = lines(native_frames)
    files['capture/recorder_info.txt'] = ('Version: 1\nMap: OpenDriveMap\n'
                                          f' Create 101: vehicle.tesla.model3 (0) at {RECORDER_START}\n')
    files['road.xodr'] = xodr
    files['capture/manifest.json'] = json.dumps({
        'status': 'draft', 'acquisition': 'synthetic_diagnostic',
        'case_id': CASE, 'map': 'Carla/Maps/OpenDriveMap',
        'frames': len(crossing),
        'required_observations': ['ru.subject', 'ru.motor_vehicle',
                                  'kin.position', 'kin.velocity', 'kin.speed',
                                  'st.intersection', 'rel.bearing'],
        'extraction_confirmed': True,
        'sources': {'road.xodr': hashlib.sha256(xodr.encode()).hexdigest(),
                    'trace.jsonl': hashlib.sha256(files['trace.jsonl'].encode()).hexdigest()},
    }, indent=2, allow_nan=False)+'\n'
    spec['graphs'] = graphs
    diagnostic_path.write_text(json.dumps(spec, indent=2, allow_nan=False)+'\n')
    recipe = HERE/'diagnostic-recipe.json'
    data = json.loads(recipe.read_text())
    digest = hashlib.sha256(diagnostic_path.read_bytes()).hexdigest()
    for source in data['sources']:
        if source['source'].endswith('/diagnostic.json'):
            source['sha256'] = digest
    data['generator']['sha256'] = digest
    recipe.write_text(json.dumps(data, indent=2)+'\n')
    return {'diagnostic_sha256': digest, 'frames': len(crossing),
            'graph_sources': len(graphs), 'physical_evidence': False}


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))

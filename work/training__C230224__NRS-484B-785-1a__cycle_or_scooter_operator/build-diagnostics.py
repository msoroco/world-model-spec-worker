"""Build exact, source-hashed textual scooter diagnostics; no physical evidence."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
SPEEDS = {'controlled_1': 12, 'controlled_at_cap': 15, 'controlled_2': 17}
SOURCES = ('scooter_classification_source', 'scooter_mass_source',
           'scooter_motor_max_speed_source', 'path_surface_source',
           'path_continuity_source', 'path_access_source',
           'roadway_boundary_source', 'ordinance_applicability_source',
           'ordinance_review_source', 'scooter_handlebars_source',
           'scooter_electric_motor_source', 'scooter_riding_design_source',
           'scooter_propulsion_source', 'contrary_posting_source',
           'local_definition_applicability_source', 'assistive_device_intent_source')


def write(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n')


def main():
    for suffix, mph in SPEEDS.items():
        root = HERE / ('cases/' + suffix)
        root.mkdir(parents=True, exist_ok=True)
        frames = ''.join(json.dumps({'video_frame': i, 'carla_frame': 100+i, 'native_frame': 100+i,
                                     'time_s': round(i*.05, 8)})+'\n' for i in range(600))
        trace = ''.join(json.dumps({'video_frame': i, 'native_frame': 100+i,
                                    'source_kind': 'synthetic_native_sample',
                                    'device_actor_id': 1, 'rider_actor_id': 2,
                                    'device_center_xy_m': [round(i*mph*.44704*.05, 8), 0],
                                    'device_speed_mps': mph*.44704})+'\n' for i in range(600))
        canonical_trace = ''.join(json.dumps({'frame': 100+i, 'time_s': round(i*.05, 8),
            'position': {'x': round(i*mph*.44704*.05, 8), 'y': 0, 'z': 0},
            'position_m': [round(i*mph*.44704*.05, 8), 0, 0], 'heading_deg': 0,
            'speed_mps': mph*.44704, 'speed_mph': (mph*.44704)/.44704,
            'velocity_mps': [mph*.44704, 0, 0],
            'control': {}})+'\n' for i in range(600))
        road = ('<OpenDRIVE><header revMajor="1" revMinor="4" name="C230224-scooter-route" '
                'version="1" date="2026-11-25" north="8" south="-8" east="305" west="-5" '
                'vendor="full-train-worker"/><road id="1" name="route" length="300" junction="-1">'
                '<link/><planView><geometry s="0" x="-5" y="0" hdg="0" length="300"><line/>'
                '</geometry></planView><lanes><laneOffset s="0" a="0" b="0" c="0" d="0"/>'
                '<laneSection s="0"><left><lane id="1" type="biking" level="false">'
                '<width sOffset="0" a="2" b="0" c="0" d="0"/><roadMark sOffset="0" '
                'type="solid" color="white" width="0.1"/></lane></left><center><lane id="0" '
                'type="none" level="false"/></center><right><lane id="-1" type="driving" '
                'level="false"><width sOffset="0" a="3.5" b="0" c="0" d="0"/>'
                '<roadMark sOffset="0" type="solid" color="white" width="0.1"/>'
                '</lane></right></laneSection></lanes><objects/><signals/></road></OpenDRIVE>\n')
        evidence_rows = []
        replay_rows = []
        graphs = []
        for i in range(600):
            x, t, frame = round(i*mph*.44704*.05, 8), round(i*.05, 8), 100+i
            bbox = [[x+dx, dy, z] for dx in (-.35, .35)
                    for dy in (-.2, .2) for z in (0, 1.2)]
            graph_path = f'graphs/base/{frame:08d}.adapter.json'
            evidence_rows.append({'original_frame': frame, 'replay_frame': frame,
                'actor_id': 1, 'recording_time_s': t, 'replay_simulation_time_s': t,
                'ego': {'position_m': [x, 0, 0], 'heading_deg': 0,
                        'speed_mps': mph*.44704, 'speed_provenance': 'synthetic_native_sample',
                        'body_vertices_m': bbox}, 'synthetic_diagnostic': True,
                'world': {'weather': {'cloudiness': 0, 'precipitation': 0,
                                      'wetness': 0, 'fog_density': 0}}})
            replay_rows.append({'frame': frame, 'time_s': t, 'simulation_time': t,
                                'synthetic_diagnostic': True, 'adapter_graph': graph_path})
            graphs.append({'path': 'capture/native/'+graph_path,
                'attributes': {'frame': frame, 'simulation_time_s': t,
                               'synthetic_diagnostic': True,
                               'source': 'C230224 scooter-path software diagnostic'},
                'nodes': [{'id': 'ego', 'attributes': {'sem_class': 'ego',
                          'entity_id': 1, 'vertex': [x, 0, 0],
                          'forward': [1, 0, 0], 'threedbbox': bbox}}], 'edges': []})
        manifest = {'extraction_confirmed': True, 'frames': 600,
                    'required_observations': [],
                    'sources': {'trace.jsonl': hashlib.sha256(canonical_trace.encode()).hexdigest(),
                                'road.xodr': hashlib.sha256(road.encode()).hexdigest()},
                    'synthetic_diagnostic': True}
        context = {'assignment_id': AID, 'case_id': AID + '__' + suffix,
                   'requested_speed_mps': mph*.44704,
                   'review_kind': 'synthetic_diagnostic',
                   'device_subtype': 'electric_scooter', 'device_actor_id': 1,
                   'rider_actor_id': 2, 'path_box_xyxy_m': [-1, -2, 300, 2],
                   'scooter_rider_excluded_mass_lb': 45,
                   'scooter_motor_only_max_mph': 18,
                   'ordinance_exception_reviewed': True,
                   'path_access_reviewed': True}
        context.update({key: 'synthetic-fixture:' + key for key in SOURCES})
        spec = {'files': {'video_frames.jsonl': frames,
                          'native_rider_trace.jsonl': trace,
                          'scooter_context.json': json.dumps(context)+'\n',
                          'trace.jsonl': canonical_trace,
                          'road.xodr': road,
                          'capture/evidence.jsonl': ''.join(json.dumps(row, separators=(',', ':'))+'\n' for row in evidence_rows),
                          'capture/native/frames.jsonl': ''.join(json.dumps(row, separators=(',', ':'))+'\n' for row in replay_rows),
                          'capture/recorder_info.txt': 'Create 1: vehicle.scooter (0) at (0, 0, 0)\n',
                          'capture/manifest.json': json.dumps(manifest, separators=(',', ':'))+'\n'},
                'graphs': graphs,
                'videos': [{'path': name + '.mkv',
                            'frames': 600, 'width': (1920 if name == 'overview' else 1280),
                            'height': (1080 if name == 'overview' else 720),
                            'fps': 20, 'color': 'black'}
                           for name in ('overview', 'approach', 'reference_corner', 'driver_reference')]}
        spec_path = root/'diagnostic.json'
        write(spec_path, spec)
        rel = str(spec_path.relative_to(HERE.parents[1]))
        digest = hashlib.sha256(spec_path.read_bytes()).hexdigest()
        recipe = {'format': 'worker-fixture-recipe',
                  'sources': [{'path': 'diagnostic-input.json', 'source': rel,
                               'sha256': digest}],
                  'generator': {'source': rel, 'sha256': digest}}
        write(root/'recipe.json', recipe)
        print(json.dumps({'case': suffix, 'recipe': str(root/'recipe.json'),
                          'source_sha256': digest}, sort_keys=True))


if __name__ == '__main__':
    main()

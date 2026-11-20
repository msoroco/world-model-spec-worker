"""Inventory a reproducible synthetic C201084 source fixture; no Native claim."""
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE_NAMES = ('acquisition-provenance.json', 'native-actors.jsonl',
                'native-survey-readback.json', 'video_frames.jsonl')
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')


def build(source, case='reference'):
    if case not in ('reference', 'contrast'):
        raise ValueError('Unknown diagnostic case')
    source = Path(source).resolve()
    if '.runtime-work' not in source.parts:
        raise ValueError('Use an ignored synthetic diagnostic source')
    destination = HERE/f'fixtures/{case}-sources'
    destination.mkdir(parents=True, exist_ok=True)
    inventory = []

    def retain(name, content=None):
        path = destination/name
        path.parent.mkdir(parents=True, exist_ok=True)
        if content is None:
            shutil.copyfile(source/name, path)
        else:
            path.write_text(content)
        inventory.append({'path': name, 'source': str(path.relative_to(ROOT)),
                          'sha256': sha(path)})

    for name in SOURCE_NAMES:
        retain(name)
    actors = [json.loads(line) for line in (destination/'native-actors.jsonl').read_text().splitlines()]
    frames = [json.loads(line) for line in (destination/'video_frames.jsonl').read_text().splitlines()]
    if len(actors) != len(frames) or len(actors) != 600:
        raise ValueError('Expected a 600-frame synthetic source join')
    retain('road.xodr', '<OpenDRIVE><header revMajor="1" revMinor="4" name="synthetic_C201084" '
           'version="1" north="20" south="-20" east="100" west="-100"/>'
           '<road id="17" name="synthetic_access_road" length="200" junction="-1">'
           '<link/><planView><geometry s="0" x="-100" y="0" hdg="0" length="200">'
           '<line/></geometry></planView><elevationProfile><elevation s="0" a="0" b="0" c="0" d="0"/>'
           '</elevationProfile><lanes><laneOffset s="0" a="0" b="0" c="0" d="0"/>'
           '<laneSection s="0"><left/><center><lane id="0" type="none" level="false"/></center>'
           '<right><lane id="-1" type="driving" level="false"><width sOffset="0" a="3.7" b="0" c="0" d="0"/>'
           '</lane></right></laneSection></lanes><objects/><signals/></road></OpenDRIVE>\n')
    retain('capture/recorder_info.txt',
           'Synthetic C201084 diagnostic fixture; no CARLA recorder run.\n'
           'Create 41: vehicle.tesla.model3 (0) at (10, 1, 0)\n')
    graphs, evidence, native_frames = [], [], []
    sensors = [{'actor_id': 300+i, 'blueprint': 'sensor.camera.rgb'} for i in range(4)]
    for actor, frame in zip(actors, frames):
        number = frame['carla_frame']
        relative = f'graphs/base/{number:08d}.adapter.json'
        observed = {'frame': number, 'time_s': frame['time_s'],
                    'map_context': {'declared_public_way_road_ids': []},
                    'participants': [], 'rgb_sensors': sensors,
                    'world_settings': {'no_rendering_mode': False}}
        graphs.append({'path': 'capture/native/'+relative,
                       'attributes': {'frame': number, 'simulation_time_s': frame['time_s'],
                                      'observed_evidence': observed},
                       'nodes': [], 'edges': []})
        native_frames.append({'abstract': relative, 'adapter_graph': relative,
                              'base': relative, 'edges': 0, 'frame': number,
                              'nodes': 0, 'simulation_time': frame['time_s']})
        evidence.append({'original_frame': number, 'recording_time_s': frame['time_s'],
                         'replay_frame': number, 'replay_simulation_time_s': frame['time_s'],
                         'original_observations': observed, 'actor_id': actor['ego_actor_id'],
                         'ego': {'position_m': actor['ego_pose_xyz_m'],
                                 'heading_deg': actor['ego_yaw_deg'],
                                 'body_vertices_m': actor['ego_body_vertices_xyz_m'],
                                 'speed_mps': sum(x*x for x in actor['ego_velocity_xyz_mps'])**0.5,
                                 'speed_provenance': 'synthetic_native_sample'},
                         'world': {'weather': {'precipitation': 0., 'wetness': 0.,
                                               'sun_altitude_angle': 45.}}})
    manifest = {'acquisition': 'synthetic_fixture', 'case_id': HERE.name+'__'+case,
                'frames': 600, 'observation_contract_version': 2,
                'status': 'draft', 'extraction_confirmed': True,
                'complete_driving_lanes': False, 'required_observations': [],
                'sources': {**{name: sha(destination/name) for name in SOURCE_NAMES},
                            'road.xodr': sha(destination/'road.xodr'),
                            'trace.jsonl': sha(source/'trace.jsonl')}}
    retain('capture/manifest.json', json.dumps(manifest, sort_keys=True)+'\n')
    retain('capture/evidence.jsonl', ''.join(json.dumps(row, sort_keys=True)+'\n' for row in evidence))
    retain('capture/native/frames.jsonl', ''.join(json.dumps(row, sort_keys=True)+'\n' for row in native_frames))
    sizes = ((1920, 1080), (1280, 720), (1280, 720), (1280, 720))
    spec = {'files': {}, 'graphs': graphs,
            'videos': [{'path': name+'.mkv', 'frames': 600, 'width': size[0],
                        'height': size[1], 'fps': 20, 'color': 'black'}
                       for name, size in zip(CAMERAS, sizes)]}
    spec_path = HERE/f'draft-{case}-diagnostic-spec.json'
    write(spec_path, spec)
    recipe = {'format': 'worker-fixture-recipe', 'sources': inventory,
              'generator': {'source': str(spec_path.relative_to(ROOT)),
                            'sha256': sha(spec_path)}}
    recipe_path = HERE/f'draft-{case}-diagnostic-recipe.json'
    write(recipe_path, recipe)
    return {'sources': len(inventory), 'graphs': len(graphs),
            'recipe_sha256': sha(recipe_path)}


if __name__ == '__main__':
    import sys
    print(json.dumps(build(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else 'reference'), sort_keys=True))

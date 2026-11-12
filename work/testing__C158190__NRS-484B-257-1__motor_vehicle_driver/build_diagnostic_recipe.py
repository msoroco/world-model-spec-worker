"""Build a hash-bound synthetic saved-source fixture for the first yield case.

This exercises source handling only. Flat color frames and review labels are
diagnostic inputs and make no claim about a realized sign or road marking.
"""
import hashlib
import copy
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from worker_exchange.fixture_generator import generate, inspect
from worker_exchange.fixture_recipe import materialize

CAMERAS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv',
           'driver_reference.mkv')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def body_vertices(x, y):
    return [[x+dx, y+dy, z] for dx in (-1.5, 1.5)
            for dy in (-.7, .7) for z in (0, 1.5)]


def build():
    spec_path = HERE / 'tests/test_finalizer.py'
    loader = importlib.util.spec_from_file_location('c158190_test_finalizer', spec_path)
    module = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(module)
    with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work') as temp:
        source = Path(temp) / 'source'
        source.mkdir()
        module.FinalizerTests().sources(source)
        frame_count = 600
        frames = [{'video_frame': i, 'carla_frame': 100+i,
                   'time_s': round(5+i*.05, 6)} for i in range(frame_count)]
        controls = [{'frame': row['carla_frame'],
                     'yield_sign': {'actor_id': 12, 'blueprint': 'traffic.yield',
                                    'trigger_vertices_m': [[0, 0, 0]]*4},
                     'native_crosswalk_vertices_m': [], 'competing_controls': []}
                    for row in frames]
        trace = [{'frame': row['carla_frame'], 'time_s': row['time_s'],
                  'position_m': [-20+min(i, 40)*.5, 1.8, 0],
                  'position': {'x': -20+min(i, 40)*.5, 'y': 1.8, 'z': 0},
                  'heading_deg': 0, 'speed_mps': 4 if i == 0 else 2 if i == 1 else 0,
                  'speed_mph': (4 if i == 0 else 2 if i == 1 else 0) / .44704,
                  'velocity_mps': [4 if i == 0 else 2 if i == 1 else 0, 0, 0],
                  'control': {'throttle': 0, 'steer': 0, 'brake': 0,
                              'hand_brake': False, 'reverse': False}}
                 for i, row in enumerate(frames)]
        bodies = [{'frame': row['carla_frame'], 'time_s': row['time_s'],
                   'ego': {'body_vertices_m': body_vertices(trace[i]['position_m'][0], 1.8)},
                   'through': {'body_vertices_m': body_vertices(1.8, 20-min(i, 60)*.5)}}
                  for i, row in enumerate(frames)]
        for name, rows in (('video_frames.jsonl', frames),
                           ('control_inventory.jsonl', controls),
                           ('trace.jsonl', trace),
                           ('interaction_history.jsonl', bodies)):
            (source / name).write_text(''.join(json.dumps(row, separators=(',', ':'))+'\n'
                                                for row in rows))
        reference = json.loads((ROOT / 'work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/diagnostic.json').read_text())
        template = json.loads(reference['files']['capture/evidence.jsonl'].splitlines()[0])
        evidence, frame_index, graphs = [], [], []
        for i, row in enumerate(frames):
            frame, time_s = row['carla_frame'], row['time_s']
            event = copy.deepcopy(template)
            event.update(original_frame=frame, replay_frame=frame, actor_id=101,
                         recording_time_s=time_s, replay_simulation_time_s=time_s)
            event['ego'].update(position_m=trace[i]['position_m'],
                                speed_mps=trace[i]['speed_mps'],
                                body_vertices_m=bodies[i]['ego']['body_vertices_m'])
            event['world']['road_projection'].update(road_id=158190, lane_id=-1,
                                                      s_m=max(0, 20+trace[i]['position_m'][0]))
            observed = event['original_observations']
            observed.update(frame=frame, time_s=time_s,
                            world_settings={'no_rendering_mode': False},
                            rgb_sensors=[{'actor_id': 401+j, 'blueprint': 'sensor.camera.rgb'}
                                         for j in range(4)])
            observed['relations'] = [{'a': 101, 'b': 23, 'visible': i > 0}]
            samples = bodies[i]['ego']['body_vertices_m'] + [trace[i]['position_m']]
            event['visibility'] = {
                'visibility_criterion': 'any_of_nine_body_samples',
                'distance_convention': 'incoming driving-lane waypoint arc length to actor projected station',
                'eye_height_m': 1.5, 'scan_step_m': 1,
                'horizon_tolerance_m': 1, 'probe_distance_m': 20,
                'ego_body_samples_m': samples,
                'ego_projection': {'road_id': 158190 if trace[i]['position_m'][0] < -8 else 158192},
                'required_lane_ids': [-1],
                'approaches': [{'lane_id': -1, 'any_sample_clear_at_probe': True,
                                'any_body_sight_horizon': {'bound': 'at_least',
                                                           'distance_m': 25}}]}
            ego, through = observed['participants']
            ego.update(position_m=trace[i]['position_m'],
                       body_vertices_m=bodies[i]['ego']['body_vertices_m'],
                       speed_mps=trace[i]['speed_mps'],
                       velocity_mps=trace[i]['velocity_mps'])
            through.update(actor_id=23, position_m=[1.8, 20-min(i, 60)*.5, 0],
                           body_vertices_m=bodies[i]['through']['body_vertices_m'],
                           speed_mps=4, velocity_mps=[0, -4, 0])
            evidence.append(event)
            base = f'graphs/base/{frame:08d}.pkl'
            abstract = f'graphs/abstract/{frame:08d}.pkl'
            frame_index.append({'frame': frame, 'simulation_time': time_s,
                                'base': base, 'abstract': abstract,
                                'nodes': 1, 'edges': 0,
                                'extraction_seconds': 0, 'capture_seconds': 0})
            for graph_name in (base, abstract):
                attributes = {'frame': frame, 'simulation_time_s': time_s,
                              'units': {'position': 'm'}}
                if graph_name == base:
                    attributes['observed_evidence'] = observed
                sign = {'id': 'native-yield-sign',
                        'attributes': {'sem_class': 'traffic.yield',
                                       'landmark_type': '205', 'landmark_id': '12',
                                       'vertex': [-20, 3.8, 0]}}
                graphs.append({'path': 'capture/native/' + graph_name,
                               'attributes': attributes,
                               'nodes': [sign] if graph_name == base else [],
                               'edges': []})
        (source / 'capture/evidence.jsonl').write_text(''.join(json.dumps(e,separators=(',', ':'))+'\n'
                                                            for e in evidence))
        (source / 'capture/native').mkdir(exist_ok=True)
        (source / 'capture/native/frames.jsonl').write_text(''.join(json.dumps(e,separators=(',', ':'))+'\n'
                                                                 for e in frame_index))
        (source / 'capture/recorder_info.txt').write_text(reference['files']['capture/recorder_info.txt'])
        configuration = json.loads((HERE / 'config.json').read_text())
        manifest = {'status': 'draft', 'acquisition': 'synthetic_diagnostic',
                    'case_id': configuration['selected_case_id'],
                    'map': 'Carla/Maps/OpenDriveMap', 'frames': frame_count,
                    'observation_contract_version': 2,
                    'required_observations': configuration['required_atoms'],
                    'extraction_confirmed': True,
                    'sources': {'road.xodr': sha(source / 'road.xodr'),
                                'trace.jsonl': sha(source / 'trace.jsonl')}}
        (source / 'capture/manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        videos = []
        for name in CAMERAS:
            size = (1920, 1080) if name == 'overview.mkv' else (1280, 720)
            (source / name).unlink()
            videos.append({'path': name, 'frames': frame_count, 'width': size[0],
                           'height': size[1], 'fps': 20, 'color': 'black'})
        diagnostic = {'files': {}, 'graphs': graphs, 'videos': videos}
        inspect(diagnostic)
        generated = Path(temp) / 'generated'
        generated.mkdir()
        generate(diagnostic, generated)
        review = json.loads((source / 'rendered_marking_review.json').read_text())
        review['reviewer'] = 'synthetic-diagnostic-labels-no-physical-claim'
        review['reviewed_frame_count'] = frame_count
        review['reviewed_carla_frames'] = [row['carla_frame'] for row in frames]
        review['last_carla_frame'] = frames[-1]['carla_frame']
        review['source_sha256'] = {name: sha(generated / name) for name in CAMERAS}
        (source / 'rendered_marking_review.json').write_text(json.dumps(review, indent=2) + '\n')
        targets = HERE / 'diagnostic-sources'
        targets.mkdir(exist_ok=True)
        items = []
        for file in sorted(source.rglob('*')):
            if not file.is_file():
                continue
            relative = file.relative_to(source)
            if str(relative) == 'config.json':
                continue
            target = targets / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(file.read_bytes())
            items.append({'path': str(relative), 'source': str(target.relative_to(ROOT)),
                          'sha256': sha(target)})
        diagnostic_path = HERE / 'diagnostic.json'
        diagnostic_path.write_text(json.dumps(diagnostic, separators=(',', ':')) + '\n')
        if diagnostic_path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError('Diagnostic specification exceeds worker file size limit')
        recipe = {'format': 'worker-fixture-recipe', 'sources': items,
                  'generator': {'source': str(diagnostic_path.relative_to(ROOT)),
                                'sha256': sha(diagnostic_path)}}
        recipe_path = HERE / 'diagnostic-recipe.json'
        recipe_path.write_text(json.dumps(recipe, indent=2) + '\n')
    with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work') as temp:
        fixture = Path(temp) / 'fixture'
        receipt = materialize(ROOT, recipe_path, fixture)
        from finalizer import finalize
        (fixture / 'config.json').write_bytes((HERE / 'config.json').read_bytes())
        positive = finalize(fixture, fixture / 'analysis-report.json')
        negative = Path(temp) / 'negative'
        materialize(ROOT, recipe_path, negative)
        (negative / 'config.json').write_bytes((HERE / 'config.json').read_bytes())
        (negative / 'visibility_rays.jsonl').unlink()
        try:
            finalize(negative, negative / 'analysis-report.json')
        except ValueError as error:
            if 'visibility_rays.jsonl' not in str(error):
                raise
            negative_error = str(error)
        else:
            raise AssertionError('Missing original sight rays did not fail')
        return {'fixture': receipt, 'measurement': positive['measurements']['speed_at_closest_view_mps']['value'],
                'negative_error': negative_error, 'scope': '600-frame synthetic saved-source protocol only'}


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))

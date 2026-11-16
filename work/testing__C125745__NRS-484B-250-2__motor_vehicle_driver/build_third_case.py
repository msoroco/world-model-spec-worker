"""Build the separated-entry C125745 primary and seven-frame CPU diagnostic."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name + '__stop_ego_left_separated'


def emit(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(text):
    return [json.loads(line) for line in text.splitlines()]


def lines(values):
    return ''.join(json.dumps(value, allow_nan=False) + '\n' for value in values)


def build():
    runner = (HERE / 'runner.py').read_text()
    old = """                        progress={'ego':1,'other':1};stopped=False
                        for i in range(config['frames']):
                            clear=_other_conflict_clear(other,polygon)
                            progress,stopped,commands=step_pair(
                                carla,ego,other,scene,progress,stopped,clear,
                                i>=config['other_release_frame'])
"""
    new = """                        progress={'ego':1,'other':1};stopped=False
                        first_clear_frame=None
                        hold_frames=config.get('ego_hold_after_clear_frames',0)
                        if type(hold_frames) is not int or not 0<=hold_frames<config['frames']:
                            raise ValueError('Finite ego post-clear hold frames required')
                        for i in range(config['frames']):
                            clear=_other_conflict_clear(other,polygon)
                            if clear and first_clear_frame is None:first_clear_frame=i
                            gated_clear=clear and first_clear_frame is not None and i-first_clear_frame>=hold_frames
                            progress,stopped,commands=step_pair(
                                carla,ego,other,scene,progress,stopped,gated_clear,
                                i>=config['other_release_frame'])
"""
    assert old in runner
    runner = runner.replace(old, new)
    runner_path = HERE / 'third-runner.py'
    runner_path.write_text(runner)
    config = copy.deepcopy(json.loads((HERE / 'config.json').read_text()))
    config['selected_case_id'] = CASE
    config['ego_hold_after_clear_frames'] = 8
    config_path = HERE / 'third-config.json'
    emit(config_path, config)
    construction = copy.deepcopy(json.loads((HERE / 'construction.json').read_text()))
    construction['case_id'] = CASE
    construction['case_design'] = {'changed_relation': 'separated complete-body entry timing',
                                   'ego_hold_after_clear_frames': 8,
                                   'physical_acceptance_claimed': False}
    for file in construction['files']:
        if file['path'] == 'runner.py':
            file['source'] = str(runner_path.relative_to(ROOT))
            file['content'] = runner
        elif file['path'] == 'config.json':
            file['source'] = str(config_path.relative_to(ROOT))
            file['content'] = config_path.read_text()
        elif file['path'] == 'tests/test_bundle.py':
            file['content'] = file['content'].replace(HERE.name + '__stop_ego_left_near_time', CASE)
    construction_path = HERE / 'third-construction.json'
    emit(construction_path, construction)

    spec = copy.deepcopy(json.loads((HERE / 'diagnostic.json').read_text()))
    files = spec['files']
    original_crossing = rows(files['crossing_history.jsonl'])
    outside_ego = original_crossing[1]['ego']['body_vertices_xy_m']
    crossing = original_crossing[:2]
    for frame in range(102, 107):
        row = copy.deepcopy(original_crossing[2])
        row['frame'], row['time_s'] = frame, round(1 + (frame - 100) / 20, 5)
        if frame < 106:
            row['ego']['body_vertices_xy_m'] = copy.deepcopy(outside_ego)
        crossing.append(row)
    files['crossing_history.jsonl'] = lines(crossing)
    for name in ('video_frames.jsonl', 'trace.jsonl', 'controller_history.jsonl',
                 'capture/evidence.jsonl', 'capture/native/frames.jsonl'):
        original = rows(files[name])
        updated = original[:2]
        for row in crossing[2:]:
            item = copy.deepcopy(original[2])
            frame, time_s = row['frame'], row['time_s']
            if name == 'video_frames.jsonl':
                item.update(video_frame=frame - 100, carla_frame=frame, time_s=time_s)
            elif name == 'capture/native/frames.jsonl':
                item.update(frame=frame, simulation_time=time_s,
                            base=f'graphs/base/{frame:08d}.pkl',
                            abstract=f'graphs/abstract/{frame:08d}.pkl')
            elif name == 'capture/evidence.jsonl':
                item.update(original_frame=frame, replay_frame=frame,
                            recording_time_s=time_s, replay_simulation_time_s=time_s)
                ego = item['original_observations']['participants'][0]
                center = [sum(v[i] for v in row['ego']['body_vertices_xy_m']) / 4 for i in (0, 1)]
                ego['position_m'][:2] = center
                ego['body_vertices_m'] = [[x, y, z] for x, y in row['ego']['body_vertices_xy_m']
                                          for z in (0, 1.5)]
                item['ego']['position_m'][:2] = center
                item['ego']['body_vertices_m'] = copy.deepcopy(ego['body_vertices_m'])
                item['world']['road_projection']['s_m'] = center[0]
                item['original_observations'].update(frame=frame, time_s=time_s)
            else:
                item.update(frame=frame, time_s=time_s)
                if name == 'trace.jsonl':
                    center = [sum(v[i] for v in row['ego']['body_vertices_xy_m']) / 4 for i in (0, 1)]
                    item['position'].update(x=center[0], y=center[1])
                    item['position_m'][:2] = center
            updated.append(item)
        files[name] = lines(updated)
    templates = spec['graphs'][-2:]
    spec['graphs'] = spec['graphs'][:4]
    for row in crossing[2:]:
        frame, time_s = row['frame'], row['time_s']
        for template in templates:
            graph = copy.deepcopy(template)
            graph['path'] = graph['path'].replace('00000102', f'{frame:08d}')
            graph['attributes'].update(frame=frame, simulation_time_s=time_s)
            obs = graph['attributes']['observed_evidence']
            obs.update(frame=frame, time_s=time_s)
            ego = obs['participants'][0]
            ego['position_m'][:2] = [sum(v[i] for v in row['ego']['body_vertices_xy_m']) / 4
                                    for i in (0, 1)]
            ego['body_vertices_m'] = [[x, y, z] for x, y in row['ego']['body_vertices_xy_m']
                                      for z in (0, 1.5)]
            spec['graphs'].append(graph)
    manifest = json.loads(files['capture/manifest.json'])
    manifest['case_id'], manifest['frames'] = CASE, len(crossing)
    manifest['sources']['trace.jsonl'] = hashlib.sha256(files['trace.jsonl'].encode()).hexdigest()
    files['capture/manifest.json'] = json.dumps(manifest, indent=2, allow_nan=False) + '\n'
    for video in spec['videos']:
        video['frames'] = len(crossing)
    diagnostic_path = HERE / 'third-diagnostic.json'
    emit(diagnostic_path, spec)
    site = HERE / 'site.json'
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'site-source.json', 'source': str(site.relative_to(ROOT)),
                           'sha256': sha(site)}],
              'generator': {'source': str(diagnostic_path.relative_to(ROOT)),
                            'sha256': sha(diagnostic_path)}}
    emit(HERE / 'third-diagnostic-recipe.json', recipe)

    manifest_path = HERE / 'execution-manifest.json'
    execution = json.loads(manifest_path.read_text())
    third = {'case_id': CASE, 'kind': 'delivery', 'construction': construction_path.name,
             'construction_sha256': sha(construction_path),
             'physical_risk': {'status': 'physical',
                               'reason': 'Controller braking may compress measured body-entry separation'},
             'candidates': [], 'measurement_contract': 'measurement-contract.json',
             'measurement_procedure': {'entrypoint': 'finalizer.py'},
             'native_handoff': {'python_env_var': 'CARLA_PYTHON', 'host_env_var': 'CARLA_HOST',
                                'port_env_var': 'CARLA_PORT'},
             'fixture_recipe': str((HERE / 'third-diagnostic-recipe.json').relative_to(ROOT))}
    execution['cases'] = [entry for entry in execution['cases'] if entry['case_id'] != CASE] + [third]
    emit(manifest_path, execution)
    return {'case_id': CASE, 'construction_sha256': third['construction_sha256'],
            'diagnostic_sha256': recipe['generator']['sha256'],
            'original_frames': len(crossing), 'planned_entry_gap_s': 0.25}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))

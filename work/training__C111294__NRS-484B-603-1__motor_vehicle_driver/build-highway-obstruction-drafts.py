"""Build same-cell physical road-obstruction alternatives for the speed pair."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAIRS = (('probe_a', 'obstruction_probe_a'), ('probe_b', 'obstruction_probe_b'))


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Construction anchor missing or ambiguous: ' + old[:60])
    return source.replace(old, new, 1)


def runner_source(text):
    text = replace_once(text,
        'CHANNELS = ("ego_pose", "ego_speed", "observed_speed", "other_vehicle_pose")',
        'CHANNELS = ("ego_pose", "ego_speed", "observed_speed", "other_vehicle_pose", "obstruction_pose")')
    text = replace_once(text,
        '"map_readback_pending": True, "native_capture_pending": True,',
        '"obstruction_spawn_request": {"native_xy_m": [3.25, -5.0], "role": "highway_obstruction"},\n'
        '            "map_readback_pending": True, "native_capture_pending": True,')
    text = replace_once(text,
        'def native_sample(index: int, frame: int, elapsed_s: float, ego, other) -> dict:',
        'def native_sample(index: int, frame: int, elapsed_s: float, ego, other, obstruction) -> dict:')
    text = replace_once(text, 'et, ot = ego.get_transform(), other.get_transform()',
                        'et, ot, bt = ego.get_transform(), other.get_transform(), obstruction.get_transform()')
    text = replace_once(text, '"other_position_m": [ot.location.x, ot.location.y, ot.location.z],',
        '"other_position_m": [ot.location.x, ot.location.y, ot.location.z],\n'
        '            "obstruction_actor_id": obstruction.id,\n'
        '            "obstruction_blueprint": obstruction.type_id,\n'
        '            "obstruction_position_m": [bt.location.x, bt.location.y, bt.location.z],')
    text = replace_once(text, '"territorial_applicability_verified": False})',
        '"territorial_applicability_verified": False,\n'
        '            "highway_obstruction": {"kind": "static roadwork barrier",\n'
        '                "source_kind": "original Native actor and map readback",\n'
        '                "spawn_native_xy_m": [3.25, -5.0]}})')
    text = replace_once(text, '        owned.append(other)\n        # This seeds initial speed only.',
        '''        owned.append(other)
        barrier_bp = library.find("static.prop.streetbarrier")
        if barrier_bp is None:
            raise RuntimeError("Native street barrier blueprint unavailable")
        obstruction = world.spawn_actor(barrier_bp, carla.Transform(
            carla.Location(x=3.25, y=-5.0, z=.25), carla.Rotation(yaw=0)))
        owned.append(obstruction)
        # This seeds initial speed only.''')
    text = replace_once(text, 'row = native_sample(index, frame, elapsed, ego, other)',
                        'row = native_sample(index, frame, elapsed, ego, other, obstruction)')
    text = replace_once(text, '"other_vehicle_pose": row["other_position_m"]}',
                        '"other_vehicle_pose": row["other_position_m"],\n'
                        '                          "obstruction_pose": row["obstruction_position_m"]}')
    return text


def finalizer_source(text):
    marker = '\ndef finalize(folder: Path, contract: dict, expected_source_sha256: str) -> dict:\n'
    extra = '''
def measure_obstruction_approach(folder: Path, value: dict) -> dict:
    source = _rows(folder, "native_samples.jsonl")
    context = json.loads(_required(folder, "context.json").read_text())
    if not context.get("highway_obstruction") or len(source) != 600:
        raise ValueError("Missing source-bound highway obstruction")
    if any(not isinstance(row.get("obstruction_actor_id"), int) or
           row.get("obstruction_blueprint") != "static.prop.streetbarrier" or
           not isinstance(row.get("obstruction_position_m"), list) or
           len(row["obstruction_position_m"]) != 3 for row in source):
        raise ValueError("Missing original road obstruction trajectory")
    if len({row["obstruction_actor_id"] for row in source}) != 1:
        raise ValueError("Road obstruction identity changed")
    closest = min(math.dist(row["ego_position_m"], row["obstruction_position_m"])
                  for row in source)
    return dict(value, obstruction_actor_id=source[0]["obstruction_actor_id"],
                obstruction_trajectory_frames=len(source),
                minimum_body_center_distance_m=closest,
                highway_obstruction_causation_legally_verified=False)

'''
    text = replace_once(text, marker, '\n' + extra + marker)
    text = replace_once(text, 'value = measure_intersection_approach(rows, relation, road)',
        'value = measure_obstruction_approach(folder, measure_intersection_approach(rows, relation, road))')
    text = replace_once(text,
        'req["output_key"] != "intersection_approach" or req["method"] != "measure_intersection_approach"',
        'req["output_key"] != "obstruction_approach" or req["method"] != "measure_obstruction_approach"')
    text = replace_once(text, 'report["measurements"]["intersection_approach"]["value"]',
                        'report["measurements"]["obstruction_approach"]["value"]')
    text = replace_once(text, '"other_vehicle_pose": lambda row: row["other_position_m"],',
                        '"other_vehicle_pose": lambda row: row["other_position_m"],\n'
                        '        "obstruction_pose": lambda row: row["obstruction_position_m"],')
    return text


def build(old, new, candidate='primary'):
    label = f'current-v2-{old}-diagnostic' if candidate == 'primary' else f'current-v2-{old}-fallback1-diagnostic'
    construction = json.loads((HERE / label / 'construction.json').read_text())
    construction['case_id'] = construction['case_id'].replace(old, new)
    for entry in construction['files']:
        content = entry['content'].replace(old, new)
        if entry['path'] == 'runner.py':
            content = runner_source(content).replace('runtime/pipeline/scenario_pipeline', 'runtime/scenario_pipeline').replace('runtime/pipeline/python', 'runtime/python')
        elif entry['path'] == 'finalize.py':
            content = finalizer_source(content)
        elif entry['path'] == 'measurement-contract.json':
            data = json.loads(content)
            data['requirements'][0].update(disposition_index=5,
                output_key='obstruction_approach', method='measure_obstruction_approach',
                inputs=['native_samples.jsonl', 'road.xodr', 'context.json'])
            content = json.dumps(data, indent=2) + '\n'
        elif entry['path'] == 'config.json':
            data = json.loads(content)
            data['supported_case_ids'] = [HERE.name + '__' + new]
            data['recording_description']['channels'].append({
                'name': 'obstruction_pose', 'unit': 'metres', 'sampling_rate_hz': 20,
                'method': 'original Native frame-joined static actor readback',
                'time_window': '600 frames at 20 Hz', 'reference_frame': 'surveyed Native map',
                'uncertainty': '50 ms sampling and independent physical obstruction review'})
            data['recording_description']['context_inputs'].append({
                'name': 'highway_obstruction', 'unit': 'structured',
                'method': 'original Native roadwork barrier placement and independent highway review'})
            data['mandatory_channels'].append('obstruction_pose')
            content = json.dumps(data, indent=2) + '\n'
            construction['recording_description'] = data['recording_description']
        entry['content'] = content
    suffix = new if candidate == 'primary' else new + '-fallback1'
    target = HERE / 'obstruction-branch-drafts' / suffix
    target.mkdir(parents=True, exist_ok=True)
    (target / 'construction.json').write_text(json.dumps(construction, indent=2) + '\n')
    for entry in construction['files']:
        if entry.get('source'):
            continue
        path = target / entry['path']
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(entry['content'])
    return target


if __name__ == '__main__':
    for old, new in PAIRS:
        print(build(old, new))
        print(build(old, new, 'fallback1'))

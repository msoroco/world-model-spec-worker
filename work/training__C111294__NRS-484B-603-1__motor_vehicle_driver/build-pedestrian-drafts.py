"""Build separate same-cell pedestrian-hazard Native construction drafts."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAIRS = (('probe_a', 'pedestrian_probe_a'), ('probe_b', 'pedestrian_probe_b'))


def rename(text):
    for old, new in PAIRS:
        text = text.replace(old, new)
    return text


def runner_source(text):
    text = text.replace('CHANNELS = ("ego_pose", "ego_speed", "observed_speed", "other_vehicle_pose")',
                        'CHANNELS = ("ego_pose", "ego_speed", "observed_speed", "other_vehicle_pose", "pedestrian_pose")')
    text = text.replace('"map_readback_pending": True, "native_capture_pending": True,',
                        '"pedestrian_spawn_request": {"native_xy_m": [-10.0, -5.0], "role": "pedestrian"},\n            "map_readback_pending": True, "native_capture_pending": True,')
    text = text.replace('def native_sample(index: int, frame: int, elapsed_s: float, ego, other) -> dict:',
                        'def native_sample(index: int, frame: int, elapsed_s: float, ego, other, pedestrian) -> dict:')
    text = text.replace('et, ot = ego.get_transform(), other.get_transform()',
                        'et, ot, pt = ego.get_transform(), other.get_transform(), pedestrian.get_transform()')
    text = text.replace('"other_position_m": [ot.location.x, ot.location.y, ot.location.z],',
                        '"other_position_m": [ot.location.x, ot.location.y, ot.location.z],\n            "pedestrian_actor_id": pedestrian.id, "pedestrian_role": "pedestrian",\n            "pedestrian_blueprint": pedestrian.type_id,\n            "pedestrian_position_m": [pt.location.x, pt.location.y, pt.location.z],')
    text = text.replace('"territorial_applicability_verified": False})',
                        '"territorial_applicability_verified": False,\n            "pedestrian_hazard": {"route": "walk from x=-10 toward crossing at y=-5",\n                                  "source_kind": "original Native walker readback"}})')
    anchor = '        owned.append(other)\n        # This seeds initial speed only.'
    replacement = '''        owned.append(other)
        walker_blueprints = library.filter("walker.pedestrian.*")
        if not walker_blueprints:
            raise RuntimeError("Native pedestrian blueprint unavailable")
        walker_bp = walker_blueprints[0]
        if walker_bp.has_attribute("role_name"):
            walker_bp.set_attribute("role_name", "c111294_pedestrian_hazard")
        pedestrian = world.spawn_actor(walker_bp, carla.Transform(
            carla.Location(x=-10.0, y=-5.0, z=.5), carla.Rotation(yaw=0)))
        owned.append(pedestrian)
        # This seeds initial speed only.'''
    if anchor not in text:
        raise ValueError('Walker spawn anchor absent')
    text = text.replace(anchor, replacement)
    text = text.replace('                row = native_sample(index, frame, elapsed, ego, other)',
                        '                pedestrian.apply_control(carla.WalkerControl(\n                    direction=carla.Vector3D(x=1, y=0, z=0), speed=1.0))\n                row = native_sample(index, frame, elapsed, ego, other, pedestrian)')
    text = text.replace('"other_vehicle_pose": row["other_position_m"]}',
                        '"other_vehicle_pose": row["other_position_m"],\n                          "pedestrian_pose": row["pedestrian_position_m"]}')
    return text


def finalizer_source(text):
    marker = '\ndef finalize(folder: Path, contract: dict, expected_source_sha256: str) -> dict:\n'
    extra = '''
def measure_pedestrian_approach(folder: Path, value: dict) -> dict:
    source = _rows(folder, "native_samples.jsonl")
    context = json.loads(_required(folder, "context.json").read_text())
    if not context.get("pedestrian_hazard") or len(source) != 600:
        raise ValueError("Missing source-bound pedestrian hazard")
    if any(row.get("pedestrian_role") != "pedestrian" or
           not isinstance(row.get("pedestrian_actor_id"), int) or
           not isinstance(row.get("pedestrian_position_m"), list) or
           len(row["pedestrian_position_m"]) != 3 for row in source):
        raise ValueError("Missing original pedestrian trajectory")
    closest = min(math.dist(row["ego_position_m"], row["pedestrian_position_m"])
                  for row in source)
    return dict(value, pedestrian_actor_id=source[0]["pedestrian_actor_id"],
                pedestrian_trajectory_frames=len(source),
                minimum_body_center_distance_m=closest,
                pedestrian_collision_hazard_legally_verified=False)

'''
    if marker not in text:
        raise ValueError('Pedestrian measurement anchor absent')
    text = text.replace(marker, '\n' + extra + marker, 1)
    text = text.replace('value = measure_intersection_approach(rows, relation, road)',
                        'value = measure_pedestrian_approach(folder, measure_intersection_approach(rows, relation, road))')
    text = text.replace('req["output_key"] != "intersection_approach" or req["method"] != "measure_intersection_approach"',
                        'req["output_key"] != "pedestrian_approach" or req["method"] != "measure_pedestrian_approach"')
    text = text.replace('report["measurements"]["intersection_approach"]["value"]',
                        'report["measurements"]["pedestrian_approach"]["value"]')
    text = text.replace('"other_vehicle_pose": lambda row: row["other_position_m"],',
                        '"other_vehicle_pose": lambda row: row["other_position_m"],\n        "pedestrian_pose": lambda row: row["pedestrian_position_m"],')
    return text


def build(old, new, candidate='primary'):
    source = HERE / (f'current-v2-{old}-diagnostic/construction.json' if candidate == 'primary'
                     else f'current-v2-{old}-fallback1-diagnostic/construction.json')
    construction = json.loads(source.read_text())
    construction['case_id'] = rename(construction['case_id'])
    for entry in construction['files']:
        path = entry['path']; content = rename(entry['content'])
        if path == 'runner.py':
            content = runner_source(content)
        if path == 'finalize.py':
            content = finalizer_source(content)
        if path == 'measurement-contract.json':
            data = json.loads(content); row = data['requirements'][0]
            row.update(disposition_index=4, output_key='pedestrian_approach',
                       method='measure_pedestrian_approach',
                       inputs=['native_samples.jsonl', 'road.xodr', 'context.json'])
            content = json.dumps(data, indent=2) + '\n'
        if path == 'config.json':
            data = json.loads(content)
            data['supported_case_ids'] = [HERE.name + '__' + new]
            data['recording_description']['channels'].append({
                'name': 'pedestrian_pose', 'unit': 'metres', 'sampling_rate_hz': 20,
                'method': 'original Native frame-joined walker actor readback',
                'time_window': '600 frames at 20 Hz', 'reference_frame': 'surveyed Native map',
                'uncertainty': '50 ms sampling and physical walker trajectory review'})
            data['recording_description']['context_inputs'].append({
                'name': 'pedestrian_hazard', 'unit': 'structured',
                'method': 'original Native walker route and highway conflict review'})
            data['mandatory_channels'].append('pedestrian_pose')
            content = json.dumps(data, indent=2) + '\n'
            construction['recording_description'] = data['recording_description']
        entry['content'] = content
    label = new if candidate == 'primary' else new + '-fallback1'
    target = HERE / 'pedestrian-branch-drafts' / label
    target.mkdir(parents=True, exist_ok=True)
    (target / 'construction.json').write_text(json.dumps(construction, indent=2) + '\n')
    for entry in construction['files']:
        if entry.get('source'):
            continue
        path = target / entry['path']; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(entry['content'])
    return target


if __name__ == '__main__':
    for old, new in PAIRS:
        print(build(old, new))
        print(build(old, new, 'fallback1'))

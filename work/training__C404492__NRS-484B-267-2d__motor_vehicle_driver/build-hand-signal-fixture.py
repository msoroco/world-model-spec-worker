"""Build a synthetic source-shaped hand-signal compatibility fixture."""
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = HERE / 'current-fixture' / 'preparing_movement'
TARGET = HERE / 'current-fixture' / 'preparing_hand_signal'
CASE = HERE.name + '__preparing_hand_signal'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def main():
    if TARGET.exists():
        raise ValueError('Hand-signal fixture already exists; keep proof source stable')
    shutil.copytree(SOURCE, TARGET)
    context_path = TARGET / 'emergency_context.json'
    context = json.loads(context_path.read_text())
    context.update(case_id=CASE,
                   driver_hand_signal_visual_source='synthetic:driver-hand-pixels',
                   driver_signal_actor_identity_source='synthetic:driver-arm-identity',
                   driver_signal_window_source='synthetic:window-geometry',
                   driver_signal_visual_review_source='synthetic:reviewed-hand-pixels',
                   driver_signal_reviewer='synthetic reviewer',
                   driver_signal_actor_id=3)
    context.pop('visible_vehicle_movement_source', None)
    write(context_path, context)
    poses_path = TARGET / 'vehicle_poses.jsonl'
    poses = [json.loads(line) for line in poses_path.read_text().splitlines()]
    stopped_x = poses[79]['emergency']['x_m']
    offset = poses[119]['emergency']['x_m'] - stopped_x
    for index, pose in enumerate(poses):
        vehicle = pose['emergency']
        vehicle['driver_signal_actor_id'] = 3
        vehicle['driver_hand_signal_visible'] = 80 <= index < 120
        vehicle.pop('visible_vehicle_movement', None)
        if 80 <= index < 120:
            vehicle['x_m'] = stopped_x
            vehicle['speed_mps'] = 0.0
        elif index >= 120:
            vehicle['x_m'] -= offset
    poses_path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in poses))
    diagnostic = json.loads((HERE / 'current-preparing_movement-diagnostic.json').read_text())
    for index, graph in enumerate(diagnostic['graphs']):
        vehicle = next(node for node in graph['nodes'] if node['id'] == 'emergency')
        prior_x = vehicle['attributes']['vertex'][0]
        target_x = poses[index]['emergency']['x_m']
        shift = target_x - prior_x
        vehicle['attributes']['vertex'][0] = target_x
        for vertex in vehicle['attributes']['threedbbox']:
            vertex[0] += shift
    diagnostic_path = HERE / 'current-preparing_hand_signal-diagnostic.json'
    write(diagnostic_path, diagnostic)
    recipe = {'format': 'worker-fixture-recipe', 'sources': [],
              'generator': {'source': diagnostic_path.relative_to(ROOT).as_posix(),
                            'sha256': sha(diagnostic_path)}}
    for source in sorted(TARGET.rglob('*')):
        if source.is_file():
            recipe['sources'].append({'path': source.relative_to(TARGET).as_posix(),
                                      'source': source.relative_to(ROOT).as_posix(),
                                      'sha256': sha(source)})
    recipe_path = HERE / 'current-preparing_hand_signal-recipe.json'
    write(recipe_path, recipe)
    print(json.dumps({'case_id': CASE, 'recipe_sha256': sha(recipe_path),
                      'generator_sha256': sha(diagnostic_path),
                      'synthetic_only': True}))


if __name__ == '__main__':
    main()

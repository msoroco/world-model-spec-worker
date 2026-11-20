"""Survey-driven C201084 Native attempt; no physical or legal acceptance."""
import argparse
import json
from math import isfinite
from pathlib import Path

from fire_lane_survey import point, require
from native_capture import acquire_with_world_restore
from native_survey import inspect
from source_measurement import analyze


def _spawn_plan(survey, mapping, carla, road_id):
    z = survey.get('anchor_z_m')
    yaw = survey.get('spawn_yaw_deg')
    require(type(z) in (int, float) and isfinite(z) and
            type(yaw) in (int, float) and isfinite(yaw),
            'Native spawn needs finite surveyed elevation and yaw')
    result = []
    for role in ('ego', 'following'):
        xy = point(survey.get(role+'_spawn_xy_m'), role+' spawn')
        location = carla.Location(x=xy.x, y=xy.y, z=z)
        waypoint = mapping.get_waypoint(location, project_to_road=True,
                                        lane_type=carla.LaneType.Driving)
        require(waypoint is not None and waypoint.road_id == road_id,
                role+' spawn differs from surveyed road')
        blueprint = survey.get(role+'_blueprint')
        require(isinstance(blueprint, str) and blueprint.startswith('vehicle.'),
                role+' spawn lacks vehicle blueprint')
        result.append((blueprint, carla.Transform(location, carla.Rotation(yaw=yaw))))
    return result


def run(client, carla, survey, case, attempt,
        *, acquisition=acquire_with_world_restore, processor=analyze,
        controller_tuning=None):
    require(case in ('reference', 'contrast'), 'Unknown fire-lane case')
    world = client.get_world()
    plan = inspect(world, carla, survey)
    if controller_tuning is not None:
        plan['controller_tuning'] = controller_tuning
    mapping = world.get_map()
    spawns = _spawn_plan(survey, mapping, carla,
                         plan['fixed_context']['road_id'])
    sign = world.get_actors().find(plan['sign_readback']['actor_id'])
    require(sign is not None, 'Surveyed sign actor disappeared before capture')
    attempt = Path(attempt)
    if attempt.exists() and any(attempt.iterdir()):
        construction_path = attempt/'construction.json'
        require(construction_path.is_file() and
                (attempt/'config.json').is_file(),
                'Retain previous attempt; use a fresh output directory')
        construction = json.loads(construction_path.read_text())
        allowed = {Path(row['path']).parts[0]
                   for row in construction.get('files', [])}
        allowed.update(('construction.json', 'candidate-selection.json'))
        require({path.name for path in attempt.iterdir()} <= allowed,
                'Retain previous attempt; use a fresh output directory')
    attempt.mkdir(parents=True, exist_ok=True)
    actors = []
    try:
        library = world.get_blueprint_library()
        for blueprint_name, transform in spawns:
            actor = world.try_spawn_actor(library.find(blueprint_name), transform)
            require(actor is not None, 'Native vehicle spawn unavailable: '+blueprint_name)
            actors.append(actor)
        readback = attempt/'native-survey-readback.json'
        with readback.open('x') as stream:
            json.dump(plan, stream, indent=2, allow_nan=False)
            stream.write('\n')
        (attempt/'acquisition-provenance.json').write_text(json.dumps({
            'provenance_kind': 'native', 'diagnostic_fixture': False,
            'source': 'original_carla_actor_and_map_readback',
            'physical_acceptance_claimed': False,
        }, indent=2)+'\n')
        capture = acquisition(world, carla, actors[0], actors[1], sign,
                              plan, case, attempt)
        measured = processor(attempt, case)
        require(measured.get('physical_or_legal_completion_claimed') is False,
                'Source measurement must not claim legal/physical completion')
        (attempt/'source-measurement.json').write_text(
            json.dumps(measured, indent=2, allow_nan=False)+'\n')
        return {'case': case, 'capture': capture,
                'source_measurement': 'source-measurement.json',
                'physical_or_legal_completion_claimed': False}
    finally:
        for actor in reversed(actors):
            actor.destroy()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--survey', required=True, type=Path)
    parser.add_argument('--case', required=True, choices=('reference', 'contrast'))
    parser.add_argument('--attempt', required=True, type=Path)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(180)
    survey = json.loads(args.survey.read_text())
    print(json.dumps(run(client, carla, survey, args.case, args.attempt),
                     indent=2, sort_keys=True))


if __name__ == '__main__':
    main()

"""Survey-bound Native lead-traffic probe with retained original sources."""
import argparse
import json
from math import isfinite
from pathlib import Path

from exception_capture import acquire_with_world_restore
from exception_measurement import analyze
from fire_lane_survey import point, require
from native_runner import _spawn_plan
from native_survey import inspect


def _lead_spawn(survey, mapping, carla, road_id):
    xy = point(survey.get('lead_spawn_xy_m'), 'lead spawn')
    z, yaw = survey.get('anchor_z_m'), survey.get('spawn_yaw_deg')
    require(type(z) in (int, float) and isfinite(z) and
            type(yaw) in (int, float) and isfinite(yaw),
            'Lead spawn needs finite surveyed elevation and yaw')
    blueprint = survey.get('lead_blueprint')
    require(isinstance(blueprint, str) and blueprint.startswith('vehicle.'),
            'Lead spawn lacks vehicle blueprint')
    location = carla.Location(x=xy.x, y=xy.y, z=z)
    waypoint = mapping.get_waypoint(location, project_to_road=True,
                                    lane_type=carla.LaneType.Driving)
    require(waypoint is not None and waypoint.road_id == road_id,
            'Lead spawn differs from surveyed road')
    ego = point(survey.get('ego_spawn_xy_m'), 'ego spawn')
    require(xy.x > ego.x+5,
            'Lead spawn must be ahead of ego along authored straight approach')
    return blueprint, carla.Transform(location, carla.Rotation(yaw=yaw))


def run(client, carla, survey, attempt, *, acquisition=acquire_with_world_restore,
        processor=analyze, controller_tuning=None):
    world = client.get_world()
    plan = inspect(world, carla, survey)
    if controller_tuning is not None:
        plan['conflict_controller_tuning'] = controller_tuning
    mapping = world.get_map()
    road_id = plan['fixed_context']['road_id']
    spawns = _spawn_plan(survey, mapping, carla, road_id)
    spawns.append(_lead_spawn(survey, mapping, carla, road_id))
    sign = world.get_actors().find(plan['sign_readback']['actor_id'])
    require(sign is not None, 'Surveyed sign actor disappeared before conflict capture')
    plan['conflict_probe'] = {
        'lead_spawn_xy_m': survey['lead_spawn_xy_m'],
        'lead_blueprint': survey['lead_blueprint'],
        'statutory_necessity_verified': False,
        'original_review_required': True}
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
        for blueprint, transform in spawns:
            actor = world.try_spawn_actor(library.find(blueprint), transform)
            require(actor is not None, 'Native vehicle spawn unavailable: '+blueprint)
            actors.append(actor)
        (attempt/'native-survey-readback.json').write_text(
            json.dumps(plan, indent=2, allow_nan=False)+'\n')
        (attempt/'acquisition-provenance.json').write_text(json.dumps({
            'provenance_kind': 'native', 'diagnostic_fixture': False,
            'source': 'original_carla_actor_and_map_readback',
            'physical_acceptance_claimed': False,
            'statutory_necessity_claimed': False}, indent=2)+'\n')
        capture = acquisition(world, carla, actors[0], actors[1], actors[2],
                              sign, plan, attempt)
        measured = processor(attempt)
        require(measured.get('physical_or_legal_completion_claimed') is False and
                measured.get('statutory_necessity_verified') is False,
                'Conflict source measurement must reserve legal/physical review')
        (attempt/'source-measurement.json').write_text(
            json.dumps(measured, indent=2, allow_nan=False)+'\n')
        return {'capture': capture, 'lead_actor_id': actors[2].id,
                'source_measurement': 'source-measurement.json',
                'physical_or_legal_completion_claimed': False}
    finally:
        for actor in reversed(actors):
            actor.destroy()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--survey', required=True, type=Path)
    parser.add_argument('--attempt', required=True, type=Path)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(180)
    survey = json.loads(args.survey.read_text())
    print(json.dumps(run(client, carla, survey, args.attempt),
                     indent=2, sort_keys=True))


if __name__ == '__main__':
    main()

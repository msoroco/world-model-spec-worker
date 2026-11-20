"""Survey-bound Native traffic pair with optional lead actor and retained sources."""
import json
from pathlib import Path

from exception_runner import _lead_spawn
from fire_lane_survey import require
from native_runner import _spawn_plan
from native_survey import inspect
from traffic_pair_capture import acquire_with_world_restore
from traffic_pair_measurement import analyze


def run(client, carla, survey, mode, attempt,
        *, acquisition=acquire_with_world_restore, processor=analyze,
        controller_tuning=None):
    require(mode in ('near_lead', 'absent_lead'), 'Unknown traffic-pair mode')
    world = client.get_world()
    plan = inspect(world, carla, survey)
    destination = survey.get('traffic_pair_destination_xy_m')
    require(destination == [30, 1] and
            destination[0] > max(point[0] for point in
                survey['authored_fire_lane_polygon_xy_m']),
            'Traffic-pair destination must be beyond authored fire-lane segment')
    lead_present = mode == 'near_lead'
    require((survey.get('lead_spawn_xy_m') == [18, 1]) if lead_present else
            ('lead_spawn_xy_m' not in survey),
            'Traffic-pair lead construction differs from requested mode')
    plan['traffic_pair'] = {
        'mode':mode, 'lead_present':lead_present,
        'destination_xy_m':destination,
        'statutory_necessity_verified':False,
        'original_review_required':True}
    if lead_present:
        plan['conflict_probe'] = {
            'lead_spawn_xy_m':survey['lead_spawn_xy_m'],
            'lead_blueprint':survey['lead_blueprint'],
            'statutory_necessity_verified':False,
            'original_review_required':True}
    if controller_tuning is not None:
        plan['traffic_pair_controller_tuning'] = controller_tuning
    mapping = world.get_map()
    spawns = _spawn_plan(survey, mapping, carla,
                         plan['fixed_context']['road_id'])
    if lead_present:
        spawns.append(_lead_spawn(survey, mapping, carla,
                                  plan['fixed_context']['road_id']))
    sign = world.get_actors().find(plan['sign_readback']['actor_id'])
    require(sign is not None, 'Surveyed sign actor disappeared before traffic-pair capture')
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
        (attempt/'native-survey-readback.json').write_text(
            json.dumps(plan, indent=2, allow_nan=False)+'\n')
        (attempt/'acquisition-provenance.json').write_text(json.dumps({
            'provenance_kind':'native', 'diagnostic_fixture':False,
            'source':'original_carla_actor_and_map_readback',
            'physical_acceptance_claimed':False,
            'statutory_necessity_claimed':False}, indent=2)+'\n')
        capture = acquisition(world, carla, actors[0], actors[1],
                              actors[2] if lead_present else None,
                              sign, plan, attempt)
        measured = processor(attempt)
        require(measured['physical_or_legal_completion_claimed'] is False and
                measured['statutory_necessity_verified'] is False and
                measured['lead_present'] is lead_present,
                'Traffic-pair source measurement differs or overclaims completion')
        (attempt/'source-measurement.json').write_text(
            json.dumps(measured, indent=2, allow_nan=False)+'\n')
        return {'mode':mode,'capture':capture,
                'source_measurement':'source-measurement.json',
                'physical_or_legal_completion_claimed':False}
    finally:
        for actor in reversed(actors):
            actor.destroy()

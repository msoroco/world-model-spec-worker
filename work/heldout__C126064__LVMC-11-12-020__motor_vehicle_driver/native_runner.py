"""Native entrypoint for the two source-marked median-opening turn variants.

An independently reviewed site/authority record must be supplied at launch.
The record is retained as a claim; this runner never verifies municipal authority.
"""
import argparse
from hashlib import sha256
import json
from math import atan2, degrees
from pathlib import Path

from marked_course_native import CAMERAS, execute_marked_turn, execute_indication_turn
from turn_source_recorder import SourceRecorder

ASSIGNMENT = 'heldout__C126064__LVMC-11-12-020__motor_vehicle_driver'
VARIANTS = ('indicated_course', 'divergent_course')
FORMS = {'button': 'button', 'other_indication': 'other_indication'}


def case_form_variant(case_id):
    prefix = ASSIGNMENT + '__'
    if not case_id.startswith(prefix):
        raise ValueError('Unknown exact marked-turn case')
    suffix = case_id[len(prefix):]
    if suffix in VARIANTS:
        return 'marker', suffix
    for form in FORMS:
        lead = form + '_'
        if suffix.startswith(lead) and suffix[len(lead):] in VARIANTS:
            return form, suffix[len(lead):]
    raise ValueError('Unknown exact marked-turn case')


def prepare(case_id, source_path, expected_sha256):
    form, variant = case_form_variant(case_id)
    path = Path(source_path)
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('Marked-turn site source hash changed')
    record = json.loads(raw)
    for key in ('authority_document', 'municipal_jurisdiction_source',
                'intersection_source', 'authorization_source', 'intersection_id',
                'map_name', 'indicated_course_xy_m', 'divergent_course_xy_m'):
        if not record.get(key):
            raise ValueError('Marked-turn site source lacks ' + key)
    if form == 'marker':
        if not record.get('markers'):
            raise ValueError('Marked-turn site source lacks markers')
    elif record.get('indication_form') != form or not record.get('indications'):
        raise ValueError('Marked-turn site source lacks exact indication form')
    if record.get('median_opening_with_intersecting_road') is not True:
        raise ValueError('Marked-turn site lacks intersecting-road median opening')
    route = record['indicated_course_xy_m']
    if not isinstance(route, list) or len(route) < 3:
        raise ValueError('Marked-turn approach route incomplete')
    first, second = route[:2]
    if any(not isinstance(point, list) or len(point) != 2 for point in (first, second)):
        raise ValueError('Marked-turn approach coordinates incomplete')
    heading = degrees(atan2(second[1] - first[1], second[0] - first[0]))
    return {'case_id': case_id, 'variant': variant, 'indication_form': form,
            'source_path': str(path), 'source_sha256': expected_sha256,
            'map_name': record['map_name'],
            'approach_xy_m': first, 'approach_heading_deg': heading,
            'authority_verified': False}


def run(plan, output, host='127.0.0.1', port=2000):
    import carla  # Native dependency is intentionally lazy.

    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    client = carla.Client(host, int(port))
    client.set_timeout(30.)
    world = client.get_world()
    if world.get_map().name != plan['map_name']:
        raise ValueError('Marked-turn site source does not match Native map')
    prior_settings = world.get_settings()
    prior_sync = prior_settings.synchronous_mode
    prior_delta = prior_settings.fixed_delta_seconds
    ego = None
    recorder = None
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        x, y = plan['approach_xy_m']
        waypoint = world.get_map().get_waypoint(carla.Location(x=x, y=y, z=0.))
        if waypoint is None:
            raise ValueError('Marked-turn approach is off the Native road')
        transform = carla.Transform(carla.Location(x=x, y=y, z=waypoint.transform.location.z + .5),
                                    carla.Rotation(yaw=plan['approach_heading_deg']))
        ego = world.try_spawn_actor(world.get_blueprint_library().find('vehicle.tesla.model3'), transform)
        if ego is None:
            raise ValueError('Marked-turn ego spawn failed')
        sizes = {name: spec[2] for name, spec in CAMERAS.items()}
        recorder = SourceRecorder(output, sizes)

        def make_transform(x, y, z, yaw):
            return carla.Transform(carla.Location(x=x, y=y, z=z), carla.Rotation(yaw=yaw))

        if plan['indication_form'] == 'marker':
            result = execute_marked_turn(world, carla, ego, plan['case_id'], plan['source_path'],
                                         plan['source_sha256'], plan['variant'], make_transform,
                                         recorder)
        else:
            result = execute_indication_turn(world, carla, ego, plan['case_id'],
                                             plan['source_path'], plan['source_sha256'],
                                             plan['indication_form'], plan['variant'],
                                             make_transform, recorder)
        (output / 'native-turn-result.json').write_text(json.dumps(result, indent=2) + '\n')
        return result
    finally:
        try:
            if recorder is not None:
                recorder.close()
        finally:
            try:
                if ego is not None:
                    ego.destroy()
            finally:
                prior_settings.synchronous_mode = prior_sync
                prior_settings.fixed_delta_seconds = prior_delta
                world.apply_settings(prior_settings)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--site-source', required=True)
    parser.add_argument('--site-sha256', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    run(prepare(args.case, args.site_source, args.site_sha256), args.output, args.host, args.port)

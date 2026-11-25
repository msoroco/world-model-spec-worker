"""Write small, explicit CPU diagnostics for four exact C80909 route variants.

These are synthetic geometry packets. Native map, vehicle, camera coverage and
public-authority establishment have not been reviewed or established by them.
"""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = 'testing__C80909__NRS-484B-227-1__motor_vehicle_driver'
ROUTES = {
    'left_through_opening': [[5,-5],[15,-5],[15,0],[15,5]],
    'left_across_blocked_divider': [[5,-5],[9,-5],[9,0],[9,5]],
    'left_at_established_crossover': [[5,-5],[15,-5],[15,0],[15,5]],
    'left_right_roadway_continuation': [[5,-5],[15,-5],[25,-5]],
}


def build(root=ROOT):
    root = Path(root)
    for suffix, route in ROUTES.items():
        folder = root / 'cases' / suffix
        folder.mkdir(parents=True, exist_ok=True)
        source = folder / 'diagnostic-site.json'
        source.write_text(json.dumps({
            'format': 'worker-cpu-diagnostic-site',
            'status': 'synthetic_geometry_no_native_map_or_camera_review',
            'right_hand_roadway_xy_m': [[0,-10],[30,-10],[30,-2],[0,-2]],
            'destination_roadway_xy_m': [[0,2],[30,2],[30,10],[0,10]],
            'dividing_space_xy_m': [[0,-2],[30,-2],[30,2],[0,2]],
            'opening_xy_m': [[10,-2],[20,-2],[20,2],[10,2]],
            'barrier_footprints_xy_m': [
                [[0,-2],[8,-2],[8,2],[0,2]],
                [[22,-2],[30,-2],[30,2],[22,2]]]}, indent=2) + '\n')
        site = json.loads(source.read_text())
        context = {key: site[key] for key in (
            'right_hand_roadway_xy_m', 'destination_roadway_xy_m',
            'dividing_space_xy_m', 'opening_xy_m')}
        context.update(native_map_id='CPU_DIAGNOSTIC_NO_NATIVE_MAP',
                       divided_highway_source=source.name,
                       roadway_boundaries_source=source.name,
                       opening_geometry_source=source.name,
                       barrier_actors_source='planned_only_cpu_diagnostic',
                       other_vehicle_source='planned_only_cpu_diagnostic')
        refs = [{'path': source.name,
                 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}]
        packet = {'assignment_id': ASSIGNMENT,
                  'selected_case_id': ASSIGNMENT + '__' + suffix,
                  'source_review_status': 'authored_cpu_diagnostic',
                  'rate_hz': 20, 'frames': 600,
                  'native_map_name': 'CPU_DIAGNOSTIC_NO_NATIVE_MAP',
                  'source_refs': refs, 'divider_context': context,
                  'camera_poses': {name: [0,0,10,0,-20,0] for name in
                                   ('overview','approach','reference_corner','driver_reference')},
                  'barrier_sections': [
                      {'blueprint_id': 'unreviewed_barrier', 'pose': [4,0,0,0,0,0]},
                      {'blueprint_id': 'unreviewed_barrier', 'pose': [26,0,0,0,0,0]}],
                  'barrier_axis_xy': [1,0],
                  'planned_barrier_footprints_xy_m': site['barrier_footprints_xy_m'],
                  'ego_spawn_pose': [5,-5,0,0,0,0],
                  'other_spawn_pose': [25,-5,0,0,0,0],
                  'ego_route_xy_m': route,
                  'ego_body_radius_m': .4,
                  'other_route_xy_m': [[25,-5],[29,-5]],
                  'vehicle_blueprint_id': 'unreviewed_vehicle',
                  'native_spawn_lanes': {
                      'ego': {'road_id': 1, 'lane_id': 1},
                      'other': {'road_id': 1, 'lane_id': 1}}}
        if suffix == 'left_at_established_crossover':
            authority = folder / 'diagnostic-authority.txt'
            authority.write_text('CPU source-binding fixture only; no public-authority fact is asserted.\n')
            ref = {'path': authority.name,
                   'sha256': hashlib.sha256(authority.read_bytes()).hexdigest()}
            packet['source_refs'].append(ref)
            packet['authority_source_ref'] = ref
            packet['crossover_xy_m'] = site['opening_xy_m']
        (folder / 'site-plan.json').write_text(json.dumps(packet, indent=2) + '\n')


if __name__ == '__main__':
    build()

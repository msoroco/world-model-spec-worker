"""Materialize canonical four-view root package and source observation mapping."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def build():
    primary = json.loads((HERE / 'draft-candidates/probe_a/primary/construction.json').read_text())
    plan_path = HERE / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    ids = [entry['case_id'] for entry in plan['cases']]
    bundle = json.loads(json.dumps(primary))
    bundle['status'] = 'root_cpu_delivery_interface_original_unverified'
    bundle['measurement_plan'] = [{'case_id': case_id,
                                   'contract': f'current-v2-{case_id.rsplit("__", 1)[-1]}-measurement-contract.json'}
                                  for case_id in ids]
    bundle['static_checks'] = ['exact law/cell/actor', '600 frame source join',
                               'four synchronized source cameras', 'source-derived channels']
    existing = {row['name'] for row in bundle['recording_description']['channels']}
    required = {row['name'] for row in plan['observations'] if row.get('mandatory', True)}
    for name in sorted(required - existing):
        bundle['recording_description']['channels'].append({
            'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
            'method': 'Derived from retained Native body, actor and map readback after exact frame join',
            'time_window': 'entire 30 s / 600-frame attempt',
            'reference_frame': 'surveyed Native map and original frame identity',
            'uncertainty': '50 ms sampling; original physical and pixel review required'})
    additions = """            elif name=='st.lane_enters':value={'approach':geometry['lanes']['approach_right'],'intersection_entry_y_m':geometry['stop_line_y_m']}
            elif name=='rel.occupies':value={'ego_center_xy_m':sample['native_center_xy_m'],'approach_lane':geometry['lanes']['approach_right']}
            elif name=='st.lane_direction':value={'approach':geometry['lanes']['approach_right']['forward_xy'],'destination':geometry['lanes']['destination_right']['forward_xy']}
            elif name=='drv.turning':value={'right_turn_entry':sample['native_center_xy_m'][0]>=8 and sample['native_center_xy_m'][1]>-7}
            elif name=='ru.pedestrian':value={'walker_center_xy_m':sample['walker_center_xy_m'],'conflict_occupied':sample['walker_conflict_occupied']}
            elif name=='drv.entering_intersection':value={'ego_front_y_m':max(v[1] for v in sample['native_body_xy_m']),'stop_line_y_m':geometry['stop_line_y_m']}
"""
    for item in bundle['files']:
        if item['path'] == 'config.json':
            config = json.loads(item['content'])
            config['status'] = 'root_cpu_delivery_interface_original_unverified'
            config['supported_case_ids'] = ids
            config['recording_description'] = bundle['recording_description']
            pose = {'overview': 'fixed_world_intersection', 'approach': 'fixed_world_stop_line',
                    'reference_corner': 'ego_signal_view', 'driver_reference': 'fixed_world_destination'}
            fov = {'overview': 90, 'approach': 90, 'reference_corner': 85, 'driver_reference': 90}
            for camera in config['cameras']:
                camera['pose_strategy'] = pose[camera['name']]
                camera['fov_deg'] = fov[camera['name']]
            item['content'] = json.dumps(config, indent=2, allow_nan=False) + '\n'
        elif item['path'] == 'finalize.py':
            needle = "            elif name=='camera_frame_join':value=mapping[i]\n"
            if item['content'].count(needle) != 1:
                raise ValueError('Source-derived channel extension point changed')
            item['content'] = item['content'].replace(needle, needle + additions)
        target = HERE / item['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(item['content'])
    write(HERE / 'construction.json', bundle)
    plan['camera_plan'] = {'profile': 'overview1080-capability', 'duration_s': 30,
                           'composition': 'synchronized_four_view_primary', 'coverage': [
                               {'view': 'overview', 'subject': 'governing signal, full motor-vehicle body, right turn and pedestrians', 'interval': '0-30 s'},
                               {'view': 'approach', 'subject': 'stop line, right lane and nearest-side crosswalk', 'interval': '0-30 s'},
                               {'view': 'reference_corner', 'subject': 'driver view of governing red signal', 'interval': '0-30 s'},
                               {'view': 'driver_reference', 'subject': 'destination pedestrian and directed traffic conflict', 'interval': '0-30 s'}]}
    assignment = json.loads((ROOT / 'inputs' / HERE.name / 'assignment.json').read_text())
    terms = {item['term'] for item in assignment['source_observation_terms']}
    channels = {row['name'] for row in bundle['recording_description']['channels']}
    if not terms <= channels:
        raise ValueError('A frozen source observation term lacks a derived channel')
    plan['source_observation_mapping'] = {term: {
        'evidence': 'Frame-joined retained Native source and map-derived channel; synthetic CPU proof only',
        'channels': [term], 'source_refs': []} for term in sorted(terms)}
    for row in plan['requirement_dispositions']:
        row['evidence_or_gap'] = 'Two selected source-bound 600-frame current-v2 CPU cases and four fallbacks; original Native signal/body/pixel review and statutory conclusion pending.'
    plan['readiness'] = 'selected_cpu_preparation_original_native_pending'
    write(plan_path, plan)
    print(json.dumps({'root_construction_sha256': sha(HERE / 'construction.json'),
                      'case_plan_sha256': sha(plan_path), 'channels': len(channels)}))


if __name__ == '__main__':
    build()

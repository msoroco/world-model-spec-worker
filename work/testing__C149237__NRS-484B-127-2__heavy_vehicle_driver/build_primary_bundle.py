"""Bind current qualifying-truck source files into one exact CPU bundle."""
import hashlib
import json
from pathlib import Path


FOLDER = Path(__file__).resolve().parent
REPO = FOLDER.parents[1]
ASSIGNMENT = FOLDER.name
CASE = ASSIGNMENT + '__gap_below_500ft'
GAP_SUFFIXES = ('gap_below_500ft','gap_at_500ft','gap_above_500ft')
WIDTH_SUFFIXES = ('ego_width_below_80in','ego_width_at_80in','lead_width_below_80in')
TWO_LANE_SUFFIX = 'two_same_direction_lanes'
OVERTAKING_SUFFIX = 'overtaking'
FILES = ('runner.py', 'camera_setup.py', 'camera_encoder.py',
         'truck_site.py', 'two_lane_site.py', 'overtaking_site.py',
         'truck_construction.py', 'width_construction.py',
         'two_lane_construction.py', 'overtaking_construction.py',
         'truck_follow_controller.py', 'overtaking_controller.py',
         'truck_capture_sources.py', 'truck_measurements.py', 'finalizer.py',
         'native-map-plan/one-way-truck-road.xodr',
         'native-map-plan/two-lane-truck-road.xodr',
         'native-map-plan/overtaking-truck-road.xodr', 'tests/test_bundle.py',
         'config.json')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def physical_descriptor(overtaking=False):
    descriptor = {
        'criterion': 'following_progress',
        'motion_source': 'truck_history.jsonl',
        'body_key': 'ego.body_vertices_xy_m',
        'other_body_key': 'lead.body_vertices_xy_m',
        'context_sources': ['road_context.json'],
        'minimum_samples': 2,
        'minimum_progress_m': 20.0,
        'completion_goal_method': 'Engineering finite motion floor for the 45-second capture; not a statutory distance or legal verdict'}
    if overtaking:
        descriptor.update(criterion='overtake_pass',lateral_transition_m=1.0)
    return descriptor


def main():
    plan = json.loads((FOLDER/'case-plan.json').read_text())
    description = {'channels': [
        {'name': name, 'unit': unit, 'method': method,
         'time_window': 'entire captured interval',
         'reference_frame': 'original Native frame', 'sampling_rate_hz': 20,
         'uncertainty': 'sampled only; between-frame state unresolved'}
        for name, unit, method in (
            ('longitudinal_body_gap', 'm', 'source-bound projection of both truck bodies'),
            ('ego_overall_width', 'm', 'Native single-vehicle bounding box'),
            ('lead_overall_width', 'm', 'Native single-vehicle bounding box'),
            ('same_direction_lane_count', 'count', 'authored map and Native lane readback'))],
        'context_inputs': [{'name': 'conditions_permitting', 'unit': 'source review',
                            'method': 'road, traffic and camera source review; unresolved'}],
        'limitations': ['physical truck dimensions, following and visibility unverified',
                        'safe overtaker occupancy and legal judgment unresolved']}
    config = {'law_id': 'NRS-484B-127-2', 'cell_id': 'C149237',
              'actor': 'heavy_vehicle_driver', 'selected_case_id': CASE,
              'supported_case_ids': [case['case_id'] for case in plan['cases']],
              'rate_hz': 20, 'duration_s': 45,
              'blueprint_ids': ['vehicle.carlamotors.european_hgv',
                                'vehicle.carlamotors.carlacola'],
              'cameras': [{'name': name, 'width': width, 'height': height,
                           'fov_deg': 90, 'pose_strategy': strategy}
                          for name, width, height, strategy in (
                              ('overview', 1920, 1080, 'fixed elevated road overview'),
                              ('approach', 1280, 720, 'fixed following lane approach'),
                              ('reference_corner', 1280, 720, 'fixed side truck-body reference'),
                              ('driver_reference', 1280, 720, 'ego attached forward source'))],
              'required_atoms': ['ru.subject', 'ru.truck', 'kin.position',
                                 'kin.velocity', 'kin.speed', 'st.lane',
                                 'rel.surface_gap', 'rel.ahead_behind_in_lane'],
              'source_packets': [], 'recording_description': description,
              'physical_completion': physical_descriptor()}
    (FOLDER/'config.json').write_text(json.dumps(config,indent=2)+'\n')
    construction = {'case_id': CASE, 'law_id': config['law_id'],
                    'cell_id': config['cell_id'], 'actor': config['actor'],
                    'entrypoint': 'runner.py', 'recording_description': description,
                    'files': [{'path': name, 'content': (FOLDER/name).read_text(),
                               'source': str((FOLDER/name).relative_to(REPO))}
                              for name in FILES],
                    'status': 'draft',
                    'measurement_plan': {'raw_sources': ['truck_history.jsonl',
                                                         'road_context.json',
                                                         'video_frames.jsonl'],
                                         'analysis': 'truck_measurements.py',
                                         'legal_conclusion': 'unresolved'},
                    'static_checks': [{'name': 'runner_check', 'status': 'passed',
                                       'method': 'materialized --check and unit tests'}],
                    'termination_rules': ['45 seconds at 20 Hz',
                                          'abort on missing source frame or actor lane'],
                    'mechanisms': ['authored one-way OpenDRIVE road',
                                   'measured-length truck gap placement',
                                   'two-truck speed and lane-centering control',
                                   'four synchronized lossless source cameras']}
    (FOLDER/'construction.json').write_text(json.dumps(construction,indent=2)+'\n')
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': ASSIGNMENT,
                'runtime_manifest_sha256': sha(REPO/'runtime/SOURCE-MANIFEST.json'),
                'cases': [{'case_id': CASE, 'kind': 'delivery',
                           'construction': 'construction.json',
                           'construction_sha256': sha(FOLDER/'construction.json'),
                           'measurement_procedure': {'entrypoint': 'finalizer.py'},
                           'measurement_contract': 'measurement-contract.json',
                           'fixture_recipe': str((FOLDER/'fixture-recipe.json').relative_to(REPO)),
                           'candidate_risk': {'status': 'physical',
                                              'reason': 'realized truck body visibility and gap persistence can fail'},
                           'candidates': []}],
                'status': 'partial_first_case_offline_only'}
    (FOLDER/'gap-constructions').mkdir(exist_ok=True)
    for suffix in GAP_SUFFIXES[1:]+WIDTH_SUFFIXES+(TWO_LANE_SUFFIX,OVERTAKING_SUFFIX):
        case_id=ASSIGNMENT+'__'+suffix
        other_config=dict(config,selected_case_id=case_id)
        if suffix==OVERTAKING_SUFFIX:
            other_config['overtake']=True
            other_config['physical_completion']=physical_descriptor(overtaking=True)
        if suffix in WIDTH_SUFFIXES:
            other_config['width_candidate_blueprint_ids']=[
                'vehicle.carlamotors.carlacola','vehicle.carlamotors.firetruck',
                'vehicle.tesla.cybertruck','vehicle.carlamotors.european_hgv']
        other_construction=dict(construction,case_id=case_id)
        other_construction['files']=[dict(item,content=json.dumps(other_config,indent=2)+'\n')
                                     if item['path']=='config.json' else item
                                     for item in construction['files']]
        relative='gap-constructions/'+suffix+'.json'
        (FOLDER/relative).write_text(json.dumps(other_construction,indent=2)+'\n')
        manifest['cases'].append({'case_id':case_id,'kind':'delivery',
                                  'construction':relative,
                                  'construction_sha256':sha(FOLDER/relative),
                                  'measurement_procedure':{'entrypoint':'finalizer.py'},
                                  'measurement_contract':('measurement-contract-overtaking.json' if suffix==OVERTAKING_SUFFIX else 'measurement-contract.json'),
                                  'fixture_recipe':str((FOLDER/('fixture-recipe-'+suffix+'.json')).relative_to(REPO)),
                                  'candidate_risk':{'status':'physical',
                                    'reason':('no pinned Native truck asset may meet the exact 80-inch width category' if suffix in WIDTH_SUFFIXES else
                                              'Native two-lane map availability and same-direction lane interpretation may diverge' if suffix==TWO_LANE_SUFFIX else
                                              'opposing-lane pass may not complete or preserve safe clearance in Native motion' if suffix==OVERTAKING_SUFFIX else
                                              'realized truck body gap and visibility may diverge from the '+suffix+' target')},
                                  'candidates':[]})
    manifest['status']='partial_eight_primaries_unproved'
    (FOLDER/'execution-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')


if __name__ == '__main__':
    main()

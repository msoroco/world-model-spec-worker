"""Bind current qualifying-truck source files into one exact CPU bundle."""
import hashlib
import json
from pathlib import Path


FOLDER = Path(__file__).resolve().parent
REPO = FOLDER.parents[1]
ASSIGNMENT = FOLDER.name
CASE = ASSIGNMENT + '__gap_below_500ft'
FILES = ('runner.py', 'camera_setup.py', 'camera_encoder.py',
         'truck_site.py', 'truck_construction.py', 'truck_follow_controller.py',
         'truck_capture_sources.py', 'truck_measurements.py', 'finalizer.py',
         'native-map-plan/one-way-truck-road.xodr', 'tests/test_bundle.py',
         'config.json')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
              'source_packets': [], 'recording_description': description}
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
    (FOLDER/'execution-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')


if __name__ == '__main__':
    main()

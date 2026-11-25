"""Bind three exact intersection probes to source-owned Native delivery code."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ASSIGNMENT = HERE.name
CAMERAS = [('overview', 1920, 1080, 85, 'world'),
           ('approach', 1280, 720, 80, 'world'),
           ('reference_corner', 1280, 720, 85, 'world'),
           ('driver_reference', 1280, 720, 90, 'ego')]
CHANNELS = {
    'st.intersection': 'Original Native map readback and source camera pixels locate the actual intersection; definition review pending',
    'st.railway_crossing': 'Not asserted by the selected intersection branch; separate physical crossing would require a separate scene',
    'drv.approaching': 'Original full vehicle footprint relative to the source-hashed intersection entry',
    'rel.centre_distance': 'Original full vehicle footprint front to intersection entry; 30.48 m is an engineering proxy',
    'st.centre_line': 'Authored marked centerline plus original Native lane and map readback',
    'rel.occupies': 'Original Native four-corner footprint on either side of reviewed centerline',
    'drv.in_intersection': 'Original full vehicle footprint interval overlapping intersection bounds',
    'st.one_way_roadway': 'Original road direction context, opposed lane map readback and source pixels; applicability review pending',
}


def encode(value):
    return json.dumps(value, indent=2, ensure_ascii=False) + '\n'


def sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def build(suffix):
    case_id = ASSIGNMENT + '__' + suffix
    diagnostic_name = suffix_to_name(suffix)
    source = json.loads((HERE / f'current-v2-{diagnostic_name}-construction.json').read_text())
    files = {item['path']: item['content'] for item in source['files']}
    config = json.loads(files['config.json'])
    interval = {'probe_01': [], 'probe_02': [240, 359], 'probe_03': [400, 450]}[suffix]
    description = {'channels': [
        {'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
         'method': method, 'time_window': 'all original 600 Native frames / 30 s',
         'reference_frame': 'original Native map, body and camera frame',
         'uncertainty': '50 ms sample interval; physical and legal interpretation pending'}
        for name, method in CHANNELS.items()],
        'context_inputs': [{'name': 'two_way_intersection_source', 'unit': 'structured',
                            'method': 'Source-hashed OpenDRIVE and original Native map lane readback'}],
        'limitations': ['Authored intersection and CPU fixture do not prove public highway or legal intersection definition',
                        'Original Native centerline, body, crossing context and camera pixels require local review']}
    config.update(format='c111250-nrs-intersection-delivery-v2',
                  selected_case_id=case_id, supported_case_ids=[case_id],
                  candidate_id='primary', status='selected_native_runner_cpu_prepared',
                  requested_left_interval=interval, requested_speed_mps=3.4,
                  required_atoms=['kin.position', 'kin.heading', 'rel.occupies'],
                  source_packets=[], mandatory_channels=list(CHANNELS),
                  native_execution_integrated=True, original_native_observed=False,
                  physical_verified=False, legal_verdict=None,
                  case={'case_id': case_id, 'recording_description': description},
                  recording_description=description)
    if suffix == 'probe_03':
        config['control_phases'] = [
            {'name': 'right_approach', 'first_frame': 0, 'last_frame': 399,
             'target_lane_id': '-1', 'target_speed_mps': 3.4},
            {'name': 'left_traversal', 'first_frame': 400, 'last_frame': 450,
             'target_lane_id': '1', 'target_speed_mps': 3.4},
            {'name': 'right_departure', 'first_frame': 451, 'last_frame': 599,
             'target_lane_id': '-1', 'target_speed_mps': 3.4}]
    config['cameras'] = [{'name': name, 'fps': 20, 'width': width, 'height': height,
                          'fov_deg': fov, 'pose_strategy': attachment}
                         for name, width, height, fov, attachment in CAMERAS]
    files['assignment-source.json'] = (REPO / 'inputs' / ASSIGNMENT / 'assignment.json').read_text()
    files['road.xodr'] = (HERE / 'native/road.xodr').read_text()
    files['runner.py'] = (HERE / 'native/selected_runner.py').read_text()
    files['selected_capture.py'] = (HERE / 'native/selected_capture.py').read_text()
    files['finalize.py'] = (HERE / 'native/selected_finalize.py').read_text()
    files['zone_measure.py'] = (HERE / 'native/zone_measure.py').read_text()
    files = {name: content for name, content in files.items() if not name.startswith('tests/')}
    files['tests/test_selected.py'] = (HERE / 'native/test_selected.py').read_text()
    config['assignment_sha256'] = sha(files['assignment-source.json'])
    config['road_sha256'] = sha(files['road.xodr'])
    files['config.json'] = encode(config)
    construction = {'format': 'worker-inline-construction',
        'case_id': case_id, 'cell_id': 'C111250', 'law_id': 'NRS-484B-213-2b',
        'actor': 'motor_vehicle_driver', 'entrypoint': 'runner.py',
        'files': [{'path': name, 'content': content} for name, content in files.items()],
        'measurement_plan': {'method': 'Source-bound original Native body, lane, map and four-camera capture with saved-only zone measurement',
                             'status': 'cpu_prepared_original_native_unobserved'},
        'recording_description': description,
        'static_checks': ['assignment/road hashes', 'two-way intersection lanes',
                          'exact temporal lateral interval', 'four-camera 20 Hz profile'],
        'termination_rules': ['retain all 600 original frames',
                              'retain failure report and restore original world'],
        'mechanisms': ['OpenDRIVE opposed-lane intersection',
                       'source-bound straight-through lateral controller',
                       'four synchronized lossless cameras'],
        'status': 'selected_cpu_construction'}
    construction_path = HERE / f'selected-construction-{suffix}.json'
    construction_path.write_text(encode(construction))
    contract = json.loads((HERE / f'current-v2-{suffix_to_name(suffix)}-measurement-contract.json').read_text())
    contract['status'] = 'selected_delivery_cpu_prepared'
    contract_path = HERE / f'measurement-contract-{suffix}.json'
    contract_path.write_text(encode(contract))
    fixture = json.loads((HERE / f'current-v2-{diagnostic_name}-fixture-recipe.json').read_text())
    context = json.loads((HERE / f'current-v2-{diagnostic_name}-sources/road-context.json').read_text())
    context['two_way_intersection_source'] = True
    selected_context = HERE / f'selected-source/{suffix}/road-context.json'
    selected_context.parent.mkdir(parents=True, exist_ok=True)
    selected_context.write_text(encode(context))
    for item in fixture['sources']:
        if item['path'] == 'road-context.json':
            item['source'] = str(selected_context.relative_to(REPO))
            item['sha256'] = hashlib.sha256(selected_context.read_bytes()).hexdigest()
    selected_recipe = HERE / f'selected-recipe-{suffix}.json'
    selected_recipe.write_text(encode(fixture))
    return {'case_id': case_id, 'kind': 'delivery', 'id': 'primary',
            'construction': construction_path.name,
            'construction_sha256': hashlib.sha256(construction_path.read_bytes()).hexdigest(),
            'fixture_recipe': f'work/{ASSIGNMENT}/{selected_recipe.name}',
            'measurement_contract': contract_path.name,
            'measurement_procedure': {'entrypoint': 'finalize.py', 'output_schema': 'c111250-zone-measurement-v1'},
            'candidate_risk': {'status': 'physical',
                'reason': 'Original Native lane transition and full-body centerline crossing may not track the authored request'},
            'candidates': []}


def suffix_to_name(suffix):
    return {'probe_01': 'primary', 'probe_02': 'contrast',
            'probe_03': 'traversal'}[suffix]


def main():
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': ASSIGNMENT,
                'runtime_manifest_sha256': hashlib.sha256((REPO / 'runtime/SOURCE-MANIFEST.json').read_bytes()).hexdigest(),
                'status': 'diagnostic_selected_probe',
                'cases': [build(suffix) for suffix in ('probe_01', 'probe_02', 'probe_03')]}
    (HERE / 'selected-probe-manifest.json').write_text(encode(manifest))
    print(json.dumps({'case_ids': [case['case_id'] for case in manifest['cases']],
                      'manifest_sha256': hashlib.sha256((HERE / 'selected-probe-manifest.json').read_bytes()).hexdigest()}))


if __name__ == '__main__':
    main()

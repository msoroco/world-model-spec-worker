"""Build source-hashed draft bundles for all three planned projection boundaries."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
ASSIGNMENT = PACKAGE.name
SOURCE = ('runner.py', 'projection_measure.py', 'source_footprints.py',
          'finalize_saved.py')
TARGETS = {'below_15_ft': 14, 'at_15_ft': 15, 'above_15_ft': 16}
CANDIDATES = {
    'primary': {'load_height_m': 2.4, 'trailer_rear_m': -5,
                'camera_distance_m': 12},
    'fallback1': {'load_height_m': 1.8, 'trailer_rear_m': -5,
                  'camera_distance_m': 12},
    'fallback2': {'load_height_m': 2.4, 'trailer_rear_m': -7,
                  'camera_distance_m': 12},
    'fallback3': {'load_height_m': 2.4, 'trailer_rear_m': -5,
                  'camera_distance_m': 16},
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')


def build():
    batch = json.loads((PACKAGE.parents[1] / 'batch.json').read_text())
    plan = json.loads((PACKAGE / 'case-plan.json').read_text())
    entries = []
    for suffix, target in TARGETS.items():
        case_id = ASSIGNMENT + '__' + suffix
        requirements = []
        for index, disposition in enumerate(plan['requirement_dispositions']):
            if case_id not in disposition['case_ids']:
                continue
            requirements.append({
                'disposition_index': index,
                'requirement': disposition['requirement'],
                'source': disposition['source'],
                'output_key': ('text_0_projection' if index == 0 else
                               'reviewed_scope_0_projection'),
                'method': 'measure_text_0' if index == 0 else 'measure_scope_0',
                'value_type': 'number' if index == 0 else 'object',
                'kind': 'measured',
                'inputs': ['native-raw-actors.jsonl', 'reviewed-curb.json',
                           'native-curb-proposal.json'],
            })
        if len(requirements) != 2:
            raise ValueError('Both reviewed C229398 requirements must be measured')
        contract_path = PACKAGE / 'draft-measurement-contracts' / suffix / 'measurement-contract.json'
        write(contract_path, {
            'format': 'worker-measurement-contract', 'case_id': case_id,
            'requirements': requirements,
            'negative': {'remove': ['reviewed-curb.json'],
                         'error_contains': 'Missing required source: reviewed-curb.json'},
        })
        config = {
            'format': 'c229398-native-projection-draft-v1',
            'case_id': case_id, 'selected_case_id': case_id,
            'case_suffix': suffix, 'candidate_id': 'primary',
            'case': {'case_id': case_id}, 'cell_id': 'C229398',
            'law_id': 'LVMC-11-52-060', 'actor': 'motor_vehicle_driver',
            'target_projection_ft': target, 'duration_s': 30, 'rate_hz': 20,
            'required_atoms': ['kin.extent', 'rel.occupies', 'kin.position'],
            'source_packets': [], 'vehicle_blueprint': 'vehicle.tesla.model3',
            'load_filter': 'static.prop.*', 'trailer_filter': 'vehicle.*',
            'camera_distance_m': 12,
            'load_height_m': 2.4, 'trailer_rear_m': -5,
            'cameras': [{'name': name, 'width': 1920 if name == 'overview' else 1280,
                         'height': 1080 if name == 'overview' else 720,
                         'pose_strategy': 'ego_attached_fixed_offset', 'fov_deg': 90}
                        for name in ('overview', 'approach', 'reference_corner',
                                     'driver_reference')],
        }
        recording = {
            'channels': [{
                'name': 'maximum_projection_perpendicular_to_curb',
                'unit': 'ft', 'sampling_rate_hz': 20,
                'method': 'source-hashed Native actor poses, body extents and reviewed curb',
                'time_window': 'all 600 frames / 30 seconds',
                'reference_frame': 'reviewed Native curb line and street normal',
                'uncertainty': 'curb identity and actor attachment require physical review'}],
            'context_inputs': [{'name': 'reviewed_curb', 'unit': 'structured',
                                'method': 'Native map and original camera review'}],
            'limitations': ['Draft CPU checks do not establish original Native, '
                            'physical, or legal acceptance.'],
        }
        candidates = []
        primary_path = None
        for candidate_id, knobs in CANDIDATES.items():
            variant = json.loads(json.dumps(config))
            variant['candidate_id'] = candidate_id
            variant.update(knobs)
            files = [{'path': name, 'content': (HERE / name).read_text()}
                     for name in SOURCE]
            files.append({'path': 'tests/test_offline.py',
                          'content': (HERE / 'test_offline.py').read_text()})
            files.append({'path': 'config.json',
                          'content': json.dumps(variant, indent=2, sort_keys=True) + '\n'})
            construction = {
                'case_id': case_id, 'cell_id': 'C229398',
                'law_id': 'LVMC-11-52-060', 'actor': 'motor_vehicle_driver',
                'entrypoint': 'runner.py', 'files': files,
                'recording_description': recording,
                'measurement_plan': 'Review curb and attachments; convert all 600 original actor rows into footprints and measure the farthest streetward vertex.',
                'static_checks': ['exact boundary case', '600 frames at 20 Hz',
                                  'vehicle/load/trailer inventory', 'four source cameras'],
                'termination_rules': ['600 synchronized Native frames or explicit failure'],
                'mechanisms': ['rigid attached load and trailer proposal',
                               'position ego from full-part geometry',
                               'source-hashed original actor rows and four RGB streams'],
                'status': 'draft_cpu_offline_only',
            }
            path = (PACKAGE / 'draft-primary' / suffix / 'construction.json'
                    if candidate_id == 'primary' else
                    PACKAGE / 'draft-primary' / suffix / candidate_id / 'construction.json')
            write(path, construction)
            if candidate_id == 'primary':
                primary_path = path
            else:
                changed = [key for key in knobs if knobs[key] != CANDIDATES['primary'][key]]
                candidates.append({
                    'id': candidate_id,
                    'construction': str(path.relative_to(PACKAGE)),
                    'construction_sha256': sha(path),
                    'changed_knobs': changed,
                    'trigger': {
                        'source': 'original Native capture report and four-camera review',
                        'metric': 'observed attachment geometry, projection or framing',
                        'failure_condition': 'Primary candidate misses the requested curb projection, attachment, or camera framing review',
                    },
                })
        entries.append({
            'case_id': case_id, 'kind': 'delivery',
            'construction': str(primary_path.relative_to(PACKAGE)),
            'construction_sha256': sha(primary_path),
            'candidate_risk': {'status': 'physical',
                               'reason': 'Curb identity, rigid attachments and framing need Native review'},
            'measurement_procedure': {'entrypoint': 'finalize_saved.py',
                                      'output_schema': 'c229398-saved-projection-analysis-v1'},
            'measurement_contract': str(contract_path.relative_to(PACKAGE)),
            'candidates': candidates,
        })
    manifest_path = PACKAGE / 'draft-primary-manifest.json'
    write(manifest_path, {'format': 'worker-execution-manifest',
                          'assignment_id': ASSIGNMENT,
                          'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
                          'status': 'draft_cpu_offline_only', 'cases': entries})
    return {'manifest': str(manifest_path),
            'cases': [entry['case_id'] for entry in entries],
            'construction_sha256': [entry['construction_sha256'] for entry in entries]}


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))

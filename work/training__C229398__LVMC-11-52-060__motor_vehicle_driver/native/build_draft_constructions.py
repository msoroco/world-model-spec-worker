"""Build source-hashed draft bundles for all three planned projection boundaries."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
ASSIGNMENT = PACKAGE.name
SOURCE = ('runner.py', 'projection_measure.py', 'source_footprints.py')
TARGETS = {'below_15_ft': 14, 'at_15_ft': 15, 'above_15_ft': 16}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')


def build():
    batch = json.loads((PACKAGE.parents[1] / 'batch.json').read_text())
    entries = []
    for suffix, target in TARGETS.items():
        case_id = ASSIGNMENT + '__' + suffix
        config = {
            'format': 'c229398-native-projection-draft-v1',
            'case_id': case_id, 'selected_case_id': case_id,
            'case_suffix': suffix, 'candidate_id': 'primary',
            'case': {'case_id': case_id}, 'cell_id': 'C229398',
            'law_id': 'LVMC-11-52-060', 'actor': 'motor_vehicle_driver',
            'target_projection_ft': target, 'duration_s': 30, 'rate_hz': 20,
            'required_atoms': ['ru.vehicle', 'kin.extent', 'st.road_edge',
                               'rel.occupies', 'kin.position'],
            'source_packets': [], 'vehicle_blueprint': 'vehicle.tesla.model3',
            'load_filter': 'static.prop.*', 'trailer_filter': 'vehicle.*',
            'camera_distance_m': 12,
            'cameras': [{'name': name, 'width': 1280, 'height': 720}
                        for name in ('overview', 'curb', 'load', 'trailer')],
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
        files = [{'path': name, 'content': (HERE / name).read_text()}
                 for name in SOURCE]
        files.append({'path': 'tests/test_offline.py',
                      'content': (HERE / 'test_offline.py').read_text()})
        files.append({'path': 'config.json',
                      'content': json.dumps(config, indent=2, sort_keys=True) + '\n'})
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
        path = PACKAGE / 'draft-primary' / suffix / 'construction.json'
        write(path, construction)
        entries.append({
            'case_id': case_id, 'kind': 'delivery',
            'construction': str(path.relative_to(PACKAGE)),
            'construction_sha256': sha(path),
            'candidate_risk': {'status': 'physical',
                               'reason': 'Curb identity, rigid attachments and framing need Native review'},
            'measurement_procedure': {'entrypoint': 'projection_measure.py',
                                      'output_schema': 'c229398-curb-projection-measurement-v1'},
            'candidates': [],
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

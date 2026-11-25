"""Bind two exact unselected construction bundles to this frozen assignment."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parent
ROOT = ASSIGNMENT.parents[1]
SOURCES = ('runner.py', 'route_meter.py', 'finalize.py', 'road.xodr', 'test_offline.py')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    batch = json.loads((ROOT / 'batch.json').read_text())
    plan = json.loads((ASSIGNMENT / 'case-plan.json').read_text())
    description = {'channels': [
        {'name': 'kin.position', 'unit': 'm', 'sampling_rate_hz': 20,
         'method': 'Original pedestrian transform at each Native frame',
         'time_window': 'full 600-frame crossing capture',
         'reference_frame': 'authored road coordinates and original frame map',
         'uncertainty': '50 ms frame bracket plus Native pose uncertainty'},
        {'name': 'kin.path_length', 'unit': 'm', 'sampling_rate_hz': 20,
         'method': 'Sum distances of source-joined pedestrian positions',
         'time_window': 'entry through opposite-curb exit',
         'reference_frame': 'authored road coordinates',
         'uncertainty': 'Depends on observed entry and exit and frame sampling'},
        {'name': 'st.road_edge', 'unit': 'structured', 'sampling_rate_hz': 20,
         'method': 'Authored curb segments independently verified against Native map and pixels',
         'time_window': 'full crossing capture',
         'reference_frame': 'authored road coordinates',
         'uncertainty': 'Map projection and actual curb status require independent audit'},
        {'name': 'st.crosswalk', 'unit': 'structured', 'sampling_rate_hz': 20,
         'method': 'Authored absence of crosswalk independently verified against Native map and pixels',
         'time_window': 'full crossing capture',
         'reference_frame': 'authored road coordinates',
         'uncertainty': 'Crosswalk exception cannot be settled by authored claim alone'},
    ], 'context_inputs': [],
        'limitations': ['Measured route alternatives are not legal thresholds',
                        'Native execution and independent source audit remain unverified']}
    manifest = {'format': 'worker-unselected-draft-construction-manifest-v1',
                'assignment_id': ASSIGNMENT.name,
                'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
                'status': 'draft_not_selected', 'cases': []}
    for case, condition in zip(plan['cases'], ('right_angle', 'longer_diagonal')):
        case_id = case['case_id']
        config = {'case_id': case_id, 'selected_case_id': case_id,
                  'cell_id': 'C230222', 'law_id': 'LVMC-11-30-050', 'actor': 'pedestrian',
                  'condition': condition, 'duration_s': 30, 'rate_hz': 20,
                  'walker_speed_mps': 1.8,
                  'road_geometry_sha256': sha(HERE / 'road.xodr'),
                  'required_atoms': ['ru.pedestrian', 'kin.position', 'st.road_edge'],
                  'source_packets': [],
                  'cameras': [{key: spec[key] for key in ('name', 'width', 'height')}
                              for spec in json.loads(json.dumps([
                                  {'name': 'overview', 'width': 1280, 'height': 720},
                                  {'name': 'entry_curb', 'width': 1280, 'height': 720},
                                  {'name': 'opposite_curb', 'width': 1280, 'height': 720},
                                  {'name': 'route_profile', 'width': 1280, 'height': 720}]))],
                  'recording_description': description,
                  'case': {'case_id': case_id, 'recording_description': description}}
        files = [{'path': name if name != 'test_offline.py' else 'tests/test_offline.py',
                  'content': (HERE / name).read_text()} for name in SOURCES]
        files.append({'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'})
        construction = {'case_id': case_id, 'cell_id': 'C230222',
                        'law_id': 'LVMC-11-30-050', 'actor': 'pedestrian',
                        'entrypoint': 'runner.py', 'files': files,
                        'recording_description': description,
                        'measurement_plan': {'method': 'Original source joined route/curb/crosswalk geometry',
                                             'status': 'unselected_cpu_draft'},
                        'static_checks': ['30 seconds at 20 Hz', 'four original RGB cameras',
                                          'exact law/cell/actor binding'],
                        'termination_rules': ['600 original frames', 'retain encoder and restoration evidence'],
                        'mechanisms': ['Native controlled pedestrian crossing', 'source route measurements'],
                        'status': 'unselected_cpu_draft_physical_unverified'}
        suffix = 'condition_a' if condition == 'right_angle' else 'condition_b'
        path = ASSIGNMENT / 'draft-route' / suffix / 'construction.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(construction, indent=2) + '\n')
        manifest['cases'].append({'case_id': case_id, 'kind': 'draft_not_selected',
                                  'id': 'primary', 'construction': str(path.relative_to(ASSIGNMENT)),
                                  'construction_sha256': sha(path), 'candidates': [],
                                  'candidate_risk': {'status': 'physical',
                                      'reason': 'Native path, road geometry and exception require source audit'}})
    out = ASSIGNMENT / 'draft-route-manifest.json'
    out.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'manifest': str(out), 'sha256': sha(out), 'cases': len(manifest['cases'])}))


if __name__ == '__main__':
    build()

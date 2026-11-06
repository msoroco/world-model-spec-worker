"""Materialize exact unselected curb constructions for pinned CPU offline checks."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NATIVE = HERE / 'native'
IDS = ('primary', 'fallback1', 'fallback2', 'fallback3')
SOURCES = {'runner.py': 'runner.py', 'geometry.py': 'geometry.py',
           'engineering.py': 'engineering.py', 'vehicle_policy.py': 'vehicle_policy.py',
           'curb.py': 'curb.py', 'triggers.py': 'triggers.py',
           'finalize.py': 'finalize.py', 'road.xodr': 'road.xodr',
           'tests/test_offline.py': 'test_offline.py'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def recording_description():
    channels = []
    for name, unit, method in (
        ('kin.position', 'm', 'Original pedestrian and vehicle transforms plus pedestrian footprint'),
        ('kin.speed', 'm/s', 'Original pedestrian and vehicle velocity magnitudes'),
        ('kin.accel_longitudinal', 'm/s2', 'Frame-differenced pedestrian velocity with event bracket'),
        ('rel.occupies', 'structured', 'Full pedestrian footprint versus authored curb edge and vehicle path'),
        ('drv.time_to_conflict', 's', 'Vehicle distance and speed at pedestrian roadway entry'),
        ('drv.stopping_distance', 'm', 'Conditional range from source speed and documented driver assumptions'),
        ('curb_camera_frame_join', 'structured', 'Original RGB source frame hashes and Native frame/time joins'),
    ):
        channels.append({'name': name, 'unit': unit, 'sampling_rate_hz': 20,
                         'method': method, 'time_window': 'entire 240-frame 12-second approach',
                         'reference_frame': 'Native source frame/time and authored road coordinates',
                         'uncertainty': '50 ms event brackets; actual driver capability and legal status unverified'})
    return {'channels': channels,
            'context_inputs': [{'name': 'introductory_exceptions', 'unit': 'structured',
                                'method': 'Independent statutory and original context review'}],
            'limitations': ['Conditional stopping assumptions are not measured driver capability',
                            'Original vehicle control, curb status and camera pixels require independent saved audit',
                            'Curb timing and calculated margin alone do not assign a legal verdict']}


def build():
    batch = json.loads((ROOT / 'batch.json').read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    common = {name: (NATIVE / source).read_text() for name, source in SOURCES.items()}
    description = recording_description()
    manifest = {'format': 'worker-unselected-draft-construction-manifest-v1',
                'assignment_id': HERE.name,
                'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
                'status': 'draft_not_selected', 'cases': []}
    for case in plan['cases']:
        case_id = case['case_id']
        suffix = case_id.rsplit('__', 1)[-1]
        if suffix not in ('probe_1', 'probe_2'):
            continue
        contract = HERE / 'draft-curb' / suffix / 'measurement-contract.json'
        if json.loads(contract.read_text())['case_id'] != case_id:
            raise ValueError('Curb contract identity differs')
        entry = {'case_id': case_id, 'kind': 'draft_not_selected',
                 'candidate_risk': {'status': 'physical',
                                    'reason': 'Native curb, actor dynamics, driver capability and statutory exceptions remain unverified'},
                 'measurement_contract': str(contract.relative_to(HERE)),
                 'measurement_procedure': {'entrypoint': 'finalize.py',
                                           'output_schema': 'worker-analysis-report-v1'},
                 'candidates': []}
        for ident in IDS:
            source_plan = json.loads((HERE / 'draft-candidates' / suffix / ident / 'construction.json').read_text())
            e = source_plan['engineering']
            config = {'case_id': case_id, 'selected_case_id': case_id,
                      'case_suffix': suffix, 'candidate_id': ident,
                      'case': {'case_id': case_id}, 'cell_id': 'C230222',
                      'law_id': 'NRS-484B-283-1b', 'actor': 'pedestrian',
                      'duration_s': 12, 'rate_hz': 20,
                      'required_atoms': ['ru.pedestrian', 'kin.position', 'kin.speed',
                                         'st.road_edge', 'rel.occupies'],
                      'source_packets': [],
                      'cameras': [{'name': name, 'width': width, 'height': height} for name, width, height in (
                          ('overview', 1920, 1080), ('vehicle_approach', 1280, 720),
                          ('curb_side', 1280, 720), ('curb_close', 1280, 720))],
                      'recording_description': description,
                      'status': 'unselected_curb_native_capture_proposal'}
            if (e['camera_width'], e['camera_height']) != (1280, 720):
                raise ValueError('Camera dimensions differ')
            files = [{'path': name, 'content': content} for name, content in common.items()]
            files.append({'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'})
            construction = {'case_id': case_id, 'cell_id': 'C230222',
                            'law_id': 'NRS-484B-283-1b', 'actor': 'pedestrian',
                            'entrypoint': 'runner.py', 'files': files,
                            'recording_description': description,
                            'measurement_plan': {'method': 'Original curb departure, roadway entry and conditional stopping brackets',
                                                 'status': 'synthetic_cpu_prototype'},
                            'static_checks': ['authored road/curb geometry',
                                              '20 Hz controlled pedestrian departure', 'four original RGB cameras'],
                            'termination_rules': ['240 original frames',
                                                  'retain failure, encoder and world restoration evidence'],
                            'mechanisms': ['same-cell curb-entry comparison', 'moving Native pedestrian and vehicle',
                                           'original-frame source hashes with independent audit required'],
                            'status': 'unselected_cpu_draft_physical_yield_unverified'}
            path = HERE / 'draft-bundles' / suffix / ident / 'construction.json'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(construction, indent=2) + '\n')
            ref = {'id': ident, 'construction': str(path.relative_to(HERE)),
                   'construction_sha256': sha(path)}
            if ident == 'primary':
                entry.update(ref)
            else:
                rule = source_plan['trigger']
                ref.update(trigger={'source': rule['source'], 'metric': rule['metric'],
                                    'failure_condition': f"{rule['metric']} {rule['threshold']}"},
                           changed_knobs=[{'fallback1': 'pedestrian spawn and two-meter pre-roll',
                                           'fallback2': 'bounded pedestrian acceleration control',
                                           'fallback3': 'curb camera distance',
                                          }[ident]])
                entry['candidates'].append(ref)
        manifest['cases'].append(entry)
    (HERE / 'draft-execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'unselected_exact_bundles': 8, 'cases': 2,
                      'runtime_manifest_sha256': manifest['runtime_manifest_sha256']}))


if __name__ == '__main__':
    build()

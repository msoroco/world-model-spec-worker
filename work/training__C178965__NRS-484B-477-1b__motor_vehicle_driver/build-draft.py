"""Build two exact paved-alley CPU construction drafts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
CASES = (('controlled_1', 7.5), ('controlled_at_10', 6.648), ('controlled_2', 6.0))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    batch = json.loads((ROOT / 'batch.json').read_text())
    manifest = {'format': 'worker-selected-cpu-draft-manifest-v1',
                'assignment_id': ASSIGNMENT,
                'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
                'status': 'partial', 'cases': []}
    case_ids = [ASSIGNMENT + '__' + suffix for suffix, _ in CASES]
    for suffix, width in CASES:
        case_id = ASSIGNMENT + '__' + suffix
        config = {'case_id': case_id, 'selected_case_id': case_id,
                  'supported_case_ids': case_ids, 'candidate_id': 'primary',
                  'law_id': 'NRS-484B-477-1b', 'cell_id': 'C178965',
                  'actor': 'motor_vehicle_driver', 'alley_case': suffix,
                  'spawn_height_m': 8.8,
                  'rate_hz': 20, 'duration_s': 30, 'required_atoms': [],
                  'source_packets': [], 'case': {'case_id': case_id},
                  'cameras': [{'name': name, 'width': 1920 if name == 'overview' else 1280,
                               'height': 1080 if name == 'overview' else 720,
                               'pose_strategy': 'fixed_world_lateral_and_overhead_capture',
                               'fov_deg': 85}
                              for name in ('overview', 'approach', 'reference_corner', 'driver_reference')],
                  'recording_description': {'channels': [
                      {'name': 'subject_and_other_vehicle_poses', 'unit': 'structured',
                       'sampling_rate_hz': 20, 'method': 'original Native transforms, velocities and extents',
                       'time_window': '600 frames', 'reference_frame': 'authored paved road',
                       'uncertainty': '50 ms sampling',
                       'source': 'channels/subject_and_other_vehicle_poses.jsonl'},
                      {'name': 'alley_lateral_boundaries', 'unit': 'meters',
                       'sampling_rate_hz': 20, 'method': 'OpenDRIVE and original Native lane-width readback',
                       'time_window': '600 frames', 'reference_frame': 'authored paved road',
                       'uncertainty': 'pending Native readback',
                       'source': 'channels/alley_lateral_boundaries.jsonl'}] + [
                      {'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
                       'method': 'source-joined original pose, extent and alley inventory',
                       'time_window': '600 frames', 'reference_frame': 'authored paved road',
                       'uncertainty': '50 ms sampling; legal identity remains independently reviewed',
                       'source': 'channels/' + name + '.jsonl'}
                      for name in ('st.alley', 'drv.standing_or_parked', 'st.lane_width',
                                   'kin.extent', 'rel.surface_gap', 'rel.occupies')],
                      'context_inputs': [
                          {'name': 'independent_alley_review', 'unit': 'structured',
                           'method': 'source-bound alley identity, jurisdiction, ordinance and purpose review',
                           'source': 'alley-context.json'}],
                      'limitations': ['Legal alley definition, local jurisdiction and ordinance, and free movement require independent review']},
                  'status': 'cpu_draft_not_delivery_prepared'}
        config['case']['recording_description'] = config['recording_description']
        candidate_rows = {}
        for candidate_id, spawn_height in (('primary', 8.8), ('fallback1', 9.1)):
            variant = dict(config, candidate_id=candidate_id, spawn_height_m=spawn_height)
            files = [{'path': name, 'content': (HERE / 'native' / name).read_text()}
                     for name in ('runner.py', 'geometry.py', 'legal_context.py', 'tests/test_native.py')]
            files.append({'path': 'alley_measure.py', 'content': (HERE / 'alley_measure.py').read_text()})
            files.append({'path': 'finalize_alley.py', 'content': (HERE / 'finalize_alley.py').read_text()})
            files.append({'path': 'config.json', 'content': json.dumps(variant, indent=2) + '\n'})
            proposal = {'case_id': case_id, 'law_id': variant['law_id'], 'cell_id': variant['cell_id'],
                        'actor': variant['actor'], 'entrypoint': 'runner.py', 'files': files,
                        'recording_description': variant['recording_description'],
                        'measurement_plan': {'entrypoint': 'finalize_alley.py',
                                             'required_sources': ['vehicle-poses.jsonl', 'alley-inventory.json',
                                                                  'video_frames.jsonl', 'trace.jsonl'],
                                             'status': 'source_bound_cpu_draft'},
                        'static_checks': ['open-ended 100 m paved road', f'{width} m alley width',
                                          'two measured vehicle footprints', 'four profile cameras',
                                          '600 frames at 20 Hz', f'{spawn_height} m actor spawn height'],
                        'termination_rules': ['600 original frames', 'restore world and destroy owned actors'],
                        'mechanisms': ['subject parks beside other vehicle',
                                       'controlled width varies between exact cases',
                                       'original positions and extents measured each frame'],
                        'status': 'partial_native_execution_cpu_checked_physical_unverified'}
            path = HERE / 'draft-alley' / suffix / candidate_id / 'construction.json'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(proposal, indent=2) + '\n')
            candidate_rows[candidate_id] = {'construction': str(path.relative_to(HERE)),
                                            'construction_sha256': sha(path)}
        manifest['cases'].append({'case_id': case_id, 'kind': 'delivery',
                                  **candidate_rows['primary'],
                                  'candidate_risk': {'status': 'physical',
                                                     'reason': 'actor spawn may fail or interpenetrate the elevated authored road'},
                                  'candidates': [{'id': 'fallback1', **candidate_rows['fallback1'],
                                                  'trigger': {'source': 'original Native actor spawn and body readback',
                                                              'metric': 'spawn success and pavement intersection',
                                                              'failure_condition': 'primary actor spawn fails or initially intersects paved surface'},
                                                  'changed_knobs': ['both actor spawn heights 8.8 m to 9.1 m']}],
                                  'measurement_procedure': {'entrypoint': 'finalize_alley.py'},
                                  'delivery_readiness': 'incomplete'})
    (HERE / 'draft-alley-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'cases': {c['case_id']: c['construction_sha256'] for c in manifest['cases']},
                      'runtime_manifest_sha256': manifest['runtime_manifest_sha256']}, sort_keys=True))


if __name__ == '__main__':
    main()

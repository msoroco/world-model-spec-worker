"""Build five exact, explicitly synthetic exit construction protocol bundles."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
CAMERAS = ['overview', 'approach', 'reference_corner', 'driver_reference']
MAP_TEXT = '<OpenDRIVE synthetic controlled-access exit protocol fixture/>'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('returned file exceeds 2 MiB')


def build():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    witness = plan['selected_branches'][0]
    plan['requirement_dispositions'] = [{
        'requirement': witness['requirement'], 'source': witness['source'],
        'status': 'selected_required',
        'case_ids': [case['case_id'] for case in plan['cases']],
        'evidence_or_gap': 'Synthetic CPU construction protocol only; reviewed public dedication, access restriction and original exit geometry absent.',
        'reason': 'Exit-only assigned branch; measured proximity and conduct do not define immediate hazard or reasonable safety.'}]
    write(HERE / 'case-plan.json', plan)
    note = HERE / 'diagnostic-source-note.json'
    write(note, {'format': 'c228302-exit-diagnostic-source-v1',
                 'source_kind': 'synthetic_diagnostic_fixture',
                 'accepted_original_source': False, 'physical_acceptance': False,
                 'case_ids': [case['case_id'] for case in plan['cases']]})
    description = {'channels': [
        {'name': 'controlled_access_designation', 'unit': 'source context', 'method': 'original public dedication, access restriction and authority determination', 'sampling_rate_hz': 20, 'time_window': 'all 900 frames', 'reference_frame': 'original map and frame', 'uncertainty': 'synthetic fixture cannot establish legal road status'},
        {'name': 'exit_path', 'unit': 'm and original frame', 'method': 'ego original position and exit interaction polygon', 'sampling_rate_hz': 20, 'time_window': 'all 900 frames', 'reference_frame': 'original map and frame', 'uncertainty': 'synthetic fixture cannot establish realized exit'},
        {'name': 'all_approaching_vehicles', 'unit': 'm and m/s', 'method': 'all highway vehicle identities, occupancy, range and speed', 'sampling_rate_hz': 20, 'time_window': 'all 900 frames', 'reference_frame': 'original map and frame', 'uncertainty': 'synthetic fixture cannot establish immediate hazard'},
        {'name': 'precedence_duration', 'unit': 's', 'method': 'ego wait and entry time joined to approaching vehicles', 'sampling_rate_hz': 20, 'time_window': 'all 900 frames', 'reference_frame': 'original frame', 'uncertainty': 'synthetic fixture cannot establish reasonable safety'},
        {'name': 'camera_frame_identity', 'unit': 'frame ID', 'method': 'four synchronized original camera streams', 'sampling_rate_hz': 20, 'time_window': 'all 900 frames', 'reference_frame': 'original frame', 'uncertainty': 'synthetic fixture is not physical video evidence'}],
                   'context_inputs': [],
                   'limitations': ['No reviewed controlled-access authority or original map exit source.', 'Immediate hazard and reasonable safety are unresolved legal judgments.']}
    entries = []
    for row in plan['cases']:
        cid = row['case_id']; name = cid.removeprefix(AID + '__'); design = row['construction']
        road = {'map_sha256': hashlib.sha256(MAP_TEXT.encode()).hexdigest(),
                'controlled_access_readback': True, 'exit_connection_readback': True,
                'exit_waypoints': [[-10, 0, 0], [-3, 0, 0], [5, 0, 0]],
                'highway_approach_waypoints': [[0, -12, 0], [0, -10, 0], [0, 8, 0]],
                'exit_merge_polygon_xy': [[-2, -2], [6, -2], [6, 3], [-2, 3]]}
        for key in ('public_dedication_source_sha256', 'public_access_source_sha256',
                    'restricted_access_authority_source_sha256', 'restricted_access_determination_source_sha256',
                    'highway_boundary_source_sha256', 'exit_connection_source_sha256', 'route_source_sha256'):
            road[key] = sha(note)
        scene = {'case_id': cid, 'source_kind': 'synthetic_diagnostic_fixture',
                 'accepted_original_source': False, 'cell_id': 'C228302',
                 'layout': 'road', 'maneuver': 'exit_road', 'road': road,
                 'ego_blueprint': 'synthetic_ego_car', 'approach_blueprint': 'synthetic_approach_car',
                 'ego_blueprint_source_sha256': sha(note),
                 'approach_blueprint_source_sha256': sha(note),
                 'driver_control_source_sha256': sha(note)}
        config = {'law_id': 'NRS-484B-263', 'cell_id': 'C228302',
                  'actor': 'motor_vehicle_driver', 'selected_case_id': cid,
                  'rate_hz': 20, 'duration_s': 45, 'required_atoms': [],
                  'source_packets': [], 'cameras': CAMERAS,
                  'case': {'case_id': cid, 'name': name,
                           'policy': design['policy'],
                           'approaching_count': design['approaching_count'],
                           'approach_headway_s': design['approach_headway_s'],
                           'recording_description': description}}
        files = {'runner.py': (HERE / 'diagnostic_runner.py').read_text(),
                 'controlled_access_exit.py': (HERE / 'controlled_access_exit.py').read_text(),
                 'tests/test_bundle.py': (HERE / 'diagnostic_bundle_test.py').read_text(),
                 'config.json': json.dumps(config, indent=2) + '\n',
                 'scene.json': json.dumps(scene, indent=2) + '\n'}
        construction = {'law_id': 'NRS-484B-263', 'cell_id': 'C228302',
                        'actor': 'motor_vehicle_driver', 'case_id': cid,
                        'entrypoint': 'runner.py', 'diagnostic_only': True,
                        'recording_description': description,
                        'files': [{'path': path, 'content': content} for path, content in files.items()]}
        target = HERE / ('construction-diagnostic-' + name + '.json')
        write(target, construction)
        entries.append({'case_id': cid, 'kind': 'capability_research',
                        'construction': target.name, 'construction_sha256': sha(target),
                        'diagnostic_only': True})
    write(HERE / 'execution-manifest.diagnostic.json',
          {'format': 'worker-execution-manifest', 'assignment_id': AID,
           'status': 'synthetic_only_original_authority_and_exit_source_pending',
           'runtime_manifest_sha256': sha(ROOT / 'runtime/SOURCE-MANIFEST.json'),
           'cases': entries})
    return len(entries)


if __name__ == '__main__':
    print('synthetic exit bundles:', build())

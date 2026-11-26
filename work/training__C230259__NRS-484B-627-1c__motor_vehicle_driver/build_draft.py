"""Materialize exact source-hashed Native route constructions for CPU checks."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
VARIANTS = (
    ('witness_1', True, True),
    ('witness_2', True, False),
    ('exception_1_1', True, False),
    ('exception_1_2', False, False),
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def main():
    batch = json.loads((ROOT / 'batch.json').read_text())
    ids = [ASSIGNMENT + '__' + suffix for suffix, _, _ in VARIANTS]
    entries = []
    for suffix, possible, taken in VARIANTS:
        case_id = ASSIGNMENT + '__' + suffix
        description = {'channels': [
            {'name': 'participant_motion', 'unit': 'structured', 'sampling_rate_hz': 20,
             'method': 'original same-tick Native participant positions, road IDs and velocities',
             'time_window': '900 frames', 'reference_frame': 'authored route graph',
             'uncertainty': '50 ms frame interval; intended speed differs from observed speed'},
            {'name': 'route_occupancy', 'unit': 'structured', 'sampling_rate_hz': 20,
             'method': 'original map waypoint road IDs joined to participant and camera frames',
             'time_window': '900 frames', 'reference_frame': 'original OpenDRIVE road IDs',
             'uncertainty': 'waypoint projection and route availability require local review'}],
            'context_inputs': [],
            'limitations': ['Authored connectivity is not legal or practical route availability',
                            'Controlled-access designation and actual impediment require independent review',
                            'Physical route completion and pixels remain unverified']}
        cameras = [{'name': name, 'width': width, 'height': height, 'fov_deg': 85,
                    'pose_strategy': 'fixed vantage at original route choice'}
                   for name, width, height, *_ in (
                       ('overview', 1920, 1080, 0), ('approach', 1280, 720, 0),
                       ('reference_corner', 1280, 720, 0), ('driver_reference', 1280, 720, 0))]
        base = {'case_id': case_id, 'selected_case_id': case_id,
                'supported_case_ids': ids, 'candidate_id': 'primary',
                'law_id': 'NRS-484B-627-1c', 'cell_id': 'C230259',
                'actor': 'motor_vehicle_driver', 'alternate_possible': possible,
                'take_alternate': taken, 'lookahead_points': 4,
                'rate_hz': 20, 'duration_s': 45, 'required_atoms': [],
                'source_packets': [], 'case': {'case_id': case_id},
                'cameras': cameras, 'recording_description': description,
                'status': 'partial_cpu_draft'}
        paths = ('runner.py', 'geometry.py', 'route_measure.py',
                 'finalize.py', 'tests/test_native.py')
        files = [{'path': name, 'content': (HERE / name).read_text()} for name in paths]
        files.append({'path': 'config.json', 'content': json.dumps(base, indent=2) + '\n'})
        construction = {'case_id': case_id, 'law_id': base['law_id'],
            'cell_id': base['cell_id'], 'actor': base['actor'],
            'entrypoint': 'runner.py', 'files': files,
            'recording_description': description,
            'measurement_plan': {'entrypoint': 'finalize.py',
                'required_sources': ['route-trace.jsonl', 'route-context.json',
                    'road.xodr', 'video_frames.jsonl'],
                'source_review_required': True},
            'static_checks': ['same-destination main and alternate road topology',
                'two immediately following vehicles', 'four cameras and 900 original frames'],
            'termination_rules': ['900 original frames',
                'destroy owned actors and restore original world'],
            'mechanisms': ['6 m/s requested subject speed and same follower controller policy',
                'alternate road physically present' if possible else 'alternate road omitted',
                'alternate turn requested' if taken else 'mainline travel requested',
                'no legal status or physical completion inferred from targets'],
            'status': 'partial_native_execution_cpu_checked_physical_unverified'}
        primary = HERE / 'draft-route' / suffix / 'primary' / 'construction.json'
        write(primary, construction)
        fallback = json.loads(json.dumps(construction))
        fallback_config = dict(base, candidate_id='fallback1', lookahead_points=3)
        next(f for f in fallback['files'] if f['path'] == 'config.json')['content'] = \
            json.dumps(fallback_config, indent=2) + '\n'
        fallback['mechanisms'].append('fallback shortens pure-pursuit lookahead from 4 to 3 route points')
        secondary = HERE / 'draft-route' / suffix / 'fallback1' / 'construction.json'
        write(secondary, fallback)
        contract = {'format': 'worker-measurement-contract', 'case_id': case_id,
            'requirements': [{'disposition_index': 0 if suffix.startswith('witness') else 1,
                'requirement': 'NRS-484B-627-1c', 'source': 'NRS 484B.627(1)(c)',
                'output_key': 'route_observation', 'method': 'route_observation',
                'value_type': 'object', 'kind': 'measured',
                'inputs': ['route-trace.jsonl', 'route-context.json',
                           'road.xodr', 'video_frames.jsonl']}],
            'negative': {'remove': ['route-context.json'],
                'error_contains': 'Missing required source: route-context.json'}}
        contract_path = HERE / ('measurement-' + suffix + '.json')
        write(contract_path, contract)
        entries.append({'case_id': case_id, 'kind': 'delivery',
            'construction': str(primary.relative_to(HERE)),
            'construction_sha256': sha(primary),
            'measurement_contract': contract_path.name,
            'measurement_procedure': {'entrypoint': 'finalize.py',
                'output_schema': 'c230259-route-analysis-v1'},
            'fixture_recipe': str((HERE / ('selected-recipe-' + suffix + '.json')).relative_to(ROOT)),
            'candidate_risk': {'status': 'physical',
                'reason': 'Native junction turn and four-camera route visibility need observed confirmation'},
            'candidates': [{'id': 'fallback1',
                'construction': str(secondary.relative_to(HERE)),
                'construction_sha256': sha(secondary),
                'trigger': {'source': 'original route-trace.jsonl and mapped lane centrelines',
                    'metric': 'first-150-frame lateral route deviation',
                    'failure_condition': 'subject departs its selected driving lane before the route choice'},
                'changed_knobs': ['pure-pursuit lookahead 4 to 3 in every linked case']}],
            'delivery_readiness': 'incomplete'})
    manifest = {'format': 'worker-selected-cpu-draft-manifest-v1',
        'assignment_id': ASSIGNMENT,
        'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
        'status': 'partial', 'cases': entries}
    write(HERE / 'draft-route-manifest.json', manifest)
    print(json.dumps({'cases': [entry['case_id'] for entry in entries],
                      'runtime_manifest_sha256': manifest['runtime_manifest_sha256']}))


if __name__ == '__main__':
    main()

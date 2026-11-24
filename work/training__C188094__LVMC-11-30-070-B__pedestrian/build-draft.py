"""Bind exact current-v2 primary pedestrian-crossing construction drafts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
CASES = (('probe_1', 'crosswalk'), ('probe_2', 'outside'))
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    batch = json.loads((ROOT / 'batch.json').read_text())
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': ASSIGNMENT,
                'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
                'status': 'partial_native_draft', 'cases': []}
    for suffix, crossing_case in CASES:
        case_id = ASSIGNMENT + '__' + suffix
        description = {'channels': [
            {'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
             'method': method, 'time_window': '600 original frames',
             'reference_frame': 'surveyed at-grade road and original Native frame',
             'uncertainty': '50 ms sampling; business district and complete crosswalk inventory unverified'}
            for name, method in (
                ('ru.subject', 'original Native pedestrian blueprint and actor identity'),
                ('st.crosswalk', 'authored marked crosswalk and Native source survey'),
                ('st.roadway', 'authored paved road and Native waypoint readback'),
                ('rel.occupies', 'original Native pedestrian position and surveyed roadway'),
                ('st.intersection', 'crosswalk inventory and source geometry review'),
                ('kin.position', 'original Native pedestrian transform'))],
            'context_inputs': [],
            'limitations': ['Business-district authority and unmarked crossings need independent original source review']}
        config = {'case_id': case_id, 'selected_case_id': case_id,
                  'supported_case_ids': [ASSIGNMENT + '__' + s for s, _ in CASES],
                  'candidate_id': 'primary', 'law_id': 'LVMC-11-30-070-B',
                  'cell_id': 'C188094', 'actor': 'pedestrian',
                  'crossing_case': crossing_case, 'rate_hz': 20, 'duration_s': 30,
                  'required_atoms': [], 'source_packets': [], 'case': {'case_id': case_id},
                  'cameras': [{'name': name, 'width': 1920 if name == 'overview' else 1280,
                               'height': 1080 if name == 'overview' else 720} for name in CAMERAS],
                  'recording_description': description, 'status': 'cpu_draft_district_unverified'}
        files = [{'path': name, 'content': (HERE / 'native' / name).read_text()}
                 for name in ('runner.py', 'geometry.py', 'path.py',
                              'measure_crossing.py', 'finalize.py', 'tests/test_native.py')]
        files.append({'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'})
        proposal = {'case_id': case_id, 'law_id': config['law_id'],
                    'cell_id': config['cell_id'], 'actor': config['actor'],
                    'entrypoint': 'runner.py', 'files': files,
                    'recording_description': description,
                    'measurement_plan': {'entrypoint': 'measure_crossing.py',
                        'required_sources': ['road.xodr', 'crossing-survey.json',
                                             'actor-poses.jsonl', 'video_frames.jsonl']},
                    'static_checks': ['paved road, marked crosswalk and raised overpass',
                                      'Native at-grade road readback', '600 frames at 20 Hz',
                                      'four retained RGB source cameras'],
                    'termination_rules': ['600 frames', 'destroy owned actors and restore world'],
                    'mechanisms': ['same pedestrian path policy; crossing x position varies'],
                    'status': 'partial_native_draft_district_unverified'}
        path = HERE / 'draft-exact' / suffix / 'primary' / 'construction.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(proposal, indent=2) + '\n')
        manifest['cases'].append({'case_id': case_id, 'kind': 'delivery',
            'construction': str(path.relative_to(HERE)), 'construction_sha256': sha(path),
            'candidate_risk': {'status': 'physical',
                'reason': 'Native walking and business-district coverage require original review'},
            'candidates': [], 'measurement_procedure': {'entrypoint': 'finalize.py'},
            'preparation_status': 'incomplete'})
    (HERE / 'draft-execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({c['case_id']: c['construction_sha256'] for c in manifest['cases']}))


if __name__ == '__main__':
    main()

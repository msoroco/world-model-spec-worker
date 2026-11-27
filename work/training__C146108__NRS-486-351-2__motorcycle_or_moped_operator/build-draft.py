"""Build the same-lane motorcycle passing draft from this assignment's authored Native sources."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name + '__controlled_2'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    batch = json.loads((ROOT / 'batch.json').read_text())
    cameras = [{'name': name, 'width': width, 'height': height,
                'pose_strategy': 'static surveyed one-way same-lane pass view',
                'fov_deg': 85} for name, width, height in
               [('overview', 1920, 1080), ('approach', 1280, 720),
                ('reference_corner', 1280, 720), ('driver_reference', 1280, 720)]]
    channels = ('ru.motorcycle', 'ru.moped', 'st.lane', 'rel.occupies',
                'rel.longitudinal_overlap', 'drv.overtaking', 'rel.bearing',
                'ru.motor_vehicle', 'rel.surface_gap', 'kin.position',
                'kin.heading', 'kin.speed')
    description = {'channels': [
        {'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
         'method': 'original Native actor transform and full body corners',
         'time_window': 'all 600 frames across 30 seconds',
         'reference_frame': 'one-way OpenDRIVE road and Native frame',
         'uncertainty': '50 ms sampling'} for name in channels],
        'context_inputs': [{'name': 'motorcycle_class', 'unit': 'category',
                            'method': 'original blueprint ID plus independent Chapter 486 review'},
                           {'name': 'subsection_3_exception', 'unit': 'source text',
                            'method': 'independent statutory source review required'}],
        'limitations': ['CPU construction does not establish actual Native motion or pixels',
                        'Driver consent cannot be inferred from the actor arrangement',
                        'Operative subsection 3 text is absent from the frozen law field']}
    config = {'case_id': CASE, 'selected_case_id': CASE,
              'supported_case_ids': [ROOT.name + '__controlled_1', CASE],
              'case_suffix': 'controlled_2', 'candidate_id': 'primary',
              'cell_id': 'C146108', 'law_id': 'NRS-486-351-2',
              'actor': 'motorcycle_or_moped_operator', 'rider_class': 'motorcycle',
              'rate_hz': 20, 'duration_s': 30, 'required_atoms': [],
              'source_packets': [],
              'case': {'case_id': CASE}, 'cameras': cameras,
              'physical_target': {'behavior': 'complete same-lane behind-to-ahead pass'},
              'recording_description': description,
              'status': 'selected_cpu_draft_not_delivery_prepared'}
    files = [{'path': name, 'content': (HERE / 'native' / name).read_text()} for name in
             ('runner.py', 'geometry.py', 'measure_pass.py', 'measure_follow.py',
              'law_review.py', 'finalize.py', 'tests/test_native.py')]
    files.append({'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'})
    proposal = {'case_id': CASE, 'law_id': 'NRS-486-351-2', 'cell_id': 'C146108',
                'actor': 'motorcycle_or_moped_operator', 'entrypoint': 'runner.py',
                'files': files, 'recording_description': description,
                'measurement_plan': {'entrypoint': 'finalize.py',
                    'required_sources': ['participant-poses.jsonl', 'video_frames.jsonl',
                        'pass-context.json', 'pass-review.json', 'trace.jsonl',
                        'capture/manifest.json', 'road.xodr',
                        'overview.mkv', 'approach.mkv', 'reference_corner.mkv',
                        'driver_reference.mkv'],
                    'status': 'source_bound_cpu_draft'},
                'static_checks': ['two 6 m one-way through lanes',
                    'motorcycle and car bodies planned in same lane',
                    'four original synchronized camera streams',
                    '600 frames at 20 Hz'],
                'termination_rules': ['600 original frames', 'restore exclusive Native world'],
                'mechanisms': ['motorcycle target velocity 5 m/s versus car 3 m/s',
                    'both bodies remain in same lane under review',
                    'behind-to-clear-ahead pass measured from retained original bodies'],
                'status': 'selected_cpu_draft_physical_and_saved_delivery_unverified'}
    path = HERE / 'draft-same-lane/controlled_2/primary/construction.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(proposal, indent=2) + '\n')
    manifest = {'format': 'worker-selected-cpu-draft-manifest-v1',
                'assignment_id': HERE.name,
                'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
                'status': 'partial', 'cases': [{'case_id': CASE, 'kind': 'delivery',
                    'construction': str(path.relative_to(HERE)),
                    'construction_sha256': sha(path),
                    'candidate_risk': {'status': 'physical',
                        'reason': 'Original motorcycle path, body clearance and visibility may fail'},
                    'candidates': [], 'measurement_procedure': {'entrypoint': 'measure_pass.py'},
                    'delivery_readiness': 'incomplete'}]}
    (HERE / 'draft-same-lane-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'case_id': CASE, 'construction_sha256': sha(path)}))


if __name__ == '__main__':
    build()

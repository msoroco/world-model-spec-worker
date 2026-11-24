"""Build source-bound bus-terminus CPU Native draft for pinned offline proof."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name + '__probe_02'

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    batch = json.loads((ROOT / 'batch.json').read_text())
    config = {'case_id': CASE, 'selected_case_id': CASE, 'supported_case_ids': [CASE], 'candidate_id': 'primary', 'law_id': 'LVMC-11-60-030-A5', 'cell_id': 'C393261', 'actor': 'bus_driver', 'rate_hz': 20, 'duration_s': 30, 'required_atoms': [], 'source_packets': [], 'case': {'case_id': CASE}, 'cameras': [{'name': name, 'width': 1280, 'height': 720} for name in ('terminus_overview', 'terminus_marker', 'parking_zone', 'bus_chase')], 'recording_description': {'channels': [{'name': 'original_bus_position_velocity', 'unit': 'structured', 'sampling_rate_hz': 20, 'method': 'Native post-tick bus transform and velocity', 'time_window': '600 frames', 'reference_frame': 'residential endpoint road 1', 'uncertainty': '50 ms sampling'}, {'name': 'endpoint_survey', 'unit': 'structured', 'sampling_rate_hz': 20, 'method': 'Native map lane and signal readback', 'time_window': '600 frames', 'reference_frame': 'road 1 parking lane -2', 'uncertainty': 'physical sign pixels unverified'}], 'limitations': ['Official designated period and establishment authority absent', 'Sign need not display designated duration', 'Actual passenger loading and bus operation classification require review']}, 'status': 'partial_cpu_draft'}
    files = [{'path': name, 'content': (HERE / 'native' / name).read_text()} for name in ('runner.py', 'geometry.py', 'measure.py', 'tests/test_native.py')]
    files.append({'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'})
    proposal = {'case_id': CASE, 'law_id': config['law_id'], 'cell_id': config['cell_id'], 'actor': config['actor'], 'entrypoint': 'runner.py', 'files': files, 'recording_description': config['recording_description'], 'measurement_plan': {'entrypoint': 'measure.py', 'required_sources': ['terminus-history.jsonl', 'terminus-context.json'], 'status': 'source_bound_cpu_draft'}, 'static_checks': ['200m residential road and parking lane -2', 'non-tour bus blueprint with terminus marker', 'four cameras and 600 original frames'], 'termination_rules': ['600 original frames', 'restore world and destroy owned actors'], 'mechanisms': ['park bus inside surveyed endpoint', 'compare measured stationary occupancy durations only to source-verified designated period'], 'status': 'partial_native_execution_cpu_checked_physical_unverified'}
    path = HERE / 'draft-terminus' / 'long_dwell' / 'primary' / 'construction.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(proposal, indent=2) + '\n')
    manifest = {'format': 'worker-selected-cpu-draft-manifest-v1', 'assignment_id': HERE.name, 'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'], 'status': 'partial', 'cases': [{'case_id': CASE, 'kind': 'delivery', 'construction': str(path.relative_to(HERE)), 'construction_sha256': sha(path), 'candidate_risk': {'status': 'physical', 'reason': 'Native bus motion, sign pixels, and official designation require inspection'}, 'candidates': [], 'measurement_procedure': {'entrypoint': 'measure.py'}, 'delivery_readiness': 'incomplete'}]}
    (HERE / 'draft-terminus-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'case_id': CASE, 'construction_sha256': sha(path), 'runtime_manifest_sha256': manifest['runtime_manifest_sha256']}))

if __name__ == '__main__':
    main()

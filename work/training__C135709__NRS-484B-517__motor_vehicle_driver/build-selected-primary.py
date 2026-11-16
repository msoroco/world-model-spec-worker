"""Materialize the first exact selected C135709 primary for pinned offline proof."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
NATIVE = ROOT/'native'
CASE = ROOT.name + '__reference'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def build():
    source = ROOT/'offline/bundles/reference/primary'
    cfg = json.loads((source/'config.json').read_text())
    cases = json.loads((ROOT/'proposals/cases.json').read_text())
    selected = next(c for c in cases['cases'] if c['case_id'] == CASE)
    cfg.update(selected_case_id=CASE, duration_s=12, required_atoms=[],
        source_packets=[], case=selected,
        supported_case_ids=[CASE], physical_success_claimed=False,
        cameras=[{'name': name, 'width': width, 'height': height,
            'pose_strategy': pose, 'fov_deg': fov}
            for name, width, height, pose, fov in (
                ('overview', 1920, 1080, 'fixed_stand_overview', 85),
                ('approach', 1280, 720, 'fixed_incoming_road', 75),
                ('reference_corner', 1280, 720, 'fixed_stand_and_sign', 75),
                ('driver_reference', 1280, 720, 'ego_attached', 90))])
    inventory = {
        'runner.py': ROOT/'runner.py',
        'capture.py': NATIVE/'capture.py',
        'check.py': NATIVE/'check.py',
        'fixture_raw.py': NATIVE/'fixture_raw.py',
        'prepare_raw.py': NATIVE/'prepare_raw.py',
        'measure_prepared.py': NATIVE/'measure_prepared.py',
        'finalize_selected.py': NATIVE/'finalize_selected.py',
        'measure_saved.py': NATIVE/'measure_saved.py',
        'triggers.py': NATIVE/'triggers.py',
        'stand-road.xodr': NATIVE/'stand-road.xodr',
        'requested-tracks.jsonl': source/'requested-tracks.jsonl',
        'assignment-source.json': REPO/'inputs'/ROOT.name/'assignment.json',
        'case-plan.json': ROOT/'case-plan.json',
        'measurement-contract.json': NATIVE/'measurement-contract.json',
        'tests/test_reference_primary.py': ROOT/'selected-tests/test_reference_primary.py'}
    for name in ('native-observed.jsonl', 'camera-frames.jsonl',
                 'stand-review.jsonl', 'stand-readback.json'):
        inventory['saved/'+name] = NATIVE/'saved-fixtures/reference/primary'/name
    files = [{'path': path, 'content': target.read_text()}
             for path, target in inventory.items()]
    files.append({'path': 'config.json', 'content': json.dumps(cfg, indent=2)+'\n'})
    construction = {'case_id': CASE, 'law_id': 'NRS-484B-517', 'cell_id': 'C135709',
        'actor': 'motor_vehicle_driver', 'entrypoint': 'runner.py', 'files': files,
        'status': 'draft_selected_cpu', 'original_native_observed': False,
        'delivery_ready': False,
        'recording_description': selected['recording_description'],
        'measurement_plan': {'source': 'Native actor, map, sign review and four camera streams',
            'finalizer': 'measure_prepared.py', 'legal_verdict': None},
        'static_checks': ['exact frozen source', '240 request frames',
                          'four source cameras', 'synthetic raw-to-saved'],
        'termination_rules': {'requested_frames': 240, 'stop_on_error': True},
        'mechanisms': {'construction_status': 'authored_cpu_unverified_physical',
            'road': 'stand-road.xodr', 'controller': 'capture.py'}}
    path = ROOT/'selected-primary/reference/construction.json'
    write(path, construction)
    batch = json.loads((REPO/'batch.json').read_text())
    runtime = REPO/batch['runtime']['root']/'SOURCE-MANIFEST.json'
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': ROOT.name,
        'status': 'first_primary_offline_in_progress',
        'runtime_manifest_sha256': sha(runtime),
        'source_branch': 'non_taxicab_parking_in_taxicab_stand',
        'cases': [{'case_id': CASE, 'kind': 'delivery',
            'construction': 'construction.json',
            'construction_sha256': sha(path),
            'candidate_risk': {'status': 'physical',
                'reason': 'Generated stand geometry, actual parking and all four camera views unverified'},
            'candidates': []}],
        'original_native_observed': False, 'delivery_ready': False}
    manifest_path = ROOT/'selected-primary/reference/draft-manifest.json'
    write(manifest_path, manifest)
    return {'construction_sha256': sha(path), 'construction_bytes': path.stat().st_size,
            'manifest': manifest_path.relative_to(ROOT).as_posix()}


if __name__ == '__main__':
    print(json.dumps(build()))

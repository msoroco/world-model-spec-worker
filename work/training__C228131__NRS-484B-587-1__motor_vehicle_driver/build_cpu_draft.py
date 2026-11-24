"""Bind exact source-hashed CPU request constructions for pinned offline checks."""
import hashlib
import json
from pathlib import Path

CASE = Path(__file__).resolve().parent
ROOT = CASE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    input_path = ROOT / 'inputs' / CASE.name / 'assignment.json'
    plan_path = CASE / 'case-plan.json'
    entries = []
    for suffix, gate_x in (('witness_1', 0), ('witness_2', 60)):
        case_id = CASE.name + '__' + suffix
        config = {'assignment_id': CASE.name, 'case_id': case_id,
                  'selected_case_id': case_id, 'supported_case_ids': [case_id],
                  'candidate_id': 'primary', 'law_id': 'NRS-484B-587-1',
                  'cell_id': 'C228131', 'actor': 'motor_vehicle_driver',
                  'input_sha256': sha(input_path), 'case_plan_sha256': sha(plan_path),
                  'source_kind': 'authored_native_request',
                  'requested_entry_x_m': gate_x, 'rate_hz': 20, 'duration_s': 30,
                  'camera_names': ['overview', 'approach', 'indicated_gate', 'highway_side'],
                  'required_atoms': [], 'source_packets': [],
                  'case': {'case_id': case_id}, 'status': 'unselected_cpu_diagnostic'}
        files = [{'path': name, 'content': (CASE / source).read_text()}
                 for name, source in (('cpu_runner.py', 'cpu_runner.py'),
                                      ('entry_cpu.py', 'entry_cpu.py'),
                                      ('saved_entry.py', 'saved_entry.py'),
                                      ('tests/test_request.py', 'cpu_tests/test_request.py'))]
        files.append({'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'})
        construction = {'case_id': case_id, 'law_id': 'NRS-484B-587-1',
                        'cell_id': 'C228131', 'actor': 'motor_vehicle_driver',
                        'entrypoint': 'cpu_runner.py', 'files': files,
                        'recording_description': {'duration_s': 30,
                            'cameras': config['camera_names'],
                            'limitations': ['CPU authored request only; Native execution pending']},
                        'status': 'partial_cpu_diagnostic'}
        destination = CASE / 'draft-entry' / suffix / 'primary' / 'construction.json'
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(construction, indent=2) + '\n')
        entries.append({'case_id': case_id, 'kind': 'delivery',
                        'construction': str(destination.relative_to(CASE)),
                        'construction_sha256': sha(destination),
                        'candidate_risk': {'status': 'physical',
                                           'reason': 'Entry road connectivity and vehicle trajectory require Native review'},
                        'candidates': [], 'delivery_readiness': 'incomplete'})
    manifest = {'format': 'worker-selected-cpu-draft-manifest-v1',
                'assignment_id': CASE.name, 'input_sha256': sha(input_path),
                'case_plan_sha256': sha(plan_path), 'status': 'partial',
                'cases': entries}
    destination = CASE / 'draft-entry-manifest.json'
    destination.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'manifest_sha256': sha(destination), 'cases': len(entries)}))


if __name__ == '__main__':
    main()

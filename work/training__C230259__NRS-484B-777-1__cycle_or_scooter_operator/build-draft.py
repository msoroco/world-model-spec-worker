"""Package exact C230259 reference/contrast Native CPU drafts for pinned offline."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASES = (HERE.name + '__reference', HERE.name + '__contrast')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    batch = json.loads((ROOT / 'batch.json').read_text())
    entries = []
    for case_id, y in zip(CASES, (-2.65, -1.45)):
        config = {'case_id': case_id, 'selected_case_id': case_id,
                  'supported_case_ids': list(CASES), 'candidate_id': 'primary',
                  'law_id': 'NRS-484B-777-1', 'cell_id': 'C230259',
                  'actor': 'cycle_or_scooter_operator', 'rider_class': 'bicycle',
                  'rate_hz': 20, 'duration_s': 30, 'required_atoms': [],
                  'source_packets': [], 'cameras': ['overview', 'approach', 'side', 'rear'],
                  'requested_cycle_center_y_m': y,
                  'recording_description': {'channels': [
                      {'name': 'cycle_lateral_distance_from_right_edge', 'unit': 'm',
                       'method': 'Native bicycle body footprint minus surveyed roadway edge',
                       'sampling_rate_hz': 20, 'time_window': '600 original frames'},
                      {'name': 'standing_vehicle_clearance', 'unit': 'm',
                       'method': 'Native actor footprints during longitudinal overlap',
                       'sampling_rate_hz': 20, 'time_window': 'passing interval'}],
                      'limitations': ['No legal threshold for practicability or due care',
                                      'Native execution and physical behavior unverified']},
                  'status': 'partial_cpu_draft'}
        files = [{'path': name, 'content': (HERE / 'native' / name).read_text()}
                 for name in ('runner.py', 'capture.py', 'geometry.py', 'measure_right_edge.py',
                              'measurement-contract.json', 'prove_right_edge.py',
                              'tests/test_saved.py')]
        files.append({'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'})
        proposal = {'case_id': case_id, 'law_id': config['law_id'],
                    'cell_id': config['cell_id'], 'actor': config['actor'],
                    'entrypoint': 'runner.py', 'files': files,
                    'recording_description': config['recording_description'],
                    'measurement_plan': {'entrypoint': 'runner.py --process-saved',
                                         'required_sources': json.loads((HERE / 'native' / 'measurement-contract.json').read_text())['input_sources'],
                                         'source_hash_inventory_required': True,
                                         'status': 'source_bound_cpu_draft'},
                    'mechanisms': ['authored 160 m driving lane with right shoulder',
                                   'original Native bicycle and standing vehicle actor footprints',
                                   'four original camera frame hashes with 20 Hz Native frame map',
                                   'readback-gated roadway edge and lane widths'],
                    'termination_rules': ['600 original 20 Hz frames',
                                          'restore world and destroy owned actors',
                                          'fail closed on map, camera or source mismatch'],
                    'status': 'partial_native_construction_cpu_checked_physical_unverified'}
        path = HERE / 'draft-right-edge' / case_id.rsplit('__', 1)[-1] / 'primary/construction.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(proposal, indent=2) + '\n')
        entries.append({'case_id': case_id, 'kind': 'delivery',
                        'construction': str(path.relative_to(HERE)),
                        'construction_sha256': sha(path),
                        'candidate_risk': {'status': 'physical',
                                           'reason': 'Bicycle dynamics, roadside clearance and camera realization need Native review'},
                        'candidates': [],
                        'measurement_procedure': {'entrypoint': 'runner.py --process-saved'},
                        'delivery_readiness': 'incomplete'})
    manifest = {'format': 'worker-selected-cpu-draft-manifest-v1',
                'assignment_id': HERE.name,
                'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
                'status': 'partial', 'cases': entries}
    out = HERE / 'draft-right-edge-manifest.json'
    out.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'cases': {e['case_id']: e['construction_sha256'] for e in entries},
                      'manifest_sha256': sha(out)}))


if __name__ == '__main__':
    main()

"""Independent exact-case diagnostic acceptance rehearsal for sidewalk riding."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REQUIRED = {'actual_analysis', 'native_validation', 'mandatory_observations',
            'lean_decoder', 'render', 'final_decode', 'four_camera_sources',
            'selected_measurements', 'negative_case_source'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def check(case_id, diagnostic):
    manifest = read(HERE / 'selected-30s-draft-execution-manifest.json')
    entries = [e for e in manifest['cases'] if e['case_id'] == case_id]
    if len(entries) != 1:
        raise ValueError('Select one exact sidewalk case')
    if not diagnostic:
        raise ValueError('Original Native source required for delivery acceptance')
    entry = entries[0]
    witness = case_id.rsplit('__', 1)[-1]
    construction_path = HERE / entry['construction']
    if sha(construction_path) != entry['construction_sha256']:
        raise ValueError('Selected construction changed')
    construction = read(construction_path)
    files = {item['path']: item['content'] for item in construction['files']}
    tracks = [json.loads(row) for row in files['requested-tracks.jsonl'].splitlines()]
    if len(tracks) != 600 or any(row['frame'] != i or row['time_s'] != round(i / 20, 4)
                                  for i, row in enumerate(tracks)):
        raise ValueError('Motorcycle frame/time source incomplete')
    proof_path = HERE / 'selected-30s/physical-proof' / witness / 'proof.json'
    physical = read(proof_path)
    if (physical['construction_sha256'] != entry['construction_sha256'] or
            physical['original_native_observed'] is not False or
            {item['kind'] for item in physical['fixtures']} !=
            {'complete_motion', 'incomplete_motion', 'missing_evidence'}):
        raise ValueError('Three-outcome physical diagnostic missing')
    receipt_path = HERE / 'selected-30s/proof' / witness / 'primary/compatibility.json'
    receipt = read(receipt_path)
    if (not receipt['passed'] or receipt['case_id'] != case_id or
            receipt['construction_sha256'] != entry['construction_sha256'] or
            receipt['runtime_manifest_sha256'] != manifest['runtime_manifest_sha256'] or
            not REQUIRED <= set(receipt['checks'])):
        raise ValueError('Exact selected compatibility proof missing')
    measured = receipt['measurement_examples']['motorcycle_sidewalk_occupancy']['value']
    expected_overlap = 0 if witness == 'witness_1' else 520
    if (measured['frames'] != 600 or measured['moving_sidewalk_overlap_frames'] != expected_overlap or
            measured['spatial_context']['city_authority_reviewed'] is not False or
            measured['spatial_context']['driveway_rule_composition_reviewed'] is not False):
        raise ValueError('Diagnostic sidewalk measurement differs')
    return {'case_id': case_id, 'diagnostic_only': True,
            'physical_acceptance': False, 'legal_verdict': None,
            'source_kind': 'synthetic_fixture', 'joined_frames': 600,
            'moving_sidewalk_overlap_frames': expected_overlap,
            'construction_sha256': sha(construction_path),
            'compatibility_sha256': sha(receipt_path),
            'physical_proof_sha256': sha(proof_path),
            'requested_tracks_sha256': hashlib.sha256(files['requested-tracks.jsonl'].encode()).hexdigest()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    print(json.dumps(check(args.case, args.diagnostic), sort_keys=True))

"""Independent CPU rehearsal for the selected NRS 484B.267(2)(f) cases."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'native'))
from measure_approach import measure
from measure_official import measure as measure_official
from measure_stopped import measure as measure_stopped


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(case_id, diagnostic):
    manifest = json.loads((HERE / 'current-execution-manifest.json').read_text())
    entries = [entry for entry in manifest['cases'] if entry['case_id'] == case_id]
    if len(entries) != 1:
        raise ValueError('Select one exact selected case')
    if not diagnostic:
        raise ValueError('Original Native source required for delivery acceptance')
    entry = entries[0]
    suffix = case_id.rsplit('__', 1)[-1]
    fixture = HERE / 'current-fixture' / suffix
    provenance = json.loads((fixture / 'acquisition-provenance.json').read_text())
    if provenance.get('provenance_kind') != 'synthetic_local_diagnostic' or not provenance.get('diagnostic_fixture'):
        raise ValueError('Diagnostic source provenance differs')
    measurement = ({'official_approach': measure_official,
                    'stopped_referral': measure_stopped}.get(suffix, measure))(fixture)
    if measurement['assignment_id'] != HERE.name or measurement['samples'] != 600:
        raise ValueError('Source-bound 600-frame measurement missing')
    compatibility_path = HERE / 'current-public' / (suffix + '-primary-compatibility.json')
    processing_path = HERE / 'current-public' / (suffix + '-primary-processing.json')
    compatibility = json.loads(compatibility_path.read_text())
    processing = json.loads(processing_path.read_text())
    required = {'actual_analysis', 'native_validation', 'mandatory_observations',
                'lean_decoder', 'render', 'final_decode', 'four_camera_sources',
                'selected_measurements', 'negative_case_source'}
    if (compatibility.get('case_id') != case_id or compatibility.get('candidate_id') != 'primary'
            or compatibility.get('construction_sha256') != entry['construction_sha256']
            or compatibility.get('runtime_manifest_sha256') != manifest['runtime_manifest_sha256']
            or compatibility.get('passed') is not True
            or not required <= set(compatibility.get('checks', []))):
        raise ValueError('Current-runtime exact-case compatibility missing')
    if (processing.get('case_id') != case_id or processing.get('passed') is not True
            or processing.get('recorded_only') is not True
            or processing.get('originals_preserved') is not True
            or processing.get('analysis_revision', {}).get('construction_sha256') != entry['construction_sha256']):
        raise ValueError('Recorded-only source-preserving processing missing')
    proof_path = HERE / 'physical-proof' / suffix / 'proof.json'
    proof = json.loads(proof_path.read_text())
    if proof.get('case_id') != case_id or proof.get('construction_sha256') != entry['construction_sha256']:
        raise ValueError('Exact-case physical diagnostic changed')
    if proof.get('original_native_observed') is not False:
        raise ValueError('Synthetic diagnostic mislabeled as original')
    return {'case_id': case_id, 'diagnostic_only': True,
            'physical_acceptance': False, 'legal_verdict': None,
            'joined_frames': measurement['samples'],
            'right_edge_stop_until_passed_observed': measurement['right_edge_stop_until_passed_observed'],
            'emergency_pass_frame': measurement['emergency_pass_frame'],
            'compatibility_sha256': sha(compatibility_path),
            'saved_processing_sha256': sha(processing_path),
            'physical_proof_sha256': sha(proof_path),
            'original_source_sha256': measurement['source_sha256']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    print(json.dumps(check(args.case, args.diagnostic), sort_keys=True))

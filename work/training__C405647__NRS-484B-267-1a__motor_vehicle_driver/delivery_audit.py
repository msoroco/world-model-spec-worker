"""Independent exact-case CPU delivery rehearsal for the six source branches."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(case_id, diagnostic):
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entries = [e for e in manifest['cases'] if e['case_id'] == case_id]
    if len(entries) != 1:
        raise ValueError('Select one exact case')
    entry = entries[0]
    suffix = case_id.rsplit('__', 1)[-1]
    if not diagnostic:
        raise ValueError('Original Native source required for delivery acceptance')
    recipe = json.loads((HERE / f'current-{suffix}-recipe.json').read_text())
    sources = {x['path']: HERE.parents[1] / x['source'] for x in recipe['sources']}
    source = sources['actor-frames.jsonl']
    context = sources['context-scope.json']
    scope = json.loads(context.read_text())
    rows = [json.loads(line) for line in source.read_text().splitlines()]
    if (scope.get('source_kind') != 'synthetic_cpu' or len(rows) != 480 or
            any(r.get('frame') != i or not isinstance(r.get('native_frame'), int) or
                abs(r.get('time_s', -1) - i / 20) > 1e-4 for i, r in enumerate(rows))):
        raise ValueError('Synthetic Native-style body/frame join incomplete')
    receipt_path = HERE / 'current-public' / (suffix + '-primary-compatibility.json')
    process_path = HERE / 'current-public' / (suffix + '-primary-processing.json')
    receipt = json.loads(receipt_path.read_text())
    processing = json.loads(process_path.read_text())
    expected = {'actual_analysis', 'native_validation', 'mandatory_observations',
                'lean_decoder', 'render', 'final_decode', 'four_camera_sources',
                'selected_measurements', 'negative_case_source'}
    if (receipt['case_id'] != case_id or receipt['candidate_id'] != 'primary' or
            receipt['construction_sha256'] != entry['construction_sha256'] or
            receipt['runtime_manifest_sha256'] != manifest['runtime_manifest_sha256'] or
            not receipt['passed'] or not expected <= set(receipt['checks'])):
        raise ValueError('Current-runtime exact-case compatibility missing')
    if not (processing['passed'] and processing['recorded_only'] and
            processing['originals_preserved']):
        raise ValueError('Recorded-only saved processing missing')
    proof_path = HERE / entry['physical_preparation']['receipt']
    physical = json.loads(proof_path.read_text())
    if (sha(proof_path) != entry['physical_preparation']['sha256'] or
            physical['original_native_observed'] is not False):
        raise ValueError('Synthetic physical preparation changed')
    return {'case_id': case_id, 'diagnostic_only': True,
            'physical_acceptance': False, 'legal_verdict': None,
            'source_kind': 'synthetic_fixture', 'joined_frames': len(rows),
            'compatibility_sha256': sha(receipt_path),
            'saved_processing_sha256': sha(process_path),
            'actor_frames_sha256': sha(source),
            'context_sha256': sha(context)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    print(json.dumps(check(args.case, args.diagnostic), sort_keys=True))

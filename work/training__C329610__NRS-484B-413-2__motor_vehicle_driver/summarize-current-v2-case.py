"""Bind one current runtime synthetic compatibility and saved processing proof."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(suffix, compatibility, saved):
    compatibility_receipt = compatibility / 'compatibility.json'
    processing_receipt = saved / 'v0001/processing.json'
    public = json.loads(compatibility_receipt.read_text())
    processing = json.loads(processing_receipt.read_text())
    manifest = HERE / ('current-v2-' + suffix + '-probe-manifest.json')
    entry = json.loads(manifest.read_text())['cases'][0]
    assert public['case_id'] == entry['case_id'] == processing['case_id']
    assert public['candidate_id'] == processing['candidate_id'] == 'primary'
    assert public['passed'] and processing['passed']
    assert public['construction_sha256'] == entry['construction_sha256']
    assert public['fixture_recipe_sha256'] == sha(HERE / ('current-v2-' + suffix + '-recipe.json'))
    assert public['measurement_contract_sha256'] == sha(HERE / entry['measurement_contract'])
    assert public['fixture_manifest']['native_samples.jsonl'] == sha(HERE / 'current-v2-case-sources' / suffix / 'native_samples.jsonl')
    assert public['negative_removed'] == 'native_samples.jsonl'
    assert public['negative_error_contains'] == 'Missing required source: native_samples.jsonl'
    assert processing['recorded_only'] and processing['originals_preserved']
    assert processing['timestamp_joins']['passed'] and processing['timestamp_joins']['frames'] == 800
    assert processing['final_video_checks']['passed'] and processing['final_video_checks']['frames'] == 800
    assert not processing['missing_evidence']
    assert not processing['physical_acceptance_claimed'] and not processing['legal_acceptance_claimed']
    proof = {
        'format': 'c329610-current-v2-case-proof-v1',
        'case_id': public['case_id'],
        'candidate_id': 'primary',
        'synthetic_cpu_only': True,
        'physical_acceptance_claimed': False,
        'legal_verdict_claimed': False,
        'manifest_sha256': sha(manifest),
        'construction_sha256': public['construction_sha256'],
        'fixture_recipe_sha256': public['fixture_recipe_sha256'],
        'measurement_contract_sha256': public['measurement_contract_sha256'],
        'native_samples_sha256': public['fixture_manifest']['native_samples.jsonl'],
        'compatibility': {
            'passed': True,
            'receipt_sha256': sha(compatibility_receipt),
            'checks': public['checks'],
            'negative_removed': public['negative_removed'],
            'negative_log_sha256': public['negative_log_sha256'],
            'continuous_signal_distance_ft': public['measurement_examples']['continuous_signal_distance_ft']['value'],
        },
        'recorded_only': {
            'passed': True,
            'receipt_sha256': sha(processing_receipt),
            'originals_preserved': True,
            'timestamp_join_frames': 800,
            'missing_evidence': False,
            'final_video_frames': 800,
            'final_video_sha256': processing['final_video_checks']['video_sha256'],
        },
    }
    path = HERE / ('current-v2-' + suffix + '-primary-proof.json')
    path.write_text(json.dumps(proof, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'case_id': public['case_id'], 'proof_sha256': sha(path),
                      'measured_distance_ft': proof['compatibility']['continuous_signal_distance_ft']}, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('suffix')
    parser.add_argument('compatibility', type=Path)
    parser.add_argument('saved', type=Path)
    args = parser.parse_args()
    main(args.suffix, args.compatibility, args.saved)

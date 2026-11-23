"""Audit a selected long fallback against the current compatibility core."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def audit(proof_path, output_path, attempt_path):
    proof_path = Path(proof_path).resolve()
    output_path = Path(output_path).resolve()
    attempt_path = Path(attempt_path).resolve()
    assert proof_path.parent == ROOT
    assert REPO / '.runtime-work' in output_path.parents
    assert REPO / '.runtime-work' in attempt_path.parents
    proof = read(proof_path)
    manifest_path = ROOT / 'execution-manifest.json'
    entry = next(item for item in read(manifest_path)['cases']
                 if item['case_id'] == proof['case_id'])
    candidate = next(item for item in entry['candidates']
                     if item['id'] == proof['candidate_id'])
    assert proof['passed'] is True
    assert proof['frames'] in (36120, 36121, 36122)
    assert proof['manifest_sha256'] == sha(manifest_path)
    assert proof['construction_sha256'] == candidate['construction_sha256']
    positive = output_path / 'positive'
    negative = output_path / 'negative'
    selection = read(positive / 'candidate-selection.json')
    assert selection['candidate_id'] == proof['candidate_id']
    assert selection['construction_sha256'] == candidate['construction_sha256']
    source_selection = read(attempt_path / 'candidate-selection.json')
    for key in ('case_id', 'candidate_id', 'construction_sha256', 'manifest_sha256'):
        assert source_selection[key] == selection[key]
    for source in ('acquisition-provenance.json', 'native-passenger-actors.jsonl',
                   'native-raw-actors.jsonl', 'video_frames.jsonl',
                   'overview.mkv', 'approach.mkv', 'reference_corner.mkv',
                   'driver_reference.mkv'):
        assert sha(attempt_path / source) == sha(positive / source)
    assert proof['positive_analysis_sha256'] == sha(positive / 'finalize_selected.py')
    required = {'acquisition_unchanged', 'actual_analysis', 'derived_outputs_rebuilt',
                'final_decode', 'four_camera_sources', 'lean_decoder',
                'mandatory_observations', 'native_validation', 'render'}
    assert required <= set(proof['core_checks'])
    assert read(positive / 'final-decode.json')['frames'] == proof['frames']
    for index in range(4):
        source = read(positive / f'source-{index}.json')
        assert source['passed'] and source['frames'] == proof['frames']
    assert proof['measurement_keys'] == ['signed_curb_observation']
    assert proof['negative_removed'] == 'native-passenger-actors.jsonl'
    assert not (negative / proof['negative_removed']).exists()
    negative_log = output_path / 'negative-analysis.log'
    assert sha(negative_log) == proof['negative_log_sha256']
    assert proof['negative_error_contains'] in negative_log.read_text()
    assert proof['scope'] == 'direct synthetic compatibility core; no pinned recipe receipt'
    assert proof['original_native_observed'] is False
    assert proof['physical_acceptance_claimed'] is False
    assert proof['legal_acceptance_claimed'] is False
    return {'format': 'c150142-current-long-fallback-core-audit-v1',
            'passed': True, 'case_id': proof['case_id'],
            'candidate_id': proof['candidate_id'], 'frames': proof['frames'],
            'manifest_sha256': proof['manifest_sha256'],
            'construction_sha256': proof['construction_sha256'],
            'proof_sha256': sha(proof_path),
            'final_decode_sha256': sha(positive / 'final-decode.json'),
            'negative_log_sha256': sha(negative_log),
            'official_recipe_compatibility_passed': False,
            'original_native_observed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--proof', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--attempt', required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.proof, args.output, args.attempt), indent=2))

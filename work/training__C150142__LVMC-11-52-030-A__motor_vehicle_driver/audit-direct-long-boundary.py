"""Bind an exact long boundary core diagnostic to its selected construction."""
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


def audit(case, frames, proof_path, output_path):
    proof_path = Path(proof_path)
    output_path = Path(output_path)
    assert REPO / '.runtime-work' in output_path.resolve().parents
    proof = read(proof_path)
    manifest_path = ROOT / 'execution-manifest.json'
    entry = next(item for item in read(manifest_path)['cases']
                 if item['case_id'] == proof['case_id'])
    positive = output_path / 'positive'
    negative = output_path / 'negative'
    assert proof['passed'] is True
    assert proof['case_id'] == ROOT.name + '__' + case
    assert proof['candidate_id'] == 'primary'
    assert proof['frames'] == frames
    assert proof['manifest_sha256'] == sha(manifest_path)
    assert proof['construction_sha256'] == entry['construction_sha256']
    assert proof['positive_analysis_sha256'] == sha(positive / 'finalize_selected.py')
    selection = read(positive / 'candidate-selection.json')
    assert selection['construction_sha256'] == entry['construction_sha256']
    required = {'acquisition_unchanged', 'actual_analysis', 'derived_outputs_rebuilt',
                'final_decode', 'four_camera_sources', 'lean_decoder',
                'mandatory_observations', 'native_validation', 'render'}
    assert required <= set(proof['core_checks'])
    assert read(positive / 'final-decode.json')['frames'] == frames
    for index in range(4):
        source = read(positive / f'source-{index}.json')
        assert source['passed'] and source['frames'] == frames
    boundary = read(positive / 'analysis-report.json')['measurements'] \
        ['signed_curb_observation']['value']['duration_relative_to_30_minutes']
    expected = {'tour_bus_below': 'below', 'tour_bus_at': 'at',
                'tour_bus_above': 'above'}[case]
    assert boundary == expected
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
    return {'format': 'c150142-current-direct-long-boundary-audit-v1',
            'passed': True, 'case_id': proof['case_id'], 'candidate_id': 'primary',
            'frames': frames, 'boundary': boundary,
            'manifest_sha256': proof['manifest_sha256'],
            'proof_sha256': sha(proof_path),
            'final_decode_sha256': sha(positive / 'final-decode.json'),
            'negative_log_sha256': sha(negative_log),
            'official_recipe_compatibility_passed': False,
            'original_native_observed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=('tour_bus_below', 'tour_bus_at',
                                           'tour_bus_above'), required=True)
    parser.add_argument('--frames', type=int, required=True)
    parser.add_argument('--proof', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.case, args.frames, args.proof, args.output), indent=2))

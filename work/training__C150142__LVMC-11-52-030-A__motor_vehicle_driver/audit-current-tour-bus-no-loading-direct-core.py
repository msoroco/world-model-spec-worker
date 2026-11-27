"""Audit the selected no-loading direct synthetic Core diagnostic."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = REPO / '.runtime-work/c150142-current-tour-bus-no-loading-primary-direct-v2'
PROOF = HERE / 'current-tour-bus-no-loading-primary-direct-core.json'
CASE = HERE.name + '__tour_bus_no_loading'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def audit():
    proof = read(PROOF)
    manifest_path = HERE / 'execution-manifest.json'
    entry = next(item for item in read(manifest_path)['cases']
                 if item['case_id'] == CASE)
    assert proof['passed'] is True
    assert proof['case_id'] == CASE and proof['candidate_id'] == 'primary'
    assert proof['frames'] == 36121
    assert proof['manifest_sha256'] == sha(manifest_path)
    assert proof['construction_sha256'] == entry['construction_sha256']
    assert proof['prior_source_selection'] is True
    assert proof['source_selection_manifest_sha256'] != proof['manifest_sha256']
    assert proof['negative_removed'] == 'native-passenger-inventory.jsonl'
    assert proof['negative_error_contains'] == 'Missing required source: native-passenger-inventory.jsonl'
    assert proof['scope'] == 'direct synthetic compatibility core; no pinned recipe receipt'
    assert proof['original_native_observed'] is False
    assert proof['physical_acceptance_claimed'] is False
    assert proof['legal_acceptance_claimed'] is False
    assert set(proof['core_checks']) >= {
        'acquisition_unchanged', 'actual_analysis', 'derived_outputs_rebuilt',
        'final_decode', 'four_camera_sources', 'lean_decoder',
        'mandatory_observations', 'native_validation', 'render'}
    positive = OUT / 'positive'
    assert read(positive / 'candidate-selection.json')['construction_sha256'] == entry['construction_sha256']
    assert sha(positive / 'finalize_selected.py') == proof['positive_analysis_sha256']
    final = read(positive / 'final-decode.json')
    assert final['passed'] is True and final['frames'] == 36121
    for index in range(4):
        source = read(positive / f'source-{index}.json')
        assert source['passed'] is True and source['frames'] == 36121
    negative = OUT / 'negative'
    log = OUT / 'negative-analysis.log'
    assert sha(log) == proof['negative_log_sha256']
    assert proof['negative_error_contains'] in log.read_text()
    assert not (negative / proof['negative_removed']).exists()
    return {'format': 'c150142-current-no-loading-direct-core-audit-v1',
            'passed': True, 'case_id': CASE, 'frames': 36121,
            'proof_sha256': sha(PROOF), 'manifest_sha256': proof['manifest_sha256'],
            'construction_sha256': proof['construction_sha256'],
            'source_selection_manifest_sha256': proof['source_selection_manifest_sha256'],
            'final_decode_sha256': sha(positive / 'final-decode.json'),
            'negative_log_sha256': proof['negative_log_sha256'],
            'official_fixture_recipe_compatibility_passed': False,
            'original_native_observed': False}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2, sort_keys=True))

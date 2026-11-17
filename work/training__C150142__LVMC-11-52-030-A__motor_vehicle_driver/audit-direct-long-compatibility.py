"""Bind a worker direct long compatibility core proof to exact selected bytes."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CASE = ROOT.name + '__tour_bus_above'
OUT = REPO / '.runtime-work/c150142-direct-long-compat-tour-bus-above-primary-v1'


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def audit():
    manifest_path = ROOT / 'execution-manifest.json'
    entry = next(item for item in read(manifest_path)['cases']
                 if item['case_id'] == CASE)
    proof = read(ROOT / 'update055-tour-bus-above-direct-compat.log')
    positive = OUT / 'positive'
    negative = OUT / 'negative'
    expected_checks = {'acquisition_unchanged', 'actual_analysis',
                       'derived_outputs_rebuilt', 'final_decode',
                       'four_camera_sources', 'lean_decoder',
                       'mandatory_observations', 'native_validation', 'render'}
    assert proof['passed'] is True
    assert proof['case_id'] == CASE and proof['candidate_id'] == 'primary'
    assert proof['frames'] == 36122
    assert proof['manifest_sha256'] == sha(manifest_path)
    assert proof['construction_sha256'] == entry['construction_sha256']
    assert set(proof['core_checks']) >= expected_checks
    assert proof['measurement_keys'] == ['signed_curb_observation']
    assert proof['scope'] == 'direct synthetic compatibility core; no pinned recipe receipt'
    assert proof['original_native_observed'] is False
    assert proof['physical_acceptance_claimed'] is False
    assert proof['legal_acceptance_claimed'] is False
    assert read(positive / 'candidate-selection.json')['construction_sha256'] == entry['construction_sha256']
    assert sha(positive / 'finalize_selected.py') == proof['positive_analysis_sha256']
    assert read(positive / 'final-decode.json')['passed'] is True
    assert read(positive / 'final-decode.json')['frames'] == 36122
    for index in range(4):
        source = read(positive / ('source-' + str(index) + '.json'))
        assert source['passed'] is True and source['frames'] == 36122
    negative_log = OUT / 'negative-analysis.log'
    assert sha(negative_log) == proof['negative_log_sha256']
    assert proof['negative_removed'] == 'native-passenger-actors.jsonl'
    assert proof['negative_error_contains'] in negative_log.read_text()
    assert not (negative / proof['negative_removed']).exists()
    return {'format': 'c150142-direct-long-compatibility-audit-v1',
            'passed': True, 'case_id': CASE, 'frames': 36122,
            'manifest_sha256': proof['manifest_sha256'],
            'positive_final_decode_sha256': sha(positive / 'final-decode.json'),
            'negative_log_sha256': proof['negative_log_sha256'],
            'scope': proof['scope'], 'original_native_observed': False}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))

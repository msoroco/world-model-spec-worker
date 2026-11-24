"""Check durable primary diagnostic receipts against current authored sources."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIMARY = HERE / 'v2-primary/witness_1'
PROOFS = PRIMARY / 'proofs'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    manifest = read(HERE / 'v2-primary-manifest.json')
    case = manifest['cases'][0]
    compatibility = read(PROOFS / 'compatibility.json')
    processing = read(PROOFS / 'processing.json')
    selection = read(PROOFS / 'candidate-selection.json')
    report = read(PROOFS / 'analysis-report.json')
    expected = {'actual_analysis', 'native_validation', 'mandatory_observations',
                'lean_decoder', 'render', 'final_decode', 'acquisition_unchanged',
                'derived_outputs_rebuilt', 'four_camera_sources',
                'selected_measurements', 'negative_case_source'}
    assert compatibility['passed'] is True
    assert set(compatibility['checks']) == expected
    assert compatibility['case_id'] == case['case_id'] == processing['case_id']
    assert compatibility['construction_sha256'] == case['construction_sha256']
    assert sha(PRIMARY / 'construction.json') == case['construction_sha256']
    assert compatibility['fixture_recipe_sha256'] == sha(PRIMARY / 'recipe.json')
    assert compatibility['measurement_contract_sha256'] == sha(PRIMARY / 'measurement-contract.json')
    assert compatibility['analysis_report_sha256'] == sha(PROOFS / 'analysis-report.json')
    assert compatibility['negative_log_sha256'] == sha(PROOFS / 'negative-analysis.log')
    assert compatibility['log_sha256'] == sha(PROOFS / 'positive-analysis.log')
    assert compatibility['negative_removed'] == 'c111331-native-samples.jsonl'
    assert compatibility['negative_error_contains'] in (PROOFS / 'negative-analysis.log').read_text()
    assert selection['candidate_id'] == 'primary'
    assert selection['construction_sha256'] == case['construction_sha256']
    assert processing['recorded_only'] is True and processing['missing_evidence'] is False
    assert processing['physical_acceptance_claimed'] is False
    assert processing['legal_acceptance_claimed'] is False
    assert 'selected_analysis_executed' in processing['events']
    assert 'originals_verified' in processing['events']
    measurement = report['measurements']['pedestrian_entry_signal']['value']
    assert measurement['entry_frame'] == 230 and measurement['exit_frame'] == 291
    assert measurement['native_provenance'] is False and measurement['legal_verdict'] is None
    source_hashes = report['measurements']['pedestrian_entry_signal']['sources']
    for name, digest in source_hashes.items():
        assert digest == sha(PRIMARY / 'sources' / name)
    return {'case_id': case['case_id'], 'compatibility_sha256': sha(PROOFS / 'compatibility.json'),
            'processing_sha256': sha(PROOFS / 'processing.json'),
            'construction_sha256': case['construction_sha256'],
            'recipe_sha256': sha(PRIMARY / 'recipe.json'),
            'checks': len(expected), 'entry_frame': measurement['entry_frame'],
            'diagnostic_only': True}


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))

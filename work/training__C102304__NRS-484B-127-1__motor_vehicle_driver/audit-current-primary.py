"""Independently bind the current C102304 primary CPU diagnostic receipts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
COMPAT = ROOT / '.runtime-work/c102304-current-compat-a5'
SAVED = ROOT / '.runtime-work/c102304-current-saved-a5/v0001'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    manifest_path = HERE / 'current-diagnostic-manifest.json'
    manifest = read(manifest_path)
    entry = manifest['cases'][0]
    compatibility = read(COMPAT / 'compatibility.json')
    saved = read(SAVED / 'processing.json')
    recipe = HERE / 'current-fixture/condition_a-recipe.json'
    contract = HERE / 'current-fixture/condition_a-measurement-contract.json'
    construction = HERE / 'current-fixture/condition_a-primary-construction.json'
    runtime = ROOT / 'runtime/pipeline/SOURCE-MANIFEST.json'
    case = entry['case_id']
    assert manifest['runtime_manifest_sha256'] == sha(runtime)
    assert entry['construction_sha256'] == sha(construction)
    assert compatibility['format'] == 'worker-package-compatibility'
    assert compatibility['case_id'] == case and compatibility['candidate_id'] == 'primary'
    assert compatibility['passed'] is True
    assert compatibility['runtime_manifest_sha256'] == sha(runtime)
    assert compatibility['construction_sha256'] == sha(construction)
    assert compatibility['fixture_recipe_sha256'] == sha(recipe)
    assert compatibility['measurement_contract_sha256'] == sha(contract)
    assert compatibility['negative_removed'] == 'native_samples.jsonl'
    assert compatibility['negative_error_contains'] in (COMPAT / 'negative-analysis.log').read_text()
    assert compatibility['negative_log_sha256'] == sha(COMPAT / 'negative-analysis.log')
    assert compatibility['analysis_report_sha256'] == sha(COMPAT / 'analysis-report.json')
    assert compatibility['log_sha256'] == sha(COMPAT / 'compatibility-analysis.log')
    assert {'selected_measurements', 'negative_case_source', 'lean_decoder',
            'four_camera_sources', 'final_decode', 'derived_outputs_rebuilt'} <= set(compatibility['checks'])
    assert len((COMPAT / 'video_frames.jsonl').read_text().splitlines()) == 900
    report = read(COMPAT / 'analysis-report.json')
    observed = report['measurements']['moving_following_interval']['value']
    assert observed['median_bumper_gap_m'] == 10.0
    assert observed['following_duration_s'] == 45.0
    result = read(COMPAT / 'result.json')
    assert result['accepted'] is False and result['legal_verdict_claimed'] is False
    assert saved['format'] == 'worker-saved-processing' and saved['passed'] is True
    assert saved['case_id'] == case and saved['candidate_id'] == 'primary'
    assert saved['analysis_revision']['construction_sha256'] == sha(construction)
    assert saved['analysis_revision']['runtime_manifest_sha256'] == sha(runtime)
    assert saved['recorded_only'] is True and saved['originals_preserved'] is True
    assert saved['timestamp_joins']['passed'] is True and saved['timestamp_joins']['frames'] == 900
    assert saved['final_video_checks']['passed'] is True and saved['final_video_checks']['frames'] == 900
    assert saved['physical_acceptance_claimed'] is False and saved['legal_acceptance_claimed'] is False
    for index in range(4):
        audit = read(SAVED / f'source-{index}.json')
        assert audit['passed'] is True and audit['frames'] == 900
    summary = {
        'format': 'c102304-current-primary-cpu-audit',
        'case_id': case, 'candidate_id': 'primary', 'frames': 900,
        'source_cameras': 4, 'median_bumper_gap_m': 10.0,
        'compatibility_receipt_sha256': sha(COMPAT / 'compatibility.json'),
        'saved_processing_receipt_sha256': sha(SAVED / 'processing.json'),
        'manifest_sha256': sha(manifest_path), 'construction_sha256': sha(construction),
        'runtime_manifest_sha256': sha(runtime), 'recipe_sha256': sha(recipe),
        'source_status': 'synthetic_diagnostic_only',
        'native_or_physical_acceptance_claimed': False,
    }
    (HERE / 'current-primary-proof.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, sort_keys=True))


if __name__ == '__main__':
    main()

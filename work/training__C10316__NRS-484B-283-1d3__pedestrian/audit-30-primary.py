"""Bind the 600-frame public CPU software path without asserting physical review."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
COMPAT = ROOT / '.runtime-work/c10316-30-compat-2'
SAVED = ROOT / '.runtime-work/c10316-30-saved-1/v0001'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    manifest_path = HERE / 'draft-execution-manifest.json'
    manifest = read(manifest_path)
    case = manifest['cases'][0]
    runtime_sha = sha(ROOT / 'runtime/pipeline/SOURCE-MANIFEST.json')
    construction = HERE / case['construction']
    recipe = ROOT / case['fixture_recipe']
    contract = HERE / case['measurement_contract']
    c = read(COMPAT / 'compatibility.json')
    s = read(SAVED / 'processing.json')
    report = read(COMPAT / 'analysis-report.json')
    result = read(COMPAT / 'result.json')
    assert manifest['runtime_manifest_sha256'] == runtime_sha
    assert case['construction_sha256'] == sha(construction)
    assert c['passed'] is True and c['case_id'] == case['case_id']
    assert c['candidate_id'] == 'primary'
    assert c['runtime_manifest_sha256'] == runtime_sha
    assert c['construction_sha256'] == sha(construction)
    assert c['fixture_recipe_sha256'] == sha(recipe)
    assert c['measurement_contract_sha256'] == sha(contract)
    assert c['negative_removed'] == 'no-countdown-samples.jsonl'
    assert c['negative_error_contains'] in (COMPAT/'negative-analysis.log').read_text()
    assert c['negative_log_sha256'] == sha(COMPAT/'negative-analysis.log')
    assert {'four_camera_sources', 'lean_decoder', 'derived_outputs_rebuilt',
            'negative_case_source', 'final_decode'} <= set(c['checks'])
    assert s['passed'] is True and s['recorded_only'] is True
    assert s['originals_preserved'] is True
    assert s['case_id'] == case['case_id'] and s['candidate_id'] == 'primary'
    assert s['analysis_revision']['runtime_manifest_sha256'] == runtime_sha
    assert s['analysis_revision']['construction_sha256'] == sha(construction)
    assert s['timestamp_joins']['frames'] == 600 and s['timestamp_joins']['passed'] is True
    assert s['final_video_checks']['frames'] == 600 and s['final_video_checks']['passed'] is True
    assert s['physical_acceptance_claimed'] is False and s['legal_acceptance_claimed'] is False
    value = report['measurements']['no_countdown_entry_and_clearance']['value']
    assert value['original_frames'] == 600 and value['entry_indication'] == 'walk'
    assert value['source_kind'] == 'synthetic_scene_request'
    assert value['governing_device_observed'] is False
    assert result['accepted'] is False and result['legal_verdict_claimed'] is False
    receipt = {'format': 'c10316-current-30-second-primary-audit',
               'case_id': case['case_id'], 'frames': 600, 'rate_hz': 20,
               'duration_s': 30, 'source_cameras': 4,
               'entry_indication': value['entry_indication'],
               'source_kind': 'synthetic_scene_request',
               'runtime_manifest_sha256': runtime_sha,
               'manifest_sha256': sha(manifest_path),
               'construction_sha256': sha(construction),
               'recipe_sha256': sha(recipe),
               'compatibility_sha256': sha(COMPAT/'compatibility.json'),
               'saved_processing_sha256': sha(SAVED/'processing.json'),
               'physical_or_legal_acceptance_claimed': False}
    (HERE/'primary-30-proof.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()

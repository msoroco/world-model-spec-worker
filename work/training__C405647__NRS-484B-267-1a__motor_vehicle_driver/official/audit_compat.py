"""Independently join retained exact portable receipts to official sources."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CHECKS = {'actual_analysis', 'native_validation', 'mandatory_observations',
          'lean_decoder', 'render', 'final_decode', 'acquisition_unchanged'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    manifest = json.loads((HERE / 'package-manifest.json').read_text())
    manifest_sha = sha(HERE / 'package-manifest.json')
    batch = json.loads((REPO / 'batch.json').read_text())
    assert manifest['status'] == 'draft_not_selected'
    assert len(manifest['cases']) == 2
    checked = set()
    for entry in manifest['cases']:
        case = entry['case_id'].rsplit('__', 1)[1]
        for ref in [entry] + entry['candidates']:
            candidate = ref['id']
            key = case, candidate
            assert key not in checked
            checked.add(key)
            folder = HERE / 'portable-receipts' / case / candidate
            summary = json.loads((folder / 'summary.json').read_text())
            receipt = json.loads((folder / 'compatibility.json').read_text())
            report = json.loads((folder / 'analysis-report.json').read_text())
            result = json.loads((folder / 'result.json').read_text())
            assert summary['manifest_sha256'] == manifest_sha
            assert summary['case_id'] == entry['case_id']
            assert summary['candidate_id'] == candidate
            assert summary['positive_receipt_sha256'] == sha(folder / 'compatibility.json')
            assert summary['positive_log_sha256'] == sha(folder / 'portable-analysis.log')
            assert summary['negative_log_sha256'] == sha(folder / 'negative-analysis.log')
            assert summary['negative_error'] in (folder / 'negative-analysis.log').read_text()
            assert receipt['format'] == 'worker-package-compatibility-v1'
            assert receipt['passed'] is True and CHECKS <= set(receipt['checks'])
            assert receipt['case_id'] == entry['case_id'] and receipt['candidate_id'] == candidate
            assert receipt['construction_sha256'] == ref['construction_sha256']
            assert receipt['runtime_manifest_sha256'] == batch['runtime']['source_manifest_sha256']
            assert receipt['log_sha256'] == sha(folder / 'portable-analysis.log')
            construction = json.loads((HERE / ref['construction']).read_text())
            code = next(item['content'] for item in construction['files'] if item['path'] == 'finalize.py')
            assert receipt['analysis_sha256'] == hashlib.sha256(code.encode()).hexdigest()
            source_manifest = receipt['fixture_manifest']
            assert len([name for name in source_manifest if name.startswith('capture/native/graphs/base/')]) == 480
            assert source_manifest['actor-frames.jsonl'] == sha(
                HERE / 'saved-fixtures' / case / candidate / 'actor-frames.jsonl')
            assert source_manifest['source-scope.json'] == sha(
                HERE / 'saved-fixtures' / case / candidate / 'source-scope.json')
            assert source_manifest['road.xodr'] == sha(HERE / 'drafts/road.xodr')
            assert report['case_id'] == entry['case_id'] and result['case_id'] == entry['case_id']
            assert 'official_approach_clearance' in report['measurements']
            assert result['accepted'] is False and result['setup_confirmed'] is False
            assert result['physical_failure_flags']
            decode = json.loads((folder / 'final-decode.json').read_text())
            assert decode.get('frames') == 480 or decode.get('frame_count') == 480
    assert len(checked) == 8
    return {'passed': True, 'exact_portable_positive_negative_receipts': len(checked),
            'source_and_construction_hashes_joined': True,
            'physical_or_legal_outcome_verified': False,
            'strict_recipe_v2_verified': False}


if __name__ == '__main__':
    print(json.dumps(audit(), sort_keys=True))

"""Independent exact-manifest/log audit of all 24 v1 synthetic probes."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPO=HERE.parent.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    matrix=json.loads((HERE/'draft-package-probe-summary.json').read_text())
    manifest=json.loads((HERE/'draft-execution-manifest.json').read_text())
    assert len(matrix['results'])==24 and not matrix['selected'] and not matrix['original_native_observed']
    refs={}
    for entry in manifest['cases']:
        refs[(entry['case_id'],'primary')]=entry
        refs.update({(entry['case_id'],r['id']):r for r in entry['candidates']})
    assert len(refs)==24
    found=set()
    required={'actual_analysis','native_validation','mandatory_observations','lean_decoder',
              'render','final_decode','acquisition_unchanged'}
    for item in matrix['results']:
        key=(item['case_id'],item['candidate_id'])
        assert key in refs and key not in found
        found.add(key)
        ref=refs[key]
        assert sha(HERE/ref['construction'])==ref['construction_sha256']==item['construction_sha256']
        log=HERE/item['log']
        assert sha(log)==item['log_sha256']
        lines=log.read_text().splitlines()
        assert lines and lines[0].startswith('scratch ')
        result=json.loads(lines[-1])
        positive=result['positive']
        assert result['case_id']==item['case_id'] and result['candidate_id']==item['candidate_id']
        assert positive['format']=='worker-package-compatibility-v1' and positive['passed']
        assert positive['construction_sha256']==ref['construction_sha256']
        assert positive['runtime_manifest_sha256']==manifest['runtime_manifest_sha256']
        assert required<=set(positive['checks'])
        assert result['negative']['exit_code']!=0 and result['negative']['removed']=='native_samples.jsonl'
        assert result['synthetic'] and not result['selected'] and not result['original_pixels']
    assert found==set(refs)
    print(json.dumps({'cases_audited':6,'exact_v1_positives':24,'exact_removed_source_negatives':24,
                      'selected':False,'original_native_observed':False}))


if __name__=='__main__':main()

"""Verify and summarize every update-012 source-hashed exact CPU proof."""
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text())

def main():
    runtime=sha(ROOT/'runtime/main-pipeline-v7/SOURCE-MANIFEST.json')
    rows=[]
    for manifest_path in sorted((ROOT/'work').glob('testing__*/execution-manifest.json')):
        manifest=read(manifest_path);folder=manifest_path.parent
        if manifest['runtime_manifest_sha256']!=runtime:raise ValueError('Runtime binding differs: '+str(manifest_path))
        for entry in manifest['cases']:
            result={'case_id':entry['case_id'],'assignment_id':manifest['assignment_id'],'candidates':{}}
            for label,proof in [('primary',entry),('fallback1',entry['candidates'][0])]:
                construction=folder/proof['construction'];offline=proof['offline'];compat=proof['compatibility']
                receipt_path=folder/compat['receipt'];receipt=read(receipt_path)
                checks={
                    'construction_sha256':sha(construction),
                    'offline_log_sha256':sha(folder/offline['log']),
                    'compatibility_receipt_sha256':sha(receipt_path),
                    'analysis_log_sha256':sha(folder/compat['log']),
                    'negative_log_sha256':sha(folder/compat['negative_log']),
                }
                if (checks['construction_sha256']!=proof['construction_sha256']
                        or checks['offline_log_sha256']!=offline['log_sha256']
                        or checks['compatibility_receipt_sha256']!=compat['sha256']
                        or checks['analysis_log_sha256']!=receipt['log_sha256']
                        or checks['negative_log_sha256']!=receipt['negative_log_sha256']
                        or receipt['runtime_manifest_sha256']!=runtime
                        or receipt['candidate_id']!=label
                        or receipt['fixture_recipe_sha256']!=sha(ROOT/entry['fixture_recipe'])
                        or offline['exit_code']!=0 or compat['exit_code']!=0):
                    raise ValueError('Exact proof mismatch: '+entry['case_id']+' '+label)
                result['candidates'][label]=checks
            saved=entry['post_capture'];result['saved_log_sha256']=sha(folder/saved['test_log'])
            if saved['test_exit_code']!=0 or result['saved_log_sha256']!=saved['test_log_sha256']:
                raise ValueError('Saved processing proof mismatch: '+entry['case_id'])
            rows.append(result)
    comparison=read(ROOT/'work/_shared/comparison-proofs.json')
    summary={'format':'worker-v7-proof-index-v1','runtime_manifest_sha256':runtime,
             'assignments':len({r['assignment_id'] for r in rows}), 'cases':len(rows),
             'primary_proofs':len(rows),'fallback1_proofs':len(rows),'saved_processing_proofs':len(rows),
             'comparisons':sum(x['comparisons'] for x in comparison),
             'case_proofs':rows,
             'comparison_proofs_sha256':sha(ROOT/'work/_shared/comparison-proofs.json'),
             'integration_proof_sha256':sha(ROOT/'work/_shared/local-integration-proof.json'),
             'runtime_proof_sha256':sha(ROOT/'work/_shared/runtime-proof.json')}
    path=ROOT/'work/_shared/v7-proof-index.json';path.write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({key:value for key,value in summary.items() if key!='case_proofs'},indent=2))
if __name__=='__main__':main()

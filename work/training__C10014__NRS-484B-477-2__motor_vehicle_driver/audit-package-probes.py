"""Independently inspect all diagnostic exact package positive/negative executions."""
import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
from worker_exchange.common import digest,tree
SUFFIXES=('reference','contrast')
CANDIDATES=('primary','fallback1','fallback2','fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    manifest=json.loads((HERE/'draft-execution-manifest.json').read_text())
    rows=[]
    for suffix in SUFFIXES:
        entry=next(row for row in manifest['cases'] if row['case_id'].endswith('__'+suffix))
        for candidate in CANDIDATES:
            filename='package-compatibility-'+suffix+('' if candidate=='primary' else '-'+candidate)+'.log'
            log=HERE/filename
            lines=log.read_text().splitlines()
            if len(lines)!=2 or not lines[0].startswith('scratch '):
                raise ValueError('Incomplete diagnostic run: '+filename)
            scratch=Path(lines[0][8:])
            if ROOT/'.runtime-work' not in scratch.parents:
                raise ValueError('Unexpected scratch location')
            result=json.loads(lines[1]);positive=result['positive'];negative=result['negative']
            if result.get('case_suffix')!=suffix or result.get('candidate')!=candidate:
                raise ValueError('Wrong diagnostic identity')
            selected=entry if candidate=='primary' else next(c for c in entry['candidates'] if c['id']==candidate)
            if (positive['format']!='worker-package-compatibility-v1' or positive['passed'] is not True
                or positive['case_id']!=entry['case_id'] or positive['candidate_id']!=candidate
                or positive['construction_sha256']!=selected['construction_sha256']
                or positive['runtime_manifest_sha256']!=manifest['runtime_manifest_sha256']):
                raise ValueError('Stale or failed positive '+suffix+' '+candidate)
            required={'actual_analysis','native_validation','mandatory_observations','lean_decoder',
                      'render','final_decode','acquisition_unchanged'}
            if not required<=set(positive['checks']):
                raise ValueError('Missing positive check')
            stored=json.loads((scratch/'output/compatibility.json').read_text())
            if any(stored.get(key)!=value for key,value in positive.items()):
                raise ValueError('Saved receipt differs from log')
            if digest(tree(scratch/'fixture'))!=positive['fixture_sha256']:
                raise ValueError('Diagnostic fixture changed')
            if sha(scratch/'output/finalize.py')!=positive['analysis_sha256']:
                raise ValueError('Packaged finalizer changed')
            if sha(scratch/'output/compatibility-analysis.log')!=positive['log_sha256']:
                raise ValueError('Saved analysis log changed')
            if not all(json.loads((scratch/'output'/f'source-{i}.json').read_text())['passed']
                       and json.loads((scratch/'output'/f'source-{i}.json').read_text())['frames']==480
                       for i in range(4)):
                raise ValueError('Missing source-video audit')
            if not json.loads((scratch/'output/final-decode.json').read_text())['passed']:
                raise ValueError('Final render decode failed')
            native_result=json.loads((scratch/'output/result.json').read_text())
            if native_result['accepted'] or native_result['legal_verdict_claimed'] or any(
                check.get('physical_cause_confirmed') for check in native_result['target_checks']):
                raise ValueError('Synthetic diagnostic claimed physical success or acceptance')
            if (negative['exit_code']==0 or negative['removed']!='native_samples.jsonl'
                or negative['error_contains']!='Missing required source: native_samples.jsonl'
                or negative['error_contains'] not in (scratch/'negative-analysis.log').read_text()):
                raise ValueError('Negative proof absent')
            rows.append({'case_suffix':suffix,'candidate':candidate,
                         'positive_receipt_sha256':sha(scratch/'output/compatibility.json'),
                         'negative_log_sha256':sha(scratch/'negative-analysis.log'),
                         'command_log_sha256':sha(log),'scope':'synthetic diagnostic v1, unselected'})
    output={'format':'c10014-477-2-diagnostic-package-audit-v1','count':len(rows),'rows':rows,
            'ready':False,'strict_v2_compatibility':False}
    (HERE/'draft-package-probe-summary.json').write_text(json.dumps(output,indent=2)+'\n')
    return output


if __name__=='__main__':print(json.dumps(audit(),indent=2))

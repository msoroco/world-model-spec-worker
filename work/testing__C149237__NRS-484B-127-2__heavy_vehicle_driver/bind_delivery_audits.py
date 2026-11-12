"""Run and bind every exact C149237 diagnostic delivery-audit CPU proof."""
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PYTHON = '.venv-cpu/bin/python'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command, log):
    with log.open('w') as stream:
        result = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                                text=True)
    return result.returncode


def main():
    manifest_path=HERE/'execution-manifest.json'
    manifest=json.loads(manifest_path.read_text())
    batch=json.loads((ROOT/'batch.json').read_text())
    sets=batch['assignments'][HERE.name]['set_ids']
    script='delivery_audit.py'
    script_hash=sha(HERE/script)
    checks=['native_source','all_participants','time_join','full_video_decode',
            'actual_pixels','physical_completion']
    records=[]
    for entry in manifest['cases']:
        case=entry['case_id']
        suffix=case.removeprefix(HERE.name+'__')
        source=f'.runtime-work/c149237-{suffix}-saved-v14/v0001/analysis'
        output=f'.runtime-work/c149237-delivery-{suffix}-v2'
        positive=[PYTHON,str((HERE/'prove_delivery_audit.py').relative_to(ROOT)),
                  '--source',source,'--case',case,'--output-root',output]
        positive_log=HERE/(suffix+'-delivery-positive.log')
        if run(positive,positive_log):
            raise ValueError('Diagnostic delivery proof failed: '+suffix+'; see '+str(positive_log))
        negative=[PYTHON,str((HERE/script).relative_to(ROOT)),
                  '--attempt',output+'/attempt','--case',case,
                  '--job-id','diagnostic-job','--attempt-number','1',
                  '--recording-id','diagnostic-recording',
                  '--pixel-review',output+'/pixel-review.json',
                  '--output',output+'/attempt/negative-native-audit.json',
                  '--decode-receipt',output+'/source-decode.json']
        negative_log=HERE/(suffix+'-delivery-negative.log')
        negative_exit=run(negative,negative_log)
        expected='Original source frame count differs from planned capture'
        if negative_exit==0 or expected not in negative_log.read_text():
            raise ValueError('Diagnostic Native rejection failed: '+suffix)
        records.append((entry,{'case_id':case,'sets':sets,'checks':checks,
            'script':script,'script_sha256':script_hash,
            'command':' '.join(positive),'test_exit_code':0,
            'test_log':positive_log.name,'test_log_sha256':sha(positive_log),
            'negative_command':' '.join(negative),'negative_exit_code':negative_exit,
            'negative_expected_error':expected,'negative_log':negative_log.name,
            'negative_log_sha256':sha(negative_log)}))
    for entry, receipt in records:
        entry['delivery_acceptance']=receipt
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'cases':len(records),'bound_diagnostic_delivery_audits':True,
                      'physical_acceptance_claimed':False},sort_keys=True))


if __name__ == '__main__':
    main()

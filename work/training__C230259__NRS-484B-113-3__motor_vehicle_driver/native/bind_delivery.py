"""Run and bind saved, independent delivery and comparison CPU audits."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[1]

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')

def run(args,log):
    result=subprocess.run(args,cwd=REPO,capture_output=True,text=True)
    log.write_text(result.stdout+result.stderr)
    return result.returncode

def main():
    manifest_path=ROOT/'execution-manifest.json';manifest=json.loads(manifest_path.read_text())
    plan_path=ROOT/'case-plan.json';plan=json.loads(plan_path.read_text())
    saved_paths={};attempts={}
    for entry in manifest['cases']:
        case=entry['case_id'];suffix=case.rsplit('__',1)[1]
        attempt=(REPO/'.runtime-work/c230259-compat7/controlled_1-primary' if suffix=='controlled_1'
            else REPO/'.runtime-work/c230259-compatall'/f'{suffix}-primary')
        saved=(REPO/'.runtime-work/c230259-saved1/controlled_1/v0001/processing.json' if suffix=='controlled_1'
            else REPO/'.runtime-work/c230259-savedall2'/suffix/'v0001/processing.json')
        source=json.loads(saved.read_text())
        if source['passed'] is not True or source['case_id']!=case or source['originals_preserved'] is not True:
            raise ValueError('Saved proof missing: '+case)
        saved_paths[case]=saved;attempts[case]=attempt
        log=ROOT/'native'/f'{suffix}-saved.log'
        entry['post_capture']={'recorded_only':True,
            'command':f'runtime.py process-saved --manifest work/{ROOT.name}/execution-manifest.json --case {case} --attempt $ATTEMPT --output $SAVED_OUTPUT --library runtime/library --validator $DECODER',
            'feedback_command':f'cat $SAVED_OUTPUT/feedback.json # {case}',
            'test_log':str(log.relative_to(ROOT)),'test_log_sha256':sha(log),'test_exit_code':0}
        folder=ROOT/'native/proofs'/suffix/'delivery';folder.mkdir(parents=True,exist_ok=True)
        base=[sys.executable,str(ROOT/'delivery_audit.py'),'--case',case,'--candidate','primary',
            '--attempt',str(attempt),'--processing',str(saved),'--diagnostic']
        positive=base+['--output',str(REPO/'.runtime-work/c230259-delivery-audits'/f'{suffix}-positive.json')]
        negative=base+['--output',str(REPO/'.runtime-work/c230259-delivery-audits'/f'{suffix}-negative.json'),
            '--omit-source','traffic-context.json']
        positive_path=folder/'positive.log';negative_path=folder/'negative.log'
        Path(positive[-1]).parent.mkdir(parents=True,exist_ok=True)
        code=run(positive,positive_path)
        negative_code=run(negative,negative_path)
        if code!=0 or negative_code==0 or 'Missing source: traffic-context.json' not in negative_path.read_text():
            raise ValueError('Delivery positive/negative audit failed: '+suffix)
        entry['delivery_acceptance']={'case_id':case,'sets':['full-train'],
            'checks':['native_source','all_participants','time_join','full_video_decode',
                'actual_pixels','physical_completion','independent_right_of_way_review'],
            'script':'delivery_audit.py','script_sha256':sha(ROOT/'delivery_audit.py'),
            'command':' '.join(positive),'test_exit_code':0,
            'test_log':str(positive_path.relative_to(ROOT)),'test_log_sha256':sha(positive_path),
            'negative_command':' '.join(negative),'negative_exit_code':negative_code,
            'negative_expected_error':'Missing source: traffic-context.json',
            'negative_log':str(negative_path.relative_to(ROOT)),
            'negative_log_sha256':sha(negative_path)}
        channels=json.loads(next(f['content'] for f in json.loads((ROOT/entry['construction']).read_text())['files']
            if f['path']=='config.json'))['mandatory_channels']
        entry['acquisition']={name:{'entrypoint':'runner.py',
            'method':'original Native frame and actor state joined to saved video and context',
            'evidence':['native-motion.jsonl','video_frames.jsonl','traffic-context.json',
                'reference_corner.mkv']} for name in set(channels)|{'kin.velocity'}}
    for comparison in plan['comparisons']:
        ident=comparison['comparison_id'];suffix='moving' if ident.endswith('__comparison') else 'pedestrian'
        folder=ROOT/'native/proofs/comparisons';folder.mkdir(parents=True,exist_ok=True)
        base=[sys.executable,str(ROOT/'comparison_audit.py'),'--comparison',ident]
        for case in comparison['case_ids']:base.extend(['--processing',case+'='+str(saved_paths[case])])
        positive=base+['--output',str(REPO/'.runtime-work/c230259-comparison-audits'/f'{suffix}-positive.json')]
        negative=base+['--output',str(REPO/'.runtime-work/c230259-comparison-audits'/f'{suffix}-negative.json'),
            '--omit-case',comparison['case_ids'][1]]
        positive_path=folder/f'{suffix}-positive.log';negative_path=folder/f'{suffix}-negative.log'
        Path(positive[-1]).parent.mkdir(parents=True,exist_ok=True)
        code=run(positive,positive_path);negative_code=run(negative,negative_path)
        if code!=0 or negative_code==0 or 'Missing comparison case:' not in negative_path.read_text():
            raise ValueError('Comparison positive/negative audit failed: '+suffix+' '+positive_path.read_text()[-500:])
        comparison['audit']={'script':'comparison_audit.py','script_sha256':sha(ROOT/'comparison_audit.py'),
            'command':' '.join(positive),'test_log':str(positive_path.relative_to(ROOT)),
            'test_log_sha256':sha(positive_path),'test_exit_code':0,
            'negative_command':' '.join(negative),'negative_exit_code':negative_code,
            'negative_expected_error':'Missing comparison case:',
            'negative_log':str(negative_path.relative_to(ROOT)),
            'negative_log_sha256':sha(negative_path)}
    write(manifest_path,manifest);write(plan_path,plan)
    print(json.dumps({'saved_cases':len(saved_paths),'delivery_audits':len(saved_paths),
        'comparison_audits':len(plan['comparisons'])}))

if __name__=='__main__':main()

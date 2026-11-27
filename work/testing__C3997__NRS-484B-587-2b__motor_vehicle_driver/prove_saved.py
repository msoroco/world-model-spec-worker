"""Test recorded-only selected finalization and failure feedback for every case."""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from author_semantic import AID,HERE

ROOT=HERE.parents[1]
SCRATCH=ROOT/'.runtime-work/c3997-owner-nov27/saved-v2'
MANIFEST=HERE/'execution-manifest.proof-draft.json'
VALIDATOR=ROOT/'.runtime-work/c110969-decoder/.lake/build/bin/adapterCheck'


def digest(path):return sha256(Path(path).read_bytes()).hexdigest()


def run_command(args,log):
    env=dict(os.environ,SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH),TMPDIR=str(SCRATCH),
             PYTHONDONTWRITEBYTECODE='1')
    done=subprocess.run(args,cwd=ROOT,env=env,text=True,stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT)
    log.write_text(done.stdout.rstrip()+'\n')
    return done.returncode


def run():
    SCRATCH.mkdir(parents=True,exist_ok=True)
    manifest=json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        case=entry['case_id'];suffix=case.removeprefix(AID+'__')
        source=ROOT/'.runtime-work/c3997-owner-nov27/proofs-v6'/('compatible-'+suffix+'-primary')
        attempt=SCRATCH/('attempt-'+suffix)
        destination=SCRATCH/('processed-'+suffix)
        if attempt.exists() or destination.exists():raise ValueError('retain prior saved proof: '+suffix)
        shutil.copytree(source,attempt,ignore=shutil.ignore_patterns('converted','traffic_spec'))
        (attempt/'candidate-selection.json').unlink()
        args=[sys.executable,str(ROOT/'runtime.py'),'process-saved','--manifest',str(MANIFEST),
              '--case',case,'--attempt',str(attempt),'--output',str(destination),
              '--library',str(ROOT/'runtime/library'),'--validator',str(VALIDATOR)]
        log=HERE/('proof-saved-'+suffix+'.log')
        code=run_command(args,log)
        if code:
            raise ValueError('recorded-only saved processing failed: '+suffix+' '+log.read_text()[-1200:])
        receipt=json.loads(log.read_text())
        if not (receipt.get('passed') is True and receipt.get('recorded_only') is True and
                receipt.get('originals_preserved') is True and receipt.get('missing_evidence') is False):
            raise ValueError('saved receipt incomplete: '+suffix)
        entry['saved_replay']={'log':log.name,'sha256':digest(log)}
        entry['post_capture']={
            'command':'.venv-cpu/bin/python runtime.py process-saved --manifest work/'+AID+
                      '/execution-manifest.json --case '+case+
                      ' --attempt $ATTEMPT --output $PROCESSED --library runtime/library --validator $LEAN_VALIDATOR --owner-release-receipt $OWNER_RELEASE_RECEIPT',
            'feedback_command':'.venv-cpu/bin/python work/'+AID+'/delivery_audit.py --case '+case+
                               ' --attempt $ATTEMPT --review $PIXEL_REVIEW --physical $PHYSICAL_RESULT',
            'recorded_only':True,'test_exit_code':0,'test_log':log.name,
            'test_log_sha256':digest(log)}
        rejected=SCRATCH/('rejected-attempt-'+suffix)
        rejected_out=SCRATCH/('rejected-processed-'+suffix)
        shutil.copytree(attempt,rejected)
        (rejected/'original-history.jsonl').unlink()
        bad_args=args.copy();bad_args[bad_args.index(str(attempt))]=str(rejected)
        bad_args[bad_args.index(str(destination))]=str(rejected_out)
        negative=HERE/('proof-saved-negative-'+suffix+'.log')
        bad_code=run_command(bad_args,negative)
        if bad_code:
            # Source rejection may exit nonzero, or return an explicit missing-evidence receipt.
            if 'Missing required source: original-history.jsonl' not in negative.read_text():
                feedback=list(rejected_out.glob('v*/feedback.json'))
                if not feedback or 'original-history.jsonl' not in feedback[0].read_text():
                    raise ValueError('saved missing-source rejection absent: '+suffix)
        else:
            bad=json.loads(negative.read_text())
            if bad.get('missing_evidence') is not True:
                raise ValueError('saved missing source did not produce actionable feedback: '+suffix)
        print('saved',suffix,flush=True)
    (HERE/'execution-manifest.saved-draft.json').write_text(json.dumps(manifest,indent=2)+'\n')


if __name__=='__main__':run()

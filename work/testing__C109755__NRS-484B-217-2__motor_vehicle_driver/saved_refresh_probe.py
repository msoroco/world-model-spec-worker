"""Replay pinned saved processing from the current exact diagnostic acquisition.

The source copy stays under .runtime-work and is never a Native capture claim.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]


def digest(root):
    return {str(path.relative_to(root)):hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob('*') if path.is_file()}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--case',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    manifest=HERE/'execution-manifest.json'
    entry=next(item for item in json.loads(manifest.read_text())['cases']
               if item['case_id']==args.case)
    command=shlex.split(entry['compatibility']['command'])
    source=(REPO/command[command.index('--output')+1]).resolve()
    output=Path(args.output).resolve()
    attempt=output.with_name(output.name+'-source')
    safe=REPO/'.runtime-work'
    if (not source.is_relative_to(safe) or not output.is_relative_to(safe) or
            output.exists() or attempt.exists()):
        raise ValueError('saved probe requires fresh source/output under .runtime-work')
    shutil.copytree(source,attempt)
    selection=attempt/'candidate-selection.json'
    if selection.exists():selection.unlink()
    before=digest(attempt)
    cmd=[sys.executable,str(REPO/'runtime.py'),'process-saved',
         '--manifest',str(manifest),'--case',args.case,'--attempt',str(attempt),
         '--output',str(output),'--library',str(REPO/'runtime/library'),
         '--validator',str(REPO/'.runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck')]
    env=dict(os.environ,SCENARIO_PIPELINE_OUTPUT_ROOT=str(safe/'c109755-saved-refresh-runtime'),
             PYTHONDONTWRITEBYTECODE='1')
    result=subprocess.run(cmd,cwd=REPO,env=env,capture_output=True,text=True,timeout=300)
    if result.returncode:
        raise RuntimeError('saved processing failed: '+result.stdout[-600:]+result.stderr[-1200:])
    receipt=json.loads((output/'v0001/processing.json').read_text())
    if (digest(attempt)!=before or receipt.get('passed') is not True or
            receipt.get('originals_preserved') is not True or
            receipt.get('missing_evidence') is not False or
            receipt.get('physical_acceptance_claimed') is not False or
            not receipt.get('final_video_checks',{}).get('passed')):
        raise AssertionError('saved sources, final video or diagnostic provenance differ')
    print(json.dumps({'case_id':args.case,'recorded_only':True,
                      'originals_preserved':True,'final_video_decoded':True,
                      'physical_acceptance_claimed':False}))


if __name__=='__main__':main()

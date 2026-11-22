"""Regenerate exact C110454 compatibility and recorded-only saved CPU receipts."""
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE/'current-runtime-reproof-manifest.json'
VALIDATOR = ROOT/'.runtime-work/decoder-update015-c10316/.lake/build/bin/adapterCheck'
PROOFS = HERE/'current-runtime-selected-proof'
PROGRESS = HERE/'current-runtime-matrix-progress.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def run(command, log):
    with log.open('w') as stream:
        code = subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT).returncode
    if code:
        raise RuntimeError(f'CPU proof command failed ({code}): {log}')


def main():
    doc = read(MANIFEST)
    current = sha(ROOT/'runtime/pipeline/SOURCE-MANIFEST.json')
    if doc['runtime_manifest_sha256'] != current or not VALIDATOR.is_file():
        raise ValueError('Current runtime or Lean validator missing')
    rows=[]
    for entry in doc['cases']:
        suffix=entry['case_id'].rsplit('__',1)[-1]
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            selected=entry if candidate=='primary' else next(c for c in entry['candidates'] if c['id']==candidate)
            if sha(HERE/selected['construction']) != selected['construction_sha256']:
                raise ValueError('Selected construction changed: '+suffix+' '+candidate)
            proof=PROOFS/suffix/candidate
            proof.mkdir(parents=True,exist_ok=True)
            required=[proof/name for name in ('compatibility.json','analysis.log','negative-analysis.log','saved-processing.json','saved-analysis.log')]
            if not all(p.is_file() for p in required):
                stem=f'c110454-current-{suffix}-{candidate}-{time.time_ns()}'
                attempt=ROOT/'.runtime-work'/(stem+'-compat')
                saved=ROOT/'.runtime-work'/(stem+'-saved')
                common=['--manifest',str(MANIFEST),'--case',entry['case_id'],
                        '--library',str(ROOT/'runtime/pipeline/library'),'--validator',str(VALIDATOR)]
                compat_command=[sys.executable,str(ROOT/'runtime.py'),'compatibility',*common,
                                '--candidate',candidate,'--output',str(attempt)]
                run(compat_command,proof/'compat-command.log')
                run([sys.executable,str(ROOT/'runtime.py'),'process-saved',*common,
                     '--attempt',str(attempt),'--output',str(saved)],proof/'saved-command.log')
                for source,target in ((attempt/'compatibility.json',required[0]),
                                      (attempt/'compatibility-analysis.log',required[1]),
                                      (attempt/'negative-analysis.log',required[2]),
                                      (saved/'v0001/processing.json',required[3]),
                                      (saved/'v0001/analysis.log',required[4])):
                    shutil.copyfile(source,target)
            compat=read(required[0]);processing=read(required[3])
            if (not compat['passed'] or compat['runtime_manifest_sha256']!=current or
                    compat['construction_sha256']!=selected['construction_sha256'] or
                    compat['case_id']!=entry['case_id'] or compat['candidate_id']!=candidate or
                    compat.get('negative_error_contains') not in required[2].read_text() or
                    not processing['passed'] or not processing['recorded_only'] or
                    processing['missing_evidence'] or not processing['originals_preserved'] or
                    processing['case_id']!=entry['case_id'] or processing['candidate_id']!=candidate or
                    processing['native_revision']['construction_sha256']!=selected['construction_sha256']):
                raise ValueError('Current-runtime receipt binding differs: '+suffix+' '+candidate)
            if any(path.stat().st_size>2*1024*1024 for path in required):
                raise ValueError('Oversized return receipt: '+suffix+' '+candidate)
            rows.append({'case_id':entry['case_id'],'candidate_id':candidate,
                         'construction_sha256':selected['construction_sha256'],
                         'proof_dir':str(proof.relative_to(HERE)),
                         'compatibility_sha256':sha(required[0]),'saved_sha256':sha(required[3])})
            PROGRESS.write_text(json.dumps({'format':'c110454-current-runtime-matrix-v1',
                'runtime_manifest_sha256':current,'manifest_sha256':sha(MANIFEST),
                'completed':len(rows),'required':36,'rows':rows},indent=2)+'\n')
            print(suffix,candidate,'compatibility and saved passed',flush=True)
    print('total',len(rows))


if __name__=='__main__':
    main()

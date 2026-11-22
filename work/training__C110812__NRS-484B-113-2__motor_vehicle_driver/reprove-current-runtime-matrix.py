"""Regenerate selected positive/negative compatibility and saved CPU proofs.

Every completed candidate has its own returned receipt, allowing safe resume.
The receipt binds the current runtime and the unchanged selected construction.
"""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT/'runtime/pipeline'), str(ROOT/'runtime/pipeline/scenario_pipeline')]
from scenario_pipeline.worker_exchange.fixture_recipe import materialize
from scenario_pipeline.worker_exchange.package_compatibility import materialize_case
from scenario_pipeline.worker_exchange.saved_processing import run

MANIFEST = HERE/'current-runtime-reproof-manifest.json'
VALIDATOR = ROOT/'.runtime-work/c110812-current-decoder/.lake/build/bin/adapterCheck'
PROGRESS = HERE/'current-runtime-matrix-progress.json'
CANDIDATES = ('primary','fallback1','fallback2','fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def save(path, value):
    path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')


def proof_row(entry, candidate, document):
    suffix = entry['case_id'].rsplit('__',1)[-1]
    chosen = entry if candidate == 'primary' else next(c for c in entry['candidates'] if c['id']==candidate)
    if sha(HERE/chosen['construction']) != chosen['construction_sha256']:
        raise ValueError('Selected construction changed: '+suffix+' '+candidate)
    stem = 'current-runtime-'+suffix+'-'+candidate
    compat_receipt = HERE/(stem+'-compatibility.json')
    negative_log = HERE/(stem+'-negative.log')
    analysis_log = HERE/(stem+'-analysis.log')
    compat_command_log = HERE/(stem+'-compat-command.log')
    saved_receipt = HERE/(stem+'-saved-receipt.json')
    saved_log = HERE/(stem+'-saved-command.log')
    if not (compat_receipt.is_file() and negative_log.is_file() and analysis_log.is_file()):
        output = ROOT/'.runtime-work'/('c110812-'+stem+'-compat')
        command = [sys.executable,str(ROOT/'runtime.py'),'compatibility',
                   '--manifest',str(MANIFEST),'--case',entry['case_id'],
                   '--candidate',candidate,'--output',str(output),
                   '--library',str(ROOT/'runtime/pipeline/library'),
                   '--validator',str(VALIDATOR)]
        with compat_command_log.open('w') as log:
            exit_code = subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT).returncode
        if exit_code:
            raise RuntimeError('Compatibility failed: '+str(compat_command_log))
        for source,target in (('compatibility.json',compat_receipt),
                              ('negative-analysis.log',negative_log),
                              ('compatibility-analysis.log',analysis_log)):
            shutil.copyfile(output/source,target)
    compatibility = read(compat_receipt)
    if (not compatibility['passed'] or
            compatibility['runtime_manifest_sha256'] != document['runtime_manifest_sha256'] or
            compatibility['construction_sha256'] != chosen['construction_sha256'] or
            'Missing required source: native_samples.jsonl' not in negative_log.read_text()):
        raise ValueError('Compatibility or negative binding failed: '+stem)
    if not saved_receipt.is_file():
        output = ROOT/'.runtime-work'/('c110812-'+stem+'-saved')
        output.mkdir(parents=True,exist_ok=True)
        with saved_log.open('w') as log:
            try:
                source = materialize(ROOT,ROOT/entry['fixture_recipe'],output/'fixture')
                materialize_case(MANIFEST,entry['case_id'],output/'attempt',output/'fixture',candidate)
                result = run(MANIFEST,entry['case_id'],output/'attempt',output/'output',
                             ROOT/'runtime/pipeline/library',VALIDATOR)
                if not result.get('passed') or not result.get('recorded_only') or result.get('missing_evidence'):
                    raise ValueError('Recorded-only saved processing failed')
                save(saved_receipt,{'source':source,'result':result})
                log.write('recorded-only saved processing passed\n')
            except Exception as error:
                log.write(repr(error)+'\n')
                raise
    saved = read(saved_receipt)['result']
    if (not saved['passed'] or not saved['recorded_only'] or
            saved['analysis_revision']['runtime_manifest_sha256'] != document['runtime_manifest_sha256'] or
            saved['analysis_revision']['construction_sha256'] != chosen['construction_sha256']):
        raise ValueError('Saved processing binding failed: '+stem)
    return {'case_id':entry['case_id'],'candidate_id':candidate,
            'construction_sha256':chosen['construction_sha256'],
            'compatibility_receipt':compat_receipt.name,'compatibility_sha256':sha(compat_receipt),
            'analysis_log':analysis_log.name,'analysis_sha256':sha(analysis_log),
            'negative_log':negative_log.name,'negative_sha256':sha(negative_log),
            'saved_receipt':saved_receipt.name,'saved_sha256':sha(saved_receipt)}


def main():
    document=read(MANIFEST)
    current=sha(ROOT/'runtime/pipeline/SOURCE-MANIFEST.json')
    if document['runtime_manifest_sha256'] != current or not VALIDATOR.is_file():
        raise ValueError('Current runtime or Lean adapter missing')
    rows=[]
    for entry in document['cases']:
        for candidate in CANDIDATES:
            row=proof_row(entry,candidate,document)
            rows.append(row)
            save(PROGRESS,{'format':'c110812-current-runtime-matrix-progress-v1',
                           'runtime_manifest_sha256':current,'manifest_sha256':sha(MANIFEST),
                           'completed':len(rows),'required':len(document['cases'])*len(CANDIDATES),
                           'rows':rows})
            print(entry['case_id'].rsplit('__',1)[-1],candidate,'compatibility and saved passed',flush=True)
    return len(rows)


if __name__=='__main__':
    print('total',main())

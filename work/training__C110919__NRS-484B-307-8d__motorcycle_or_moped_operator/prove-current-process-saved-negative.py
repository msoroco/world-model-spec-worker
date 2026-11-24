"""Reject a missing original road-geometry source in current process-saved."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
POSITIVE=HERE/'native/current-process-saved-proof.json'
MANIFEST=HERE/'saved-diagnostic-manifest.json'
CASE='training__C110919__NRS-484B-307-8d__motorcycle_or_moped_operator__selected_109a5dbc__condition_a'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    positive=json.loads(POSITIVE.read_text())
    if not positive['passed'] or positive['manifest_sha256']!=sha(MANIFEST):
        raise ValueError('Current positive saved proof changed')
    source=Path(positive['source']['attempt'])
    if not source.is_dir() or not (source/'road_geometry.json').is_file():
        raise ValueError('Positive acquisition no longer retained')
    scratch=Path(tempfile.mkdtemp(prefix='c110919-process-saved-negative-',
                                  dir=ROOT/'.runtime-work'))
    attempt=scratch/'attempt'
    shutil.copytree(source,attempt)
    (attempt/'road_geometry.json').unlink()
    output=scratch/'processed'
    command=[sys.executable,str(ROOT/'runtime.py'),'process-saved',
             '--manifest',str(MANIFEST),'--case',CASE,'--attempt',str(attempt),
             '--output',str(output),'--library',str(ROOT/'runtime/pipeline/library'),
             '--validator',str(ROOT/'.runtime-work/c104538-decoder/.lake/build/bin/adapterCheck')]
    run=subprocess.run(command,text=True,stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT,timeout=1800)
    log=HERE/'native/current-process-saved-negative-command.log'
    log.write_text(run.stdout)
    if run.returncode:
        raise RuntimeError('Saved missing-source path failed without classified feedback')
    receipt=json.loads(run.stdout)
    feedback=json.loads((Path(receipt['version'])/'feedback.json').read_text())
    analysis_log=Path(receipt['version'])/'analysis.log'
    if (not receipt['passed'] or receipt['missing_evidence'] is not True or
            feedback.get('classification')!='incomplete_or_unavailable_law_evidence' or
            'Missing required source: road_geometry.json' not in analysis_log.read_text() or
            not receipt['originals_preserved'] or feedback['native_replay_requested']):
        raise ValueError('Missing source was not reported correctly')
    result={'format':'c110919-current-process-saved-negative-v1',
            'passed':True,'positive_proof_sha256':sha(POSITIVE),
            'manifest_sha256':sha(MANIFEST),
            'missing_source':'road_geometry.json',
            'classification':feedback['classification'],
            'processing_receipt':receipt,
            'analysis_log_sha256':sha(analysis_log),
            'command_log_sha256':sha(log),
            'original_native_observed':False,'selected_delivery':False,
            'physical_acceptance_claimed':False}
    target=HERE/'native/current-process-saved-negative-proof.json'
    target.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'passed':True,'proof_sha256':sha(target),
                      'classification':feedback['classification']}))


if __name__=='__main__':
    main()

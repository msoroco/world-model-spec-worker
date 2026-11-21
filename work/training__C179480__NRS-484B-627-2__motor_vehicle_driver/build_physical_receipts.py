"""Bind current C179480 primary constructions to CPU physical fixture proofs."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
KINDS = ('complete_motion','incomplete_motion','missing_evidence')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def build():
    manifest = json.loads((HERE/'candidate-matrix-manifest.json').read_text())
    lifecycle_log = HERE/'update160-lifecycle.log'
    lifecycle = json.loads(lifecycle_log.read_text())
    if lifecycle['events'] != [
            'capture_finished','encoders_closed','restoration_verified',
            'native_exit','owner_released','saved_processing_started']:
        raise ValueError('Synthetic capture lifecycle did not close in order')
    out = HERE/'physical-diagnostic-fixtures'
    out.mkdir(exist_ok=True)
    receipts = []
    for entry in manifest['cases']:
        case = entry['case_id'].split('__')[-1]
        if sha(HERE/entry['construction']) != entry['construction_sha256']:
            raise ValueError('Current primary construction hash differs: '+case)
        fixtures = []
        for kind in KINDS:
            result = out/(case+'-'+kind+'.json')
            log = out/(case+'-'+kind+'.log')
            command = [sys.executable,str(HERE/'physical_diagnostic.py'),
                       '--case',case,'--kind',kind,'--output',str(result)]
            with log.open('w') as stream:
                completed = subprocess.run(command, cwd=REPO, stdout=stream,
                                           stderr=subprocess.STDOUT, check=False)
            if completed.returncode:
                raise ValueError('CPU physical fixture failed: '+case+' '+kind)
            fixtures.append({'kind':kind, 'command':' '.join(command),
                             'exit_code':completed.returncode,
                             'log':str(log.relative_to(HERE)),
                             'log_sha256':sha(log),
                             'result':str(result.relative_to(HERE)),
                             'result_sha256':sha(result)})
        receipt = {
            'format':'c179480-physical-preparation-cpu-v1',
            'case_id':entry['case_id'],
            'construction_sha256':entry['construction_sha256'],
            'fixtures':fixtures,
            'lifecycle':{'events':lifecycle['events'], 'exit_code':0,
                         'log':str(lifecycle_log.relative_to(HERE)),
                         'log_sha256':sha(lifecycle_log)},
            'scope':'synthetic physical-stop and fake-world lifecycle only',
            'actual_native_or_legal_acceptance_claimed':False,
        }
        path=HERE/('update160-'+case+'-physical-receipt.json')
        write(path,receipt)
        receipts.append({'case_id':entry['case_id'],
                         'receipt':str(path.relative_to(HERE)),
                         'sha256':sha(path),
                         'construction_sha256':entry['construction_sha256']})
    write(HERE/'update160-physical-receipts-index.json',
          {'format':'c179480-physical-receipts-index-v1','receipts':receipts,
           'selected_delivery_manifest_bound':False})
    return receipts


if __name__=='__main__':
    print(json.dumps({'cases':len(build())}))

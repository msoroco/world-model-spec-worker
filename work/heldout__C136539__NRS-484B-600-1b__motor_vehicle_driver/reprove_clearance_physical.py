"""Exercise and bind three synthetic physical outcomes and closure per case."""

from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


manifest = json.loads(MANIFEST.read_text())
index = {'format': 'worker-exposure-physical-preparation-cpu-proofs',
         'scope': 'synthetic Native-shaped CPU fixtures only; no CARLA physical or legal outcome',
         'probe_script': 'physical_probe.py',
         'probe_script_sha256': sha(HERE / 'physical_probe.py'), 'cases': []}
for entry in manifest['cases']:
    case = entry['case_id']; suffix = case.split('__')[-1]
    fixtures = []
    life = None
    for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence', 'lifecycle'):
        output = ROOT / '.runtime-work' / f'c136539-{suffix}-physical-{kind}-sweep-{uuid4().hex[:8]}'
        command = [sys.executable, str(HERE / 'physical_probe.py'),
                   '--case', case, '--kind', kind, '--output', str(output)]
        process = subprocess.run(command, cwd=ROOT,
                                 env={**os.environ, 'PYTHONPATH': str(ROOT / 'runtime/scenario_pipeline')},
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True)
        log_rel = f'physical/{suffix}-{kind}.log' if kind != 'lifecycle' else f'physical/{suffix}-lifecycle.log'
        (HERE / log_rel).write_text(process.stdout)
        if process.returncode:
            raise ValueError(f'{suffix} {kind} physical fixture failed: {process.stdout[-900:]}')
        if kind == 'lifecycle':
            observed = json.loads(process.stdout)
            life = {'events': observed['events'],
                    'command': f'.venv-cpu/bin/python work/{HERE.name}/physical_probe.py --case {case} --kind lifecycle --output $OUTPUT',
                    'exit_code': 0, 'log': log_rel, 'log_sha256': sha(HERE / log_rel),
                    'premature_seal_rejected': observed['premature_seal_rejected']}
        else:
            result_rel = f'physical/{suffix}-{kind}-result.json'
            fixtures.append({'kind': kind,
                             'command': f'.venv-cpu/bin/python work/{HERE.name}/physical_probe.py --case {case} --kind {kind} --output $OUTPUT',
                             'exit_code': 0, 'log': log_rel, 'log_sha256': sha(HERE / log_rel),
                             'result': result_rel, 'result_sha256': sha(HERE / result_rel)})
    receipt_rel = f'physical/{suffix}-proof.json'
    receipt = {'format': 'worker-physical-preparation-proof', 'case_id': case,
               'construction_sha256': entry['construction_sha256'],
               'fixture_scope': 'synthetic CPU source protocol, not actual motion',
               'fixtures': fixtures, 'lifecycle': life}
    (HERE / receipt_rel).write_text(json.dumps(receipt, indent=2) + '\n')
    entry['physical_preparation'] = {'receipt': receipt_rel, 'sha256': sha(HERE / receipt_rel)}
    index['cases'].append({'case_id': case, 'receipt': receipt_rel,
                           'sha256': sha(HERE / receipt_rel)})
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    print(suffix, 'physical fixture protocols passed', flush=True)
(HERE / 'physical-preparation-proofs.json').write_text(json.dumps(index, indent=2) + '\n')

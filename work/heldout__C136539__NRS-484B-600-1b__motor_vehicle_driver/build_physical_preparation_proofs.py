"""Bind current synthetic physical outcome and lifecycle CPU receipts."""

import hashlib
import json
from pathlib import Path


root = Path(__file__).resolve().parent
manifest = json.loads((root / 'probe-compatibility-manifest.json').read_text())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
index = {'format': 'worker-exposure-physical-preparation-cpu-proofs',
         'scope': 'synthetic Native-shaped CPU fixtures only; no CARLA physical or legal outcome',
         'probe_script': 'physical_probe.py',
         'probe_script_sha256': sha(root / 'physical_probe.py'),
         'cases': []}
for entry in manifest['cases']:
    suffix = entry['case_id'].split('__')[-1]
    receipt = {'format': 'worker-physical-preparation-proof',
               'case_id': entry['case_id'],
               'construction_sha256': sha(root / entry['construction']),
               'fixture_scope': 'synthetic CPU source protocol, not actual motion',
               'fixtures': []}
    for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        log = f'physical/{suffix}-{kind}.log'
        result = f'physical/{suffix}-{kind}-result.json'
        receipt['fixtures'].append({
            'kind': kind,
            'command': f'PYTHONPATH=runtime/scenario_pipeline .venv-cpu/bin/python work/{root.name}/physical_probe.py --case {entry["case_id"]} --kind {kind} --output .runtime-work/c136539-{suffix}-physical-{kind}-a',
            'exit_code': 0, 'log': log, 'log_sha256': sha(root / log),
            'result': result, 'result_sha256': sha(root / result)})
    life_log = f'physical/{suffix}-lifecycle.log'
    life = json.loads((root / life_log).read_text())
    receipt['lifecycle'] = {
        'events': life['events'],
        'command': f'PYTHONPATH=runtime/scenario_pipeline .venv-cpu/bin/python work/{root.name}/physical_probe.py --case {entry["case_id"]} --kind lifecycle --output .runtime-work/c136539-{suffix}-physical-lifecycle-a',
        'exit_code': 0, 'log': life_log, 'log_sha256': sha(root / life_log),
        'premature_seal_rejected': life['premature_seal_rejected']}
    path = root / f'physical/{suffix}-proof.json'
    path.write_text(json.dumps(receipt, indent=2) + '\n')
    index['cases'].append({'case_id': entry['case_id'],
                           'receipt': str(path.relative_to(root)), 'sha256': sha(path)})
(root / 'physical-preparation-proofs.json').write_text(json.dumps(index, indent=2) + '\n')

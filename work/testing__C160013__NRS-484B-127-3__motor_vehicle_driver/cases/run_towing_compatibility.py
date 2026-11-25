"""Run current-runtime towing compatibility in an isolated diagnostic manifest."""
import hashlib
import json
import shutil
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
STAGE = REPO / '.runtime-work/c160013-towing-compat-manifest'
OUTPUT = REPO / '.runtime-work/c160013-towing-compat-v1'


def main():
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    manifest = json.loads((PACKAGE / 'towing-diagnostic-manifest.json').read_text())
    entry = manifest['cases'][0]
    construction = PACKAGE / entry['construction']
    shutil.copyfile(construction, STAGE / construction.name)
    entry['construction'] = construction.name
    (STAGE / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    plan = json.loads((PACKAGE / 'case-plan.json').read_text())
    for disposition in plan['requirement_dispositions']:
        if disposition['status'] == 'selected_required':
            disposition.setdefault('case_ids', []).append(entry['case_id'])
    (STAGE / 'case-plan.json').write_text(json.dumps(plan, indent=2) + '\n')
    contract = json.loads((PACKAGE / 'measurement-contract.json').read_text())
    gap = next(row for row in contract['requirements'] if row['output_key'] == 'caravan_gap')
    gap['inputs'].append('towing-relationship.json')
    (STAGE / 'measurement-contract.json').write_text(json.dumps(contract, indent=2) + '\n')
    proposals = STAGE / 'proposals'
    proposals.mkdir()
    cases = json.loads((PACKAGE / 'proposals/cases.json').read_text())
    wide = next(case for case in cases['cases'] if case['case_id'].endswith('__entrant_can_occupy_gap'))
    tow = deepcopy(wide)
    tow['case_id'] = entry['case_id']
    tow['rationale'] = 'Diagnostic full drawing-and-drawn gap occupancy; legal judgment unresolved.'
    tow['recording_description'] = json.loads(construction.read_text())['recording_description']
    cases['cases'].append(tow)
    (proposals / 'cases.json').write_text(json.dumps(cases, indent=2) + '\n')
    validator = REPO / '.runtime-work/c215286-current-decoder/.lake/build/bin/adapterCheck'
    if not validator.is_file():
        raise ValueError('Pinned current-runtime decoder required')
    command = [sys.executable, str(REPO / 'runtime.py'), 'compatibility',
               '--manifest', str(STAGE / 'manifest.json'), '--case', entry['case_id'],
               '--candidate', 'primary', '--output', str(OUTPUT),
               '--library', str(REPO / 'runtime/library'), '--validator', str(validator)]
    log = PACKAGE / 'cases/towing-compatibility-command.log'
    with log.open('w') as stream:
        result = subprocess.run(command, cwd=REPO, stdout=stream,
                                stderr=subprocess.STDOUT, check=False)
    if result.returncode:
        raise RuntimeError('Towing diagnostic compatibility failed: ' + log.read_text()[-1800:])
    receipt = json.loads((OUTPUT / 'compatibility.json').read_text())
    if receipt.get('passed') is not True or receipt.get('case_id') != entry['case_id']:
        raise ValueError('Exact towing compatibility receipt required')
    for name, target in (('compatibility.json', 'towing-compatibility.json'),
                         ('compatibility-analysis.log', 'towing-compatibility-analysis.log'),
                         ('negative-analysis.log', 'towing-compatibility-negative.log')):
        shutil.copyfile(OUTPUT / name, PACKAGE / 'cases' / target)
    print(json.dumps({'case_id': entry['case_id'], 'passed': True,
                      'construction_sha256': entry['construction_sha256'],
                      'receipt_sha256': hashlib.sha256((PACKAGE / 'cases/towing-compatibility.json').read_bytes()).hexdigest(),
                      'negative_source_rejected': True}, sort_keys=True))


if __name__ == '__main__':
    main()

"""Run current-runtime towing compatibility in an isolated diagnostic manifest."""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate', choices=('primary', 'fallback1'), default='primary')
    args = parser.parse_args()
    label = 'towing' if args.candidate == 'primary' else 'towing-fallback1'
    stage = REPO / ('.runtime-work/c160013-' + label + '-compat-manifest')
    output = REPO / ('.runtime-work/c160013-' + label + '-compat-v1')
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    if output.exists():
        shutil.rmtree(output)
    manifest = json.loads((PACKAGE / 'towing-diagnostic-manifest.json').read_text())
    entry = manifest['cases'][0]
    construction = PACKAGE / entry['construction']
    shutil.copyfile(construction, stage / construction.name)
    entry['construction'] = construction.name
    for candidate in entry.get('candidates', []):
        source = PACKAGE / candidate['construction']
        shutil.copyfile(source, stage / source.name)
        candidate['construction'] = source.name
    (stage / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    plan = json.loads((PACKAGE / 'case-plan.json').read_text())
    for disposition in plan['requirement_dispositions']:
        if disposition['status'] == 'selected_required':
            disposition.setdefault('case_ids', []).append(entry['case_id'])
    (stage / 'case-plan.json').write_text(json.dumps(plan, indent=2) + '\n')
    contract = json.loads((PACKAGE / 'measurement-contract.json').read_text())
    gap = next(row for row in contract['requirements'] if row['output_key'] == 'caravan_gap')
    gap['inputs'].append('towing-relationship.json')
    (stage / 'measurement-contract.json').write_text(json.dumps(contract, indent=2) + '\n')
    proposals = stage / 'proposals'
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
               '--manifest', str(stage / 'manifest.json'), '--case', entry['case_id'],
               '--candidate', args.candidate, '--output', str(output),
               '--library', str(REPO / 'runtime/library'), '--validator', str(validator)]
    log = PACKAGE / ('cases/' + label + '-compatibility-command.log')
    with log.open('w') as stream:
        result = subprocess.run(command, cwd=REPO, stdout=stream,
                                stderr=subprocess.STDOUT, check=False)
    if result.returncode:
        raise RuntimeError('Towing diagnostic compatibility failed: ' + log.read_text()[-1800:])
    receipt = json.loads((output / 'compatibility.json').read_text())
    if (receipt.get('passed') is not True or receipt.get('case_id') != entry['case_id']
            or receipt.get('candidate_id') != args.candidate):
        raise ValueError('Exact towing compatibility receipt required')
    for name, target in (('compatibility.json', label + '-compatibility.json'),
                         ('compatibility-analysis.log', label + '-compatibility-analysis.log'),
                         ('negative-analysis.log', label + '-compatibility-negative.log')):
        shutil.copyfile(output / name, PACKAGE / 'cases' / target)
    print(json.dumps({'case_id': entry['case_id'], 'passed': True,
                      'candidate_id': args.candidate,
                      'construction_sha256': receipt['construction_sha256'],
                      'receipt_sha256': hashlib.sha256((PACKAGE / 'cases' / (label + '-compatibility.json')).read_bytes()).hexdigest(),
                      'negative_source_rejected': True}, sort_keys=True))


if __name__ == '__main__':
    main()

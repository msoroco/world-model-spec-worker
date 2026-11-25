"""Run one exact towing sweep candidate through current-runtime compatibility."""
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
    parser.add_argument('--index', type=int, choices=(0, 1, 2), required=True)
    parser.add_argument('--candidate', choices=('primary', 'fallback1'), required=True)
    args = parser.parse_args()
    label = f'qualified-towing-sweep-{args.index}-{args.candidate}'
    stage = REPO / ('.runtime-work/c160013-' + label + '-compat-manifest')
    output = REPO / ('.runtime-work/c160013-' + label + '-compat-v1')
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    if output.exists():
        shutil.rmtree(output)
    manifest = json.loads((PACKAGE / 'qualified-towing-sweep-manifest.json').read_text())
    entry = manifest['cases'][args.index]
    manifest['cases'] = [entry]
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
    sweep = deepcopy(wide)
    sweep['case_id'] = entry['case_id']
    sweep['rationale'] = 'Diagnostic towed physical spacing sample; statutory danger unresolved.'
    sweep['recording_description'] = json.loads(construction.read_text())['recording_description']
    sweep['variable_assignments']['caravan_spacing_target']['value'] = (3, 10, 6.5)[args.index]
    sweep['probe']['target_value_or_branch'] = (3, 10, 6.5)[args.index]
    cases['cases'].append(sweep)
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
        raise RuntimeError('Exact sweep compatibility failed: ' + log.read_text()[-1800:])
    receipt = json.loads((output / 'compatibility.json').read_text())
    if (receipt.get('passed') is not True or receipt.get('case_id') != entry['case_id']
            or receipt.get('candidate_id') != args.candidate):
        raise ValueError('Exact sweep compatibility receipt required')
    for name, target in (('compatibility.json', label + '-compatibility.json'),
                         ('compatibility-analysis.log', label + '-compatibility-analysis.log'),
                         ('negative-analysis.log', label + '-compatibility-negative.log')):
        shutil.copyfile(output / name, PACKAGE / 'cases' / target)
    print(json.dumps({'case_id': entry['case_id'], 'passed': True,
                      'candidate_id': args.candidate,
                      'construction_sha256': receipt['construction_sha256'],
                      'receipt_sha256': hashlib.sha256(
                          (PACKAGE / 'cases' / (label + '-compatibility.json')).read_bytes()).hexdigest(),
                      'negative_source_rejected': True}, sort_keys=True))


if __name__ == '__main__':
    main()

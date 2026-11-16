"""Prove staged sweep case, restoring the canonical selected plans afterward."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name + '__conditions_gap_120m'
MANIFEST = HERE/'sweep-stage-manifest.json'
PLAN = HERE/'case-plan.json'
PROPOSAL = HERE/'proposals/cases.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    plan_bytes, proposal_bytes = PLAN.read_bytes(), PROPOSAL.read_bytes()
    plan = json.loads(plan_bytes)
    proposal = json.loads(proposal_bytes)
    if CASE in {c['case_id'] for c in plan['cases']}:
        raise ValueError('Staged case already selected; use canonical proof instead')
    template = next(c for c in plan['cases'] if c['case_id'].endswith('__gap_below_500ft'))
    staged = deepcopy(template)
    staged['case_id'] = CASE
    staged['purpose'] = '120 m physical gap coverage point for conditions-permitting review; no legal cutoff'
    plan['cases'].append(staged)
    for disposition in plan['requirement_dispositions'][:3]:
        disposition['case_ids'].append(CASE)
    template = next(c for c in proposal['cases'] if c['case_id'].endswith('__gap_below_500ft'))
    staged = deepcopy(template)
    staged['case_id'] = CASE
    staged['target_type'] = 'judgment_sweep'
    staged['rationale'] = 'Source-bound 120 m engineering gap sample; legal conditions-permitting judgment unresolved.'
    staged['paired_probe_id'] = 'truck_follow_qualitative_review'
    staged['deliberate_differences'] = ['requested_body_gap_m']
    staged['variable_assignments']['requested_body_gap_m']['value'] = 120.0
    staged['probe'] = {'primary_variable': 'longitudinal_body_gap',
                       'comparison_or_standard': 'physical coverage; legal judgment unresolved',
                       'target_value_or_branch': 120.0}
    proposal['cases'].append(staged)
    PLAN.write_text(json.dumps(plan, indent=2) + '\n')
    PROPOSAL.write_text(json.dumps(proposal, indent=2) + '\n')
    logs = []
    try:
        commands = []
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            tag = '' if candidate == 'primary' else '-'+candidate
            option = [] if candidate == 'primary' else ['--candidate', candidate]
            compat = ROOT/'.runtime-work'/('c149237-conditions-gap-120m'+tag+'-compat-v4')
            saved = ROOT/'.runtime-work'/('c149237-conditions-gap-120m'+tag+'-saved-v4')
            common = ['--manifest', str(MANIFEST), '--case', CASE]
            decoder = ['--library', str(ROOT/'runtime/library'),
                       '--validator', str(ROOT/'.runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck')]
            commands.append((candidate+'-compat',
                [sys.executable, str(ROOT/'runtime.py'), 'compatibility', *common,
                 *option, '--output', str(compat), *decoder]))
            commands.append((candidate+'-saved',
                [sys.executable, str(ROOT/'runtime.py'), 'process-saved', *common,
                 '--attempt', str(compat), '--output', str(saved), *decoder]))
        for name, command in commands:
            log = HERE/('sweep-stage-'+name+'.log')
            with log.open('w') as stream:
                run = subprocess.run(command, cwd=ROOT, stdout=stream,
                                     stderr=subprocess.STDOUT, timeout=600)
            logs.append({'name': name, 'command': command, 'exit_code': run.returncode,
                         'log': log.name, 'sha256': sha(log)})
            if run.returncode:
                raise ValueError(name + ' staged proof failed; see ' + str(log))
    finally:
        PLAN.write_bytes(plan_bytes)
        PROPOSAL.write_bytes(proposal_bytes)
    if PLAN.read_bytes() != plan_bytes or PROPOSAL.read_bytes() != proposal_bytes:
        raise ValueError('Canonical plan/proposal restoration failed')
    print(json.dumps({'case_id': CASE, 'construction_sha256': json.loads(MANIFEST.read_text())['cases'][0]['construction_sha256'],
                      'fixture_recipe_sha256': sha(HERE/'fixture-recipe-conditions_gap_120m.json'),
                      'canonical_plan_restored': True, 'proofs': logs}, indent=2))


if __name__ == '__main__':
    main()

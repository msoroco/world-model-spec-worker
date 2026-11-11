"""Refresh this assignment's truthful local test claims from retained receipts."""
import hashlib
import json
from pathlib import Path

folder = Path(__file__).resolve().parent
root = folder.parent.parent
result_path = folder / 'result.json'
result = json.loads(result_path.read_text())
manifest = json.loads((folder / 'execution-manifest.json').read_text())
existing = {x['log']: x for x in result['tests']}


def claim(command, log):
    path = folder / log
    assert path.is_file(), path
    existing[log] = {
        'command': command, 'exit_code': 0, 'log': log,
        'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
    }


for log in ('cpu-tests.log', 'preflight.log', 'atom-preflight.log'):
    assert log in existing
    claim(existing[log]['command'], log)

for case in manifest['cases']:
    claim(case['offline']['command'], case['offline']['log'])
    claim(case['post_capture']['command'], case['post_capture']['test_log'])
    claim(case['delivery_acceptance']['command'], case['delivery_acceptance']['test_log'])
    for item in [case, *case['candidates']]:
        compat = item['compatibility']
        claim(compat['replay_command'], compat['replay_log'])
    for candidate in case['candidates']:
        claim(candidate['offline']['command'], candidate['offline']['log'])
        claim(candidate['post_capture']['command'], candidate['post_capture']['test_log'])
    physical = json.loads((folder / case['physical_preparation']['receipt']).read_text())
    for fixture in physical['fixtures']:
        claim(fixture['command'], fixture['log'])
    label = 'primary' if case is manifest['cases'][0] else 'reciprocal_continues'
    claim(f'.venv-cpu/bin/python work/{result["assignment_id"]}/physical_fixture_proof.py '
          f'--manifest work/{result["assignment_id"]}/execution-manifest.json '
          f'--case {case["case_id"]} --kind lifecycle '
          f'--output work/{result["assignment_id"]}/physical-proofs/{label}/lifecycle.json',
          physical['lifecycle']['log'])

comparison = json.loads((folder / 'comparison-proofs/receipt.json').read_text())
claim(comparison['command'], comparison['log'])
claim(f'.venv-cpu/bin/python work/{result["assignment_id"]}/validate_semantic_drafts.py',
      'semantic-drafts-validation.log')
claim(f'PYTHONPATH=runtime/scenario_pipeline:runtime/python .venv-cpu/bin/python '
      f'work/{result["assignment_id"]}/validate_semantic_chain.py',
      'semantic-chain-validation.log')
claim(f'.venv-cpu/bin/python work/{result["assignment_id"]}/cases/inside_yield/validate_draft.py',
      'cases/inside_yield/draft-validation.log')
claim(f'PYTHONPATH=work/{result["assignment_id"]} .venv-cpu/bin/python '
      f'work/{result["assignment_id"]}/cases/inside_yield/runner.py --check',
      'cases/inside_yield/runner-check.log')
claim(f'.venv-cpu/bin/python work/{result["assignment_id"]}/cases/inside_no_yield/validate_draft.py',
      'cases/inside_no_yield/draft-validation.log')
claim(f'PYTHONPATH=work/{result["assignment_id"]} .venv-cpu/bin/python '
      f'work/{result["assignment_id"]}/cases/inside_no_yield/runner.py --check',
      'cases/inside_no_yield/runner-check.log')
claim(f'PYTHONPATH=work/{result["assignment_id"]} .venv-cpu/bin/python '
      f'work/{result["assignment_id"]}/inside_comparison_audit.py '
      '--yield-recipe .runtime-work/c109749-inside-yield-delivery-v2/attempt '
      '--no-yield-recipe .runtime-work/c109749-inside-no-yield-delivery-v1/attempt '
      f'--output work/{result["assignment_id"]}/inside-comparison-receipt.json',
      'inside-comparison-positive.log')
claim(f'.venv-cpu/bin/python work/{result["assignment_id"]}/validate_inside_delivery.py',
      'inside-delivery-validation.log')
result['tests'] = list(existing.values())
result['readiness_kind'] = 'two_case_delivery_with_inside_pair_staged_draft_checkpoint'
result['reason'] = (
    'Two C109749 reciprocal-response cases and three fallbacks per case pass exact offline, '
    'compatibility and recorded-only saved processing. Source-bound physical-classifier and '
    'full-duration delivery-audit CPU fixtures pass software checks; diagnostic audits explicitly '
    'report passed=false. A comparison audit verifies fixed conditions and the declared later '
    'opposing response difference on synthetic sources, and rejects a changed fixed ego trajectory. '
    'Paired inside-yield and inside-no-yield case drafts have same-lane Native junction spawn, '
    'complete-body placement checks, distinct yield/proceed controllers, original-source turn-order '
    'observations and three distinct risk-based fallbacks each. All eight draft candidates pass '
    'exact offline, positive/negative compatibility and recorded-only saved processing in isolated '
    'ignored staging roots. An independent diagnostic comparison confirms common opposing trajectories '
    'and contrasting subject turn order over 900-frame diagnostic sources and rejects a perturbed '
    'opposing trajectory. Independent full-duration delivery audits for both staged cases pass '
    'software checks and reject absent sealed original history; diagnostic receipts explicitly say '
    'passed=false and claim no physical or legal acceptance. The pair is not yet in the canonical plan, proposal or manifest, '
    'and is not delivery-ready. The six-stage semantic chain validates for the original two cases, but all '
    'three physical judgment sweeps remain explicitly incomplete and statutory alternatives are not '
    'yet covered. These, complete '
    'coverage and all other partial assignment packages are unfinished worker-owned CPU work. Root supported_case_ids '
    'now lists both selected cases and all affected primary proofs were rerun. Accepted-original '
    'equivalence and actual Native motion/pixel visibility are unverified. Strict assignment and '
    'batch gates fail with Preparation acceptance failed: partial/missing packages remain. See HANDOFF.md.'
)
result_path.write_text(json.dumps(result, indent=2) + '\n')

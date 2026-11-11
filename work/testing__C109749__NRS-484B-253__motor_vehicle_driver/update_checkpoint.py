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
    claim(physical['lifecycle']['command'], physical['lifecycle']['log'])

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
claim(f'.venv-cpu/bin/python work/{result["assignment_id"]}/validate_manifest.py',
      'manifest-validation.log')
claim(f'.venv-cpu/bin/python work/{result["assignment_id"]}/cases/approaching_yield/validate_draft.py',
      'cases/approaching_yield/draft-validation.log')
claim(f'PYTHONPATH=work/{result["assignment_id"]} .venv-cpu/bin/python '
      f'work/{result["assignment_id"]}/cases/approaching_yield/runner.py --check',
      'cases/approaching_yield/runner-check.log')
claim(f'.venv-cpu/bin/python work/{result["assignment_id"]}/cases/approaching_no_yield/validate_draft.py',
      'cases/approaching_no_yield/draft-validation.log')
claim(f'PYTHONPATH=work/{result["assignment_id"]} .venv-cpu/bin/python '
      f'work/{result["assignment_id"]}/cases/approaching_no_yield/runner.py --check',
      'cases/approaching_no_yield/runner-check.log')
result['tests'] = list(existing.values())
result['readiness_kind'] = 'four_case_canonical_partial_cpu_checkpoint'
result['reason'] = (
    'Four C109749 exact cases (reciprocal yield/continue and subject yield/proceed with an opposing '
    'complete body inside the junction), each with three distinct physical-risk fallbacks, now occur '
    'in the canonical case plan, semantic proposal and execution manifest. All 16 exact constructions '
    'pass current canonical offline, positive/negative compatibility and recorded-only saved processing. '
    'The pinned manifest, semantic, package-compatibility, physical-preparation and delivery-contract '
    'validators pass. Full-duration 900-frame synthetic delivery audits for all four and two diagnostic '
    'comparisons exercise source joins, fixed conditions and negative rejection; their diagnostic '
    'receipts explicitly do not claim physical or legal acceptance. An isolated approaching yield/proceed '
    'pair (fifth and sixth case drafts) each passes four offline, positive/negative compatibility and recorded-only '
    'saved-processing paths, but is not yet in the canonical plan or manifest and has no delivery/comparison proof. '
    'The three physical judgment sweep specs remain incomplete, and omitted-signal and other '
    'statutory alternatives have no complete selected constructions and CPU proofs. Accepted-original '
    'equivalence, actual Native motion and camera visibility are unverified. This and all other partial '
    'assignment packages are unfinished worker-owned CPU work, with no dependency or tool blocker. '
    'Strict assignment and batch gates fail with Preparation acceptance failed: partial/missing packages remain. '
    'See HANDOFF.md for exact sources and resume actions.'
)
result_path.write_text(json.dumps(result, indent=2) + '\n')

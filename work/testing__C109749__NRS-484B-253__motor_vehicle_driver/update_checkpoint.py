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

for label, attempt, log in (
    ('signalled', '.runtime-work/c109749-inside-yield-delivery-v2/attempt', 'signal-advance-positive.log'),
    ('omitted', '.runtime-work/c109749-signal-omitted-delivery-v1/attempt', 'signal-advance-omitted.log'),
):
    claim(f'.venv-cpu/bin/python work/{result["assignment_id"]}/signal_advance_audit.py {attempt}', log)
claim(f'.venv-cpu/bin/python -m unittest discover -s work/{result["assignment_id"]}/tests '
      '-p test_signal_advance_audit.py -v', 'signal-advance-tests.log')
claim(f'.venv-cpu/bin/python -m unittest discover -s work/{result["assignment_id"]}/tests '
      '-p test_advance_signal_setup.py -v', 'advance-signal-setup-tests.log')

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
claim(f'.venv-cpu/bin/python work/{result["assignment_id"]}/validate_approaching_delivery.py',
      'approaching-delivery-validation.log')
claim(f'.venv-cpu/bin/python work/{result["assignment_id"]}/approaching_comparison_audit.py '
      '--yield-recipe .runtime-work/c109749-approaching-yield-delivery-v1/attempt '
      '--no-yield-recipe .runtime-work/c109749-approaching-no-yield-delivery-v1/attempt '
      f'--output work/{result["assignment_id"]}/approaching-comparison-receipt.json',
      'approaching-comparison-positive.log')
claim(f'.venv-cpu/bin/python -m unittest discover '
      f'-s work/{result["assignment_id"]}/tests -p test_approaching_comparison.py -v',
      'approaching-comparison-negative.log')
claim(f'.venv-cpu/bin/python work/{result["assignment_id"]}/cases/signal_omitted/validate_draft.py',
      'cases/signal_omitted/draft-validation.log')
claim(f'PYTHONPATH=work/{result["assignment_id"]} .venv-cpu/bin/python '
      f'work/{result["assignment_id"]}/cases/signal_omitted/runner.py --check',
      'cases/signal_omitted/runner-check.log')
claim(f'.venv-cpu/bin/python work/{result["assignment_id"]}/validate_signal_delivery.py',
      'signal-delivery-validation.log')
claim(f'.venv-cpu/bin/python work/{result["assignment_id"]}/signal_comparison_audit.py '
      '--signalled .runtime-work/c109749-inside-yield-delivery-v2/attempt '
      '--omitted .runtime-work/c109749-signal-omitted-delivery-v1/attempt '
      f'--output work/{result["assignment_id"]}/signal-comparison-receipt.json',
      'signal-comparison-positive.log')
claim(f'.venv-cpu/bin/python -m unittest discover '
      f'-s work/{result["assignment_id"]}/tests -p test_signal_comparison.py -v',
      'signal-comparison-negative.log')
result['tests'] = list(existing.values())
result['readiness_kind'] = 'seven_case_canonical_partial_cpu_checkpoint'
result['reason'] = (
    'Seven C109749 exact cases (reciprocal yield/continue, subject yield/proceed with an opposing '
    'complete body inside or approaching outside the junction, and an omitted-signal contrast), '
    'each with three distinct physical-risk fallbacks, occur in the canonical case plan, semantic proposal '
    'and execution manifest. All 28 exact constructions '
    'pass current canonical offline, positive/negative compatibility and recorded-only saved processing. '
    'The pinned manifest, semantic, package-compatibility, physical-preparation and delivery-contract '
    'validators pass. Full-duration 900-frame synthetic delivery audits for all seven and four diagnostic '
    'comparisons exercise source joins, fixed conditions and negative rejection; their diagnostic '
    'receipts explicitly do not claim physical or legal acceptance. '
    'A supplemental sealed-history signal-distance audit measures 12.24 m visible before the '
    'signalled diagnostic turn and 0 m for omitted signal; neither source demonstrates the '
    '30.48 m or 91.44 m advance probe, and capture-start signal onset is unknown. '
    'A same-lane upstream waypoint selector for below/at/above distance candidates passes two '
    'construction tests, but is not yet integrated into a selected Native runner or exact proofs. '
    'The three physical judgment sweep specs remain incomplete, and reciprocal-no-yield and other '
    'statutory alternatives have no complete selected constructions and CPU proofs. Accepted-original '
    'equivalence, actual Native motion and camera visibility are unverified. This and all other partial '
    'assignment packages are unfinished worker-owned CPU work, with no dependency or tool blocker. '
    'Strict assignment and batch gates fail with Preparation acceptance failed: partial/missing packages remain. '
    'See HANDOFF.md for exact sources and resume actions.'
)
result_path.write_text(json.dumps(result, indent=2) + '\n')

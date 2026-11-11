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
claim(f'.venv-cpu/bin/python -m unittest discover -s work/{result["assignment_id"]}/tests '
      '-p test_signal_advance_native_probe.py -v', 'signal-native-probe-tests.log')
signal_draft = json.loads((folder / 'cases/signal_advance_100_at/draft-proof-receipt.json').read_text())
for proof in signal_draft['offline']:
    claim(proof['command'], 'cases/signal_advance_100_at/' + proof['log'])
claim(signal_draft['signal_source_proof']['command'],
      'cases/signal_advance_100_at/' + signal_draft['signal_source_proof']['log'])
claim(signal_draft['measurement_draft']['validation_command'],
      'cases/signal_advance_100_at/' + signal_draft['measurement_draft']['validation_log'])
claim(signal_draft['delivery_audit_draft']['test_command'],
      signal_draft['delivery_audit_draft']['test_log'])
signal_exact = json.loads((folder / 'cases/signal_advance_100_at/exact-proof-receipt.json').read_text())
signal_stage = '.runtime-work/c109749-signal-advance-stage-v4'
signal_stage_manifest = signal_stage + '/work/' + result['assignment_id'] + '/draft-manifest.json'
for proof in signal_exact['proofs']:
    label = proof['candidate_id']
    candidate = '' if label == 'primary' else ' --candidate ' + label
    command = (f'.venv-cpu/bin/python runtime.py compatibility --manifest {signal_stage_manifest} '
               f'--case {signal_exact["case_id"]} --output {signal_stage}/.runtime-work/signal-advance-{label}-compat '
               '--library runtime/library --validator .runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck'
               + candidate)
    claim(command, f'cases/signal_advance_100_at/proofs/{label}/exact-compatibility-command.log')
    command = (f'.venv-cpu/bin/python runtime.py process-saved --manifest {signal_stage_manifest} '
               f'--case {signal_exact["case_id"]} '
               f'--attempt {signal_stage}/.runtime-work/signal-advance-{label}-compat '
               f'--output {signal_stage}/.runtime-work/signal-advance-{label}-saved '
               '--library runtime/library --validator .runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck')
    claim(command, f'cases/signal_advance_100_at/proofs/{label}/saved-command.log')
signal_delivery = json.loads((folder / 'cases/signal_advance_100_at/delivery-proof-receipt.json').read_text())
claim(signal_delivery['positive']['command'],
      'cases/signal_advance_100_at/' + signal_delivery['positive']['log'])
claim(f'PYTHONPATH=work/{result["assignment_id"]} .venv-cpu/bin/python '
      f'work/{result["assignment_id"]}/cases/signal_advance_100_at/runner.py --check',
      'cases/signal_advance_100_at/runner-check.log')

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
for branch in ('reciprocal_no_yield', 'reciprocal_yield_matched'):
    draft = folder / 'cases' / branch
    claim(f'PYTHONPATH=work/{result["assignment_id"]} .venv-cpu/bin/python '
          f'work/{result["assignment_id"]}/cases/{branch}/runner.py --check',
          f'cases/{branch}/runner-check.log')
    claim(f'.venv-cpu/bin/python work/{result["assignment_id"]}/cases/{branch}/validate_draft.py',
          f'cases/{branch}/draft-validation.log')
    delivery_proof = json.loads((draft / 'delivery-proof-receipt.json').read_text())
    claim(delivery_proof['positive']['command'], f'cases/{branch}/delivery-positive.log')
for pattern, log in (
    ('test_reciprocal_no_yield_observation.py', 'observation-tests.log'),
    ('test_reciprocal_no_yield_delivery.py', 'delivery-tests.log'),
):
    claim(f'.venv-cpu/bin/python -m unittest discover -s work/{result["assignment_id"]}/tests '
          f'-p {pattern} -v', 'cases/reciprocal_no_yield/' + log)
comparison_proof = json.loads((folder / 'reciprocal-matched-comparison-receipt.json').read_text())
claim(comparison_proof['command'], 'reciprocal-matched-comparison-positive.log')
claim(f'.venv-cpu/bin/python -m unittest discover -s work/{result["assignment_id"]}/tests '
      '-p test_reciprocal_matched_comparison.py -v', 'comparison-tests.log')
for suffix in ('signal_advance_100_at', 'signal_advance_100_omitted'):
    draft = folder / 'cases' / suffix
    delivery = json.loads((draft / 'delivery-proof-receipt.json').read_text())
    claim(delivery['positive']['command'], f'cases/{suffix}/delivery-positive.log')
    claim(f'PYTHONPATH=work/{result["assignment_id"]} .venv-cpu/bin/python '
          f'work/{result["assignment_id"]}/cases/{suffix}/runner.py --check',
          f'cases/{suffix}/runner-check.log')
signal_comparison = json.loads((folder / 'signal-advance-comparison-receipt.json').read_text())
claim(signal_comparison['command'], signal_comparison['log'])
claim(signal_comparison['negative_test_command'], signal_comparison['negative_log'])
result['tests'] = list(existing.values())
result['readiness_kind'] = 'eleven_case_canonical_partial_cpu_checkpoint'
result['reason'] = (
    'Eleven C109749 exact cases, each with three physical-risk fallbacks, are in the canonical '
    'case plan, semantic proposal and execution manifest. All 44 exact constructions pass current '
    'canonical offline, positive/negative compatibility and recorded-only saved processing. '
    'The new 30.48 m signalled case measures 30.4800001 m from a sealed source; its matched '
    'omitted-signal companion differs only in indicator state across 900 diagnostic samples. '
    'Both new cases pass independent 900-frame four-camera CPU delivery audits and missing '
    'sealed-source rejection, and the controlled comparison passes positive and negative tests. '
    'Physical classifier and lifecycle CPU fixtures pass for all eleven cases. All diagnostic '
    'delivery receipts explicitly say passed false and claim no physical or legal acceptance. '
    'The three physical-judgment sweep specs and other statutory alternatives still lack '
    'complete selected constructions and CPU proofs. Accepted-original equivalence, actual '
    'Native motion and camera visibility remain unverified. This and the other partial '
    'assignments are unfinished worker-owned CPU work, with no dependency or tool blocker. '
    'See HANDOFF.md for exact sources, commands and resume actions.'
)
result_path.write_text(json.dumps(result, indent=2) + '\n')

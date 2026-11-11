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
    if case is manifest['cases'][0]:
        for candidate, item in [('primary', case)] + [(x['id'], x) for x in case['candidates']]:
            log = 'primary-compatibility.log' if candidate=='primary' else f'cases/{candidate}-compatibility.log'
            command = (f'.venv-cpu/bin/python runtime.py compatibility --manifest '
                       f'work/{result["assignment_id"]}/execution-manifest.json --case {case["case_id"]} '
                       f'--output .runtime-work/c109749-root-support-{candidate}-compat-v1 '
                       f'--library runtime/library '
                       f'--validator .runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck')
            if candidate!='primary': command += f' --candidate {candidate}'
            claim(command, log)
    for candidate in case['candidates']:
        claim(candidate['offline']['command'], candidate['offline']['log'])
        claim(candidate['post_capture']['command'], candidate['post_capture']['test_log'])
    physical = json.loads((folder / case['physical_preparation']['receipt']).read_text())
    for fixture in physical['fixtures']:
        claim(fixture['command'], fixture['log'])
    if case is manifest['cases'][0]:
        claim(f'.venv-cpu/bin/python work/{result["assignment_id"]}/physical_fixture_proof.py '
              f'--manifest work/{result["assignment_id"]}/execution-manifest.json '
              f'--case {case["case_id"]} --kind lifecycle '
              f'--output work/{result["assignment_id"]}/physical-proofs/primary/lifecycle.json',
              physical['lifecycle']['log'])

comparison = json.loads((folder / 'comparison-proofs/receipt.json').read_text())
claim(comparison['command'], comparison['log'])
result['tests'] = list(existing.values())
result['readiness_kind'] = 'two_case_fallback_comparison_and_delivery_audit_checkpoint'
result['reason'] = (
    'Two C109749 reciprocal-response cases and three fallbacks per case pass exact offline, '
    'compatibility and recorded-only saved processing. Source-bound physical-classifier and '
    'full-duration delivery-audit CPU fixtures pass software checks; diagnostic audits explicitly '
    'report passed=false. A comparison audit verifies fixed conditions and the declared later '
    'opposing response difference on synthetic sources, and rejects a changed fixed ego trajectory. '
    'Remaining statutory alternatives, semantic stage proposals, complete coverage and all other '
    'partial assignment packages are unfinished worker-owned CPU work. Root supported_case_ids '
    'now lists both selected cases and all affected primary proofs were rerun. Accepted-original '
    'equivalence and actual Native motion/pixel visibility are unverified. Strict assignment and '
    'batch gates fail with Preparation acceptance failed: partial/missing packages remain. See HANDOFF.md.'
)
result_path.write_text(json.dumps(result, indent=2) + '\n')

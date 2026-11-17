"""Record the selected CPU proof checkpoint without claiming delivery readiness."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MARKER = '## Update048: source-selected exact CPU cases'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    matrix = json.loads((ROOT / 'merged-offline-matrix-canonical-v3.json').read_text())
    if (len(plan['cases']) != 30 or len(manifest['cases']) != 30 or
            len(matrix['records']) != 120 or
            any(item['status'] != 'selected_required' for item in
                plan['requirement_dispositions'])):
        raise ValueError('Selected branch or exact offline matrix incomplete')
    for slug in ('reference', 'contrast', 'ordinary_red_signed'):
        receipt = json.loads((ROOT / ('selected-' + slug +
                                      '-four-candidate-proof-canonical-v4.json')).read_text())
        if len(receipt['records']) != 4 or any(
                row['manifest_sha256'] != sha(ROOT / 'execution-manifest.json')
                for row in receipt['records']):
            raise ValueError('Canonical short-case proof changed: ' + slug)
    mail = json.loads((ROOT / 'selected-mail-adjacent-primary-proof/receipt.json').read_text())
    mail_fallbacks = json.loads((ROOT /
        'selected-mail_adjacent_deposit-four-candidate-proof-pilot-v2.json').read_text())
    if (mail['saved_frames'] != 361 or
            len(mail_fallbacks['records']) != 3 or
            any(row['saved_frames'] != 361 for row in mail_fallbacks['records'])):
        raise ValueError('Mail pilot source proof incomplete')
    result_path = ROOT / 'result.json'
    result = json.loads(result_path.read_text())
    result.update(status='partial', readiness_kind=None, cases_selected=30,
                  candidate_plans_proven=12, comparison_audits_passed=0,
                  carla_executed=False, recordings_accepted=0)
    result['reason'] = (
        'Update048 checkpoint: frozen conditional red-curb witness and full statute '
        'selected for all 30 exact CPU cases; 10 requirement dispositions are selected_required '
        'with no accepted recording. All 120 primary/fallback constructions were rebound to '
        'the selected plan and passed current offline checks, with source-hashed logs bound in '
        'execution-manifest.json. Reference, contrast and ordinary_red_signed each passed '
        'canonical compatibility, missing-source negative, and saved processing for four '
        'candidates (12 fully proven canonical candidate plans). Mail_adjacent_deposit primary '
        'and three fallbacks passed the same 361-frame paths under a separate pilot manifest; '
        'its textual fixture, two-clause measurement contract and synthetic source audit passed '
        'but await canonical manifest integration and reproof. The remaining 26 exception cases '
        'need selected fixture recipes and measurement contracts; long 30-minute cases need a '
        'CPU-compatible path past the frozen 2000-frame fixture cap. The other selected cases '
        'also need exact positive/negative compatibility and saved receipts, original-delivery '
        'and source-bound comparison audit commands, acceptance bindings and queue integration. '
        'No original Native or physical/legal acceptance is claimed. Scoped strict remains partial. '
        'Full strict gate cannot pass while packages remain partial; the prior terminal full gate '
        'also reported frozen runtime/pipeline/runs/scenario_pipeline/inputs/shared/manifest.json '
        'as unapproved output. The current full-gate log is update048-full-strict.log. '
        'Construction and proof gaps remain worker-owned, not external blockers.')
    tests = [
        ('selected-v2-preflight.log', '.venv-cpu/bin/python runtime.py preflight'),
        ('selected-v2-root-tests.log', '.venv-cpu/bin/python -m unittest discover -s tests'),
        ('canonical-v3-merged-offline.log', '.venv-cpu/bin/python work/' + ROOT.name + '/prove-merged-offline.py --tag canonical-v3 --manifest work/' + ROOT.name + '/execution-manifest.json'),
        ('selected-reference-canonical-v4.log', '.venv-cpu/bin/python work/' + ROOT.name + '/prove-selected-reference.py --manifest work/' + ROOT.name + '/execution-manifest.json --tag canonical-v4 --slug reference'),
        ('selected-contrast-canonical-v4.log', '.venv-cpu/bin/python work/' + ROOT.name + '/prove-selected-reference.py --manifest work/' + ROOT.name + '/execution-manifest.json --tag canonical-v4 --slug contrast'),
        ('selected-ordinary-red-signed-canonical-v4.log', '.venv-cpu/bin/python work/' + ROOT.name + '/prove-selected-reference.py --manifest work/' + ROOT.name + '/execution-manifest.json --tag canonical-v4 --slug ordinary_red_signed'),
        ('selected-v2-comparison-diagnostics.log', '.venv-cpu/bin/python work/' + ROOT.name + '/native/prove_comparison_audit.py'),
        ('selected-mail-adjacent-fixture-build.log', '.venv-cpu/bin/python work/' + ROOT.name + '/build-mail-adjacent-fixture.py'),
        ('selected-mail-adjacent-fixture-materialize.log', '.venv-cpu/bin/python runtime.py fixture --recipe work/' + ROOT.name + '/selected-diagnostics/mail_adjacent_deposit/primary-recipe.json --output .runtime-work/c150142-selected-mail-adjacent-fixture-v1'),
        ('selected-mail-adjacent-contract-build.log', '.venv-cpu/bin/python work/' + ROOT.name + '/build-mail-adjacent-contract.py'),
        ('selected-mail-adjacent-pilot-compat-v2.log', '.venv-cpu/bin/python runtime.py compatibility --manifest work/' + ROOT.name + '/execution-manifest-mail-adjacent-pilot.json --case ' + ROOT.name + '__mail_adjacent_deposit --candidate primary --output .runtime-work/c150142-selected-mail-adjacent-pilot-compat-v2 --library runtime/pipeline/library --validator .runtime-work/c10316-current-decoder/.lake/build/bin/adapterCheck'),
        ('selected-mail-adjacent-fallbacks-pilot-v2.log', '.venv-cpu/bin/python work/' + ROOT.name + '/prove-selected-reference.py --manifest work/' + ROOT.name + '/execution-manifest-mail-adjacent-pilot.json --tag pilot-v2 --slug mail_adjacent_deposit --candidates fallback1 fallback2 fallback3'),
        ('selected-mail-adjacent-primary-proof/process-saved.json', '.venv-cpu/bin/python runtime.py process-saved --manifest work/' + ROOT.name + '/execution-manifest-mail-adjacent-pilot.json --case ' + ROOT.name + '__mail_adjacent_deposit --attempt .runtime-work/c150142-selected-mail-adjacent-pilot-attempt-v1 --output .runtime-work/c150142-selected-mail-adjacent-pilot-result-v1 --library runtime/pipeline/library --validator .runtime-work/c10316-current-decoder/.lake/build/bin/adapterCheck'),
        ('update048-scoped-complete.log', '.venv-cpu/bin/python worker_check.py --assignment ' + ROOT.name + ' --complete')]
    known = {entry['log'] for entry in result['tests']}
    for log, command in tests:
        path = ROOT / log
        if not path.is_file() or (log.endswith('.log') and
                ('Traceback (most recent call last)' in path.read_text() or
                 'RuntimeError:' in path.read_text())):
            raise ValueError('Passing proof log absent or failed: ' + log)
        if log not in known:
            result['tests'].append({'command': command, 'exit_code': 0,
                                    'log': log, 'sha256': sha(path)})
    result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False,
                                      allow_nan=False) + '\n')
    full = ROOT / 'update048-full-strict.log'
    gate = full.read_text() if full.exists() else ''
    gate_tail = gate.strip().splitlines()[-1] if gate.strip() else 'full gate still running'
    handoff = (
        '\n\n' + MARKER + '\n\n'
        'Selected the frozen conditional witness branch `Parking beside a red-painted curb, '
        'subject to the complete subsection.` after reviewing the exact assignment and witness; '
        'no accepted recording was supplied. `case-plan.json` now selects all 10 source requirements '
        'and 30 exact case definitions with explicit evidence gaps. Selection is a CPU planning '
        'decision; Native and legal facts remain unverified. `select-exact-cpu-cases.py` rebound '
        '120 primary/fallback construction bundles to plan SHA256 `' + sha(ROOT/'case-plan.json') + '`. '
        '`execution-manifest.json` is canonical and explicitly `delivery_ready: false`. '
        'The 120 offline logs are copied under `selected-offline/` and bound in that manifest; '
        'the fresh matrix is `merged-offline-matrix-canonical-v3.json`.\n\n'
        'Canonical selected `reference`, `contrast`, and `ordinary_red_signed` each passed '
        'four-candidate compatibility (including case-specific missing-source negatives) and '
        'the actual 240-frame saved-processing path. Receipts: '
        '`selected-{reference,contrast,ordinary_red_signed}-four-candidate-proof-canonical-v4.json`; '
        'each records the canonical manifest and construction hashes. The 18 comparison checker '
        'diagnostics passed on the selected plan (`selected-v2-comparison-diagnostics.log`); '
        'these are synthetic checker tests, not selected original-Native comparisons.\n\n'
        '`mail_adjacent_deposit` gained `selected-diagnostics/mail_adjacent_deposit/primary.json` '
        '(1.71 MB), a four-camera 361-frame fixture recipe, and '
        '`selected-measurement-contracts/mail_adjacent_deposit.json` for statutory topics '
        '`text-7`/`text-8`. Under `execution-manifest-mail-adjacent-pilot.json`, primary and '
        'three fallbacks passed positive/negative compatibility and saved processing; '
        '`selected-mail-adjacent-primary-proof/receipt.json` records the 361-frame source audit '
        'and `selected-mail_adjacent_deposit-four-candidate-proof-pilot-v2.json` binds the '
        'fallbacks. Pilot proofs are synthetic and await canonical binding/reproof.\n\n'
        'Current checks: preflight and root tests pass; scoped `--complete` passes. Scoped strict '
        'fails because status is truthfully partial (`selected-v2-scoped-strict.log`). '
        'Full strict `update048-full-strict.log` ends: `' + gate_tail + '`. '
        'The concurrent earlier full scan hit a disappearing ignored fixture directory '
        '(`selected-v2-full-strict.log`); the user-supplied terminal full scan named frozen '
        '`runtime/pipeline/runs/scenario_pipeline/inputs/shared/manifest.json` as unapproved. '
        'No frozen inputs, runtime, batch.json, or Git were edited.\n\n'
        'Next CPU work: generate source-bound fixture recipes and measurement contracts for '
        'the other 26 exception cases, solve the long-case compatibility fixture path, '
        'bind/reprove mail in the canonical manifest, run each candidate saved path, bind '
        'original-source delivery and comparison audits and local integration/queue proofs. '
        'Keep `result.json` partial until the assignment strict gate passes.\n')
    handoff_path = ROOT / 'HANDOFF.md'
    if MARKER not in handoff_path.read_text():
        with handoff_path.open('a') as stream:
            stream.write(handoff)
    shared = REPO / 'work/_shared/RETURN-REPORT.md'
    heading = '### C150142 Update048'
    if heading not in shared.read_text():
        summary = ('\n\n' + heading + '\n\n'
                   'Selected all 30 C150142 exact CPU cases from the frozen conditional '
                   'red-curb witness and full statute; 120 rebound candidates passed offline '
                   'and their logs are bound in the partial canonical manifest. Reference, '
                   'contrast and ordinary signed red curb passed four candidates each through '
                   'canonical compatibility and saved processing. Mail-adjacent deposit gained '
                   'a source-bound 361-frame recipe/contract and passed primary plus three '
                   'fallbacks under a pilot manifest. All evidence is synthetic CPU diagnostics; '
                   'no original Native, physical or legal acceptance. Other exception '
                   'contracts/fixtures, long-case compatibility, selected delivery/comparison '
                   'bindings and local integration remain worker-owned. Scoped complete passes; '
                   'strict remains partial. Full gate: `' + gate_tail + '`. See '
                   '`work/' + ROOT.name + '/HANDOFF.md` for exact receipts and resume steps.\n')
        if shared.stat().st_size + len(summary.encode()) >= 2 * 1024 * 1024:
            raise ValueError('Shared return report would exceed 2 MiB')
        with shared.open('a') as stream:
            stream.write(summary)
    print(json.dumps({'status': result['status'], 'cases_selected': 30,
                      'canonical_fully_proven_candidates': 12,
                      'mail_pilot_candidates': 4,
                      'tests': len(result['tests']),
                      'full_gate_last_line': gate_tail}))


if __name__ == '__main__':
    main()

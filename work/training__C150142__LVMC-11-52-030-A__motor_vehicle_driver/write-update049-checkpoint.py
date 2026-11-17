"""Record selected armored pilot proofs without asserting delivery readiness."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = ROOT.name
MARKER = '## Update049: selected armored source pilots'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    slugs = ('armored_car_signed_business', 'armored_car_signed_no_business',
             'armored_car_unsigned_business', 'armored_car_unsigned_no_business')
    for slug in slugs:
        proofs = ([ROOT / ('selected-' + slug + '-four-candidate-proof-pilot-v1.json'),
                   ROOT / ('selected-' + slug + '-four-candidate-proof-pilot-fallbacks-v1.json')]
                  if slug == 'armored_car_signed_business' else
                  [ROOT / ('selected-' + slug + '-four-candidate-proof-pilot-v1.json')])
        rows = [row for proof in proofs for row in json.loads(proof.read_text())['records']]
        if [row['candidate_id'] for row in rows] != [
                'primary', 'fallback1', 'fallback2', 'fallback3'] or any(
                row['saved_frames'] != 361 or row['physical_acceptance_claimed']
                for row in rows):
            raise ValueError('Armored pilot proof incomplete: ' + slug)
    audit = json.loads((ROOT / 'selected-armored-pilot-source-audit-v1.json').read_text())
    if len(audit['records']) != 16 or audit['original_native_observed']:
        raise ValueError('Selected armored source audit incomplete')
    result_path = ROOT / 'result.json'
    result = json.loads(result_path.read_text())
    result['status'] = 'partial'
    result['readiness_kind'] = None
    result['candidate_plans_proven'] = 12  # Canonical full proofs only.
    result['reason'] = (
        'Update049: 30 exact selected cases and 120 canonical offline candidate passes remain. '
        'Three short cases have 12 canonical four-candidate compatibility/saved proofs. '
        'Three mail and four armored exception cases have 28 four-candidate synthetic pilot '
        'compatibility/saved proofs with bounded returned fixtures and measurement contracts; '
        'the 16 armored pilot saved sources passed independent source recomputation. These seven '
        'pilot cases require canonical manifest binding and reproof. The other 20 exception cases '
        'still need selected fixture/contract construction and exact compatibility/saved proofs. '
        'Long 30-minute cases need a CPU path beyond the frozen fixture generator 2000-frame cap. '
        'Original-source delivery/comparison acceptance bindings and local integration remain '
        'worker-owned CPU work. No original Native, CARLA motion, physical or legal acceptance '
        'is claimed. Scoped strict remains partial; full strict also rejects the pre-existing '
        'frozen runtime/pipeline/runs/scenario_pipeline/inputs/shared/manifest.json as unapproved '
        'output. See HANDOFF.md for exact receipts and resume commands.')
    logs = [
        ('selected-armored-signed-business-primary-pilot-v1.log',
         'prove-selected-reference.py --slug armored_car_signed_business --candidates primary --tag pilot-v1'),
        ('selected-armored-signed-business-fallbacks-pilot-v1.log',
         'prove-selected-reference.py --slug armored_car_signed_business --candidates fallback1 fallback2 fallback3 --tag pilot-fallbacks-v1'),
        *[('selected-' + slug + '-pilot-v1.log',
           'prove-selected-reference.py --slug ' + slug + ' --tag pilot-v1')
          for slug in slugs[1:]],
        ('selected-armored-source-audit-v1.log', 'audit-selected-armored-pilots.py'),
        ('update049-preflight.log', '.venv-cpu/bin/python runtime.py preflight'),
        ('update049-root-tests.log', '.venv-cpu/bin/python -m unittest discover -s tests'),
        ('update049-scoped-complete.log', '.venv-cpu/bin/python worker_check.py --assignment ' +
         ASSIGNMENT + ' --complete')]
    known = {row['log'] for row in result['tests']}
    for name, command in logs:
        path = ROOT / name
        if not path.is_file() or 'Traceback (most recent call last)' in path.read_text():
            raise ValueError('Passing log absent or failed: ' + name)
        if name not in known:
            result['tests'].append({'command': command, 'exit_code': 0,
                                    'log': name, 'sha256': sha(path)})
    result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    handoff = ROOT / 'HANDOFF.md'
    if MARKER not in handoff.read_text():
        with handoff.open('a') as stream:
            stream.write('\n\n' + MARKER + '\n\n'
                'Built `selected-diagnostics/armored_car_*/primary.json` and their recipes '
                'for four exact armored cases. Each is a bounded 361-frame, four-camera '
                '`synthetic_native_sample` based on retained worker diagnostics, with '
                'source-joined actor, panel readback and business/absence rows. '
                '`selected-measurement-contracts/armored_car_*.json` binds frozen `text-6` '
                'to the executed `signed_curb_observation` and removes the case-specific '
                'participant source for the negative check. `build-selected-armored-fixture.py` '
                'and `build-selected-armored-pilot.py` reproduce the returned text artifacts.\n\n'
                'For each of the four cases, primary and all three distinct fallback '
                'constructions passed positive/negative compatibility and 361-frame saved '
                'processing under `execution-manifest-armored-*-pilot.json`. Receipts are '
                '`selected-armored_car_*-four-candidate-proof-pilot-v1.json` (signed business '
                'uses `pilot-v1` primary and `pilot-fallbacks-v1` fallback receipts). '
                '`selected-armored-pilot-source-audit-v1.json` independently recomputes '
                'stationary duration, source hashes, sign and service class and checks the '
                'recorded business event/absence for all 16 saved candidates. Command: '
                '`.venv-cpu/bin/python work/' + ASSIGNMENT +
                '/audit-selected-armored-pilots.py`; log `selected-armored-source-audit-v1.log`. '
                'The attached-panel visual proxy is not an accepted armored identity or '
                'original Native observation.\n\n'
                'Preflight and root tests passed (`update049-preflight.log`, '
                '`update049-root-tests.log`); scoped complete passed '
                '(`update049-scoped-complete.log`). Assignment remains partial. Next CPU work: '
                'construct the other 20 exception fixtures/contracts and their four-candidate '
                'proofs; solve long-case fixture cap; bind/reprove all seven pilot cases in the '
                'canonical manifest; finish original-source delivery/comparison acceptance '
                'and local integration. Full strict still identifies frozen runtime path '
                '`runtime/pipeline/runs/scenario_pipeline/inputs/shared/manifest.json` as '
                'unapproved; no frozen file was edited.\n')
    shared = REPO / 'work/_shared/RETURN-REPORT.md'
    marker = '### C150142 Update049'
    if marker not in shared.read_text():
        summary = ('\n\n' + marker + '\n\nFour selected armored exception cases now have '
                   'bounded four-camera CPU fixtures and exact text-6 measurement contracts. '
                   'All 16 primary/fallback pilot compatibility and saved-processing paths '
                   'passed, with independent synthetic source recomputation. Seven exception '
                   'pilot cases (three mail, four armored) await canonical binding/reproof; '
                   '20 other exception cases and long-case fixture support remain worker-owned. '
                   'Canonical fully proven candidate count remains 12; status is partial. '
                   'No original Native or physical/legal acceptance is claimed. See `work/' +
                   ASSIGNMENT + '/HANDOFF.md` for receipts.\n')
        if shared.stat().st_size + len(summary.encode()) >= 2 * 1024 * 1024:
            raise ValueError('Shared report exceeds 2 MiB')
        with shared.open('a') as stream:
            stream.write(summary)
    print(json.dumps({'status': 'partial', 'canonical_candidates': 12,
                      'exception_pilot_candidates': 28,
                      'armored_sources_audited': 16}))


if __name__ == '__main__':
    main()

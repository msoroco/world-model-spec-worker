"""Record the selected emergency CPU pilot checkpoint as partial."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SLUGS = ('emergency_vehicle_signed_business',
         'emergency_vehicle_signed_no_business',
         'emergency_vehicle_unsigned_business',
         'emergency_vehicle_unsigned_no_business')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    for slug in SLUGS:
        paths = ([ROOT / ('selected-' + slug + '-four-candidate-proof-pilot-primary-v1.json'),
                  ROOT / ('selected-' + slug + '-four-candidate-proof-pilot-fallbacks-v1.json')]
                 if slug == SLUGS[0] else
                 [ROOT / ('selected-' + slug + '-four-candidate-proof-pilot-v1.json')])
        rows = [row for path in paths for row in json.loads(path.read_text())['records']]
        if [row['candidate_id'] for row in rows] != [
                'primary', 'fallback1', 'fallback2', 'fallback3'] or any(
                row['saved_frames'] != 361 or row['physical_acceptance_claimed']
                for row in rows):
            raise ValueError('Emergency pilot incomplete: ' + slug)
    audit = json.loads((ROOT / 'selected-emergency-pilot-source-audit-v1.json').read_text())
    if len(audit['records']) != 16 or audit['original_native_observed']:
        raise ValueError('Emergency source audit incomplete')
    result_path = ROOT / 'result.json'
    result = json.loads(result_path.read_text())
    result['status'] = 'partial'
    result['readiness_kind'] = None
    result['candidate_plans_proven'] = 12  # Canonical full proofs only.
    result['reason'] = (
        'Update050: all 30 exact selected cases and 120 canonical offline candidate passes '
        'remain. Three short cases have 12 canonical candidate compatibility/saved proofs. '
        'Three mail, four armored, and four emergency exception cases have 44 four-candidate '
        'synthetic pilot compatibility/saved proofs with bounded returned fixtures and exact '
        'measurement contracts. The 32 armored/emergency saved sources passed independent '
        'source recomputation. These 11 pilot cases need canonical binding and reproof; the '
        'other 16 exception cases need selected fixtures/contracts and candidate proofs. Long '
        '30-minute cases need a CPU path beyond the frozen 2000-frame fixture cap. Original '
        'delivery/comparison acceptance bindings and local integration remain worker-owned CPU '
        'work. No original Native, CARLA motion, physical or legal acceptance is claimed. '
        'Scoped strict remains partial. The latest terminal full strict gate rejected frozen '
        'runtime/pipeline/runs/scenario_pipeline/inputs/shared/manifest.json as unapproved; '
        'a repeat whole-tree scan was interrupted after several minutes without output. '
        'See HANDOFF.md for exact receipts and resume commands.')
    logs = [
        ('selected-emergency-signed-business-primary-pilot-v1.log',
         'prove-selected-reference.py --slug emergency_vehicle_signed_business --candidates primary --tag pilot-primary-v1'),
        ('selected-emergency-signed-business-fallbacks-pilot-v1.log',
         'prove-selected-reference.py --slug emergency_vehicle_signed_business --candidates fallback1 fallback2 fallback3 --tag pilot-fallbacks-v1'),
        *[('selected-' + slug + '-pilot-v1.log',
           'prove-selected-reference.py --slug ' + slug + ' --tag pilot-v1')
          for slug in SLUGS[1:]],
        ('selected-emergency-source-audit-v1.log', 'audit-selected-emergency-pilots.py'),
        ('update050-preflight.log', '.venv-cpu/bin/python runtime.py preflight'),
        ('update050-root-tests.log', '.venv-cpu/bin/python -m unittest discover -s tests'),
        ('update050-scoped-complete.log', '.venv-cpu/bin/python worker_check.py --assignment ' +
         ROOT.name + ' --complete')]
    known = {row['log'] for row in result['tests']}
    for name, command in logs:
        path = ROOT / name
        if not path.is_file() or 'Traceback (most recent call last)' in path.read_text():
            raise ValueError('Passing log absent or failed: ' + name)
        if name not in known:
            result['tests'].append({'command': command, 'exit_code': 0,
                                    'log': name, 'sha256': sha(path)})
    result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    handoff_path = ROOT / 'HANDOFF.md'
    marker = '## Update050: selected emergency source pilots'
    if marker not in handoff_path.read_text():
        with handoff_path.open('a') as stream:
            stream.write('\n\n' + marker + '\n\n'
                '`build-selected-emergency-fixture.py` produced four bounded textual '
                '361-frame, four-camera source recipes under `selected-diagnostics/` '
                'for signed/unsigned business and no-business emergency vehicle cases. '
                '`build-selected-emergency-pilot.py` bound frozen `text-6` to '
                '`signed_curb_observation` with a case-specific missing participant source '
                'negative and wrote four partial pilot manifests. All primary and three '
                'fallbacks for each case passed current compatibility (including negatives) '
                'and saved processing: `selected-emergency_vehicle_*-four-candidate-proof-'
                'pilot-v1.json`, with signed business split into `pilot-primary-v1` and '
                '`pilot-fallbacks-v1` receipts. `audit-selected-emergency-pilots.py` '
                'independently recomputed stationary duration, source hashes, sign, service '
                'class and activity/absence for all 16 saved sources; receipt '
                '`selected-emergency-pilot-source-audit-v1.json`, log '
                '`selected-emergency-source-audit-v1.log`. These are synthetic CPU diagnostics '
                'and do not establish actual emergency status or legal/physical acceptance.\n\n'
                'Preflight, root tests and scoped complete passed (`update050-preflight.log`, '
                '`update050-root-tests.log`, `update050-scoped-complete.log`). Scoped strict '
                'still fails because status is partial. The repeat full-tree gate was '
                'interrupted after several minutes without output; the latest terminal '
                'full strict result remains `update048-full-strict.log`, which rejects '
                'frozen `runtime/pipeline/runs/scenario_pipeline/inputs/shared/manifest.json` '
                'as unapproved. Next CPU work: construct 16 remaining exception fixtures '
                'and contracts, solve long-case fixture cap, bind and reprove 11 pilots '
                'canonically, and complete original delivery/comparison and integration '
                'proofs. No frozen inputs, runtime, batch.json or Git were edited.\n')
    shared = REPO / 'work/_shared/RETURN-REPORT.md'
    marker = '### C150142 Update050'
    if marker not in shared.read_text():
        summary = ('\n\n' + marker + '\n\nFour emergency exception cases now have '
                   'bounded source fixtures and exact text-6 contracts. All 16 primary/'
                   'fallback pilot compatibility and saved-processing paths passed, with '
                   'independent synthetic source recomputation. Eleven exception pilots '
                   'await canonical binding/reproof; 16 other exception cases and long-case '
                   'fixture support remain CPU work. Status remains partial; no original '
                   'Native or physical/legal acceptance. See `work/' + ROOT.name +
                   '/HANDOFF.md` for receipts.\n')
        if shared.stat().st_size + len(summary.encode()) >= 2 * 1024 * 1024:
            raise ValueError('Shared report exceeds 2 MiB')
        with shared.open('a') as stream:
            stream.write(summary)
    print(json.dumps({'status': 'partial', 'canonical_candidates': 12,
                      'exception_pilot_candidates': 44,
                      'armored_emergency_sources_audited': 32}))


if __name__ == '__main__':
    main()

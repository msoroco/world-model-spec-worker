"""Record exact current CPU receipts without promoting unfinished delivery."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
RESULT = ROOT / 'result.json'
HANDOFF = ROOT / 'HANDOFF.md'
REPORT = REPO / 'work/_shared/RETURN-REPORT.md'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def test(command, log):
    return {'command': command, 'exit_code': 0, 'log': log,
            'sha256': sha(ROOT / log)}


assignment = ROOT.name
base = 'work/' + assignment
manifest = base + '/execution-manifest-draft.json'
case = assignment + '__reference'
python = str(REPO / '.venv-cpu/bin/python')
proofs = [test(
    f'.venv-cpu/bin/python runtime.py offline --manifest {manifest} --case {case} '
    f'--output .runtime-work/c146314-210-2-reference-primary-offline-update056d --python {python}',
    'update056d-reference-primary-offline.log')]
proofs += [test(
    f'.venv-cpu/bin/python runtime.py offline --manifest {manifest} --case {case} '
    f'--candidate fallback{n} --output .runtime-work/c146314-210-2-reference-fallback{n}-offline-update056 '
    f'--python {python}',
    f'update056-reference-fallback{n}-offline.log') for n in (1, 2, 3)]
proofs += [test(
    f'.venv-cpu/bin/python runtime.py compatibility --manifest {manifest} --case {case} '
    '--output .runtime-work/c146314-210-2-reference-primary-compat-update056d '
    '--library runtime/pipeline/library '
    '--validator .runtime-work/c10316-current-decoder/.lake/build/bin/adapterCheck',
    'update056d-reference-primary-compat.log'),
    test(f'.venv-cpu/bin/python {base}/run-reference-primary-saved.py',
         'update056d-reference-primary-saved.log')]

value = json.loads(RESULT.read_text())
value['status'] = 'partial'
value['readiness_kind'] = None
value['cases_selected'] = 0
value['candidate_plans_proven'] = 0
value['reason'] = (
    'The reference selected primary now passes exact pinned offline, positive and missing-raw-source '
    'negative compatibility, and fresh actual saved processing with 240 joined frames, four source cameras, '
    'Core/Lean and final video decode; no missing evidence. Three distinct reference fallbacks pass offline '
    'and candidate structure validation. They still need candidate-specific compatibility and saved proofs. '
    'The contrast case, canonical semantic stages, independent selected physical/delivery and comparison '
    'audits, and scoped strict readiness remain unfinished worker-owned CPU work. Synthetic sources prove '
    'software behavior only; no original Native motion, legal safety finding or accepted recording is claimed.'
)
old = {row['log']: row for row in value['tests']}
old.update({row['log']: row for row in proofs})
value['tests'] = list(old.values())
RESULT.write_text(json.dumps(value, indent=2) + '\n')

compat = REPO / '.runtime-work/c146314-210-2-reference-primary-compat-update056d/compatibility.json'
saved = REPO / '.runtime-work/c146314-210-2-reference-primary-fresh-update056d-saved/v0001/processing.json'
saved_value = json.loads(saved.read_text())
assert saved_value['passed'] and not saved_value['missing_evidence']
assert saved_value['originals_preserved'] and saved_value['timestamp_joins']['frames'] == 240
assert saved_value['final_video_checks']['passed']
paragraph = f'''\n## Update 056: selected reference primary and fallback offline checkpoint

Exact NRS 484B.210(2) reference case `{case}` has an inline selected Native primary at `selected-primary/reference/construction.json`, four-camera source fixture recipe, source-derived finalizer, measurement contract and draft execution manifest. Its current-manifest pinned `runtime.py offline` passes (`update056d-reference-primary-offline.log`, SHA-256 `{sha(ROOT / 'update056d-reference-primary-offline.log')}`). Positive pinned `runtime.py compatibility` and its missing `native-raw-actors.jsonl` negative pass (`update056d-reference-primary-compat.log`, SHA-256 `{sha(ROOT / 'update056d-reference-primary-compat.log')}`; receipt SHA-256 `{sha(compat)}`). A fresh materialized attempt then passes actual pinned `runtime.py process-saved`, with `missing_evidence=false`, original sources preserved, 240 timestamp joins and full final decode (`update056d-reference-primary-saved.log`, SHA-256 `{sha(ROOT / 'update056d-reference-primary-saved.log')}`; processing receipt SHA-256 `{sha(saved)}`). Earlier Update 056 compatibility and saved trials are historical because the fixture recorder identity and manifest changed. The earlier saved run against a derived compatibility output returned `missing_evidence=true`; the fresh run corrected the source staging.

Three distinct right-pass reference fallback bundles at `selected-fallbacks/reference/fallback1..3/construction.json` respectively lower paired speed, elevate overview, and extend lane entry. All pass pinned `runtime.py offline` under the current draft manifest. Their logs are `update056-reference-fallback1-offline.log` SHA-256 `{sha(ROOT / 'update056-reference-fallback1-offline.log')}`, `update056-reference-fallback2-offline.log` SHA-256 `{sha(ROOT / 'update056-reference-fallback2-offline.log')}`, and `update056-reference-fallback3-offline.log` SHA-256 `{sha(ROOT / 'update056-reference-fallback3-offline.log')}`. The pinned candidate validator accepts the three distinct structures. No fallback compatibility or saved receipt is claimed.

Next worker-owned CPU steps: produce exact candidate-specific retained-source diagnostics and run positive/negative compatibility plus fresh saved processing for all three reference fallbacks; build the contrast primary and three fallbacks with the same chain; complete and test canonical stage proposals, independent selected delivery/physical audits and source-bound comparison audit; bind the canonical manifest and rerun scoped strict readiness. Current `result.json` stays `partial`, with zero fully selected cases. The synthetic motion, physical clearance, camera pixels and NRS safety judgment have no original acceptance claim. No frozen file or Git operation was performed.\n'''
with HANDOFF.open('a') as stream:
    stream.write(paragraph)
with REPORT.open('a') as stream:
    stream.write(paragraph.replace('## Update 056:', '## Update 056 C146314:'))
print('checkpoint-written', len(proofs), 'new proof entries')

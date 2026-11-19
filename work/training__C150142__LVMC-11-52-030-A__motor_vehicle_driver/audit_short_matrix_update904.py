"""Independently rebind all 56 short chains to final selected sources."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


manifest = json.loads(MANIFEST.read_text())
manifest_sha = sha(MANIFEST)
primary = json.loads((HERE / 'update902-short-primary-index.json').read_text())
reference_fallback = json.loads((HERE / 'update903-reference-fallback-index.json').read_text())
fallback = json.loads((HERE / 'update904-short-fallback-index.json').read_text())
for index in (primary, reference_fallback, fallback):
    require(index['manifest_sha256'] == manifest_sha, 'Historical short-chain index')
require(len(primary['proofs']) == 13 and len(reference_fallback['proofs']) == 3 and
        len(fallback['proofs']) == 39, 'Incomplete short-chain indexes')
selected = {(entry['case_id'].removeprefix(HERE.name + '__'), candidate): entry
            for entry in manifest['cases'] if entry.get('fixture_recipe')
            for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3')}
require(len(selected) == 56, 'Short selected matrix differs')
seen = set()
rows = []
for case, candidate in sorted(selected):
    if case == 'reference' and candidate == 'primary':
        base = ROOT / '.runtime-work/c150142-update900/reference/primary'
        logs = [HERE / 'update902-reference-offline.log',
                HERE / 'update900-reference-primary-compatibility.log',
                HERE / 'update901-reference-primary-saved.log']
    elif case == 'reference':
        base = ROOT / '.runtime-work/c150142-update903/reference' / candidate
        record = next(x for x in reference_fallback['proofs'] if x['candidate'] == candidate)
        logs = [ROOT / record[k]['log'] for k in ('offline', 'compatibility', 'saved')]
        for name, log in zip(('offline', 'compatibility', 'saved'), logs):
            require(sha(log) == record[name]['sha256'], 'Reference fallback log changed')
    elif candidate == 'primary':
        base = ROOT / '.runtime-work/c150142-update902' / case / candidate
        record = next(x for x in primary['proofs'] if x['case'] == case)
        logs = [ROOT / record[k]['log'] for k in ('offline', 'compatibility', 'saved')]
        for name, log in zip(('offline', 'compatibility', 'saved'), logs):
            require(sha(log) == record[name]['sha256'], 'Primary log changed')
    else:
        base = ROOT / '.runtime-work/c150142-update904' / case / candidate
        record = next(x for x in fallback['proofs']
                      if x['case'] == case and x['candidate'] == candidate)
        logs = [ROOT / record[k]['log'] for k in ('offline', 'compatibility', 'saved')]
        for name, log in zip(('offline', 'compatibility', 'saved'), logs):
            require(sha(log) == record[name]['sha256'], 'Fallback log changed')
    entry = selected[(case, candidate)]
    candidate_entry = next((x for x in entry['candidates'] if x['id'] == candidate), None)
    recipe_ref = (candidate_entry or {}).get('fixture_recipe') or entry['fixture_recipe']
    construction_sha = (candidate_entry or entry)['construction_sha256']
    compat_path = base / 'compatibility/compatibility.json'
    saved_path = base / 'saved/v0001/processing.json'
    compat = json.loads(compat_path.read_text())
    saved = json.loads(saved_path.read_text())
    case_id = HERE.name + '__' + case
    require(compat['passed'] is True and compat['case_id'] == case_id and
            compat['candidate_id'] == candidate and
            compat['construction_sha256'] == construction_sha and
            compat['fixture_recipe_sha256'] == sha(ROOT / recipe_ref),
            'Compatibility selection/source differs: ' + case + '/' + candidate)
    require(saved['passed'] is True and saved['recorded_only'] is True and
            saved['missing_evidence'] is False and saved['originals_preserved'] is True and
            saved['case_id'] == case_id and saved['candidate_id'] == candidate and
            bool(saved['original_source_hashes']) and all(log.is_file() for log in logs),
            'Saved source binding differs: ' + case + '/' + candidate)
    seen.add((case, candidate))
    rows.append({'case': case, 'candidate': candidate,
                 'compatibility_sha256': sha(compat_path),
                 'saved_sha256': sha(saved_path)})
require(seen == set(selected), 'Short matrix coverage differs')
proof = {'format': 'c150142-current-short-matrix-audit-v1',
         'manifest_sha256': manifest_sha, 'chains_passed': len(rows),
         'diagnostic_only': True, 'original_native_accepted': False,
         'rows': rows}
path = HERE / 'update904-short-matrix-audit.json'
path.write_text(json.dumps(proof, indent=2) + '\n')
print(json.dumps({'chains_passed': len(rows), 'audit_sha256': sha(path)}))

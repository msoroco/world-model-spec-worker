"""Independently check final selected C177225 source and receipt bindings."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


manifest = json.loads(MANIFEST.read_text())
index = json.loads((HERE / 'update071-selected-index.json').read_text())
require(len(index['proofs']) == 8, 'Incomplete candidate matrix')
seen = set()
rows = []
for proof in index['proofs']:
    case, candidate = proof['case'], proof['candidate']
    require((case, candidate) not in seen, 'Duplicate candidate proof')
    seen.add((case, candidate))
    entry = next(x for x in manifest['cases'] if x['case_id'] == HERE.name + '__' + case)
    target = entry if candidate == 'primary' else next(x for x in entry['candidates']
                                                       if x['id'] == candidate)
    recipe = (target.get('fixture_recipe') or entry['fixture_recipe'])
    construction = HERE / target['construction']
    require(sha(construction) == target['construction_sha256'], 'Construction changed')
    compat_path = HERE / target['compatibility']['receipt']
    saved_path = HERE / target['saved_processing']['receipt']
    compat = json.loads(compat_path.read_text())
    saved = json.loads(saved_path.read_text())
    require(sha(compat_path) == target['compatibility']['sha256'] and
            sha(saved_path) == target['saved_processing']['sha256'],
            'Selected receipt changed')
    require(compat['passed'] is True and compat['case_id'] == entry['case_id'] and
            compat['candidate_id'] == candidate and
            compat['construction_sha256'] == target['construction_sha256'] and
            compat['fixture_recipe_sha256'] == sha(ROOT / recipe) and
            {'selected_measurements', 'negative_case_source', 'lean_decoder', 'final_decode'}
            <= set(compat['checks']), 'Compatibility selection changed')
    require(sha(HERE / target['compatibility']['log']) == compat['log_sha256'] and
            sha(HERE / target['compatibility']['negative_log']) == compat['negative_log_sha256'],
            'Compatibility source logs changed')
    require(saved['passed'] is True and saved['recorded_only'] is True and
            saved['missing_evidence'] is False and saved['originals_preserved'] is True and
            saved['case_id'] == entry['case_id'] and saved['candidate_id'] == candidate and
            bool(saved['original_source_hashes']), 'Saved source receipt incomplete')
    require(target['offline']['exit_code'] == 0 and
            sha(HERE / target['offline']['log']) == target['offline']['log_sha256'],
            'Offline proof changed')
    for phase in ('offline', 'compatibility', 'saved'):
        require(sha(ROOT / proof[phase]['log']) == proof[phase]['sha256'],
                'Original selected chain log changed')
    rows.append({'case': case, 'candidate': candidate,
                 'construction_sha256': target['construction_sha256'],
                 'compatibility_sha256': sha(compat_path),
                 'saved_sha256': sha(saved_path)})
require(seen == {(case, candidate) for case in ('reference', 'contrast')
                 for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3')},
        'Selected matrix coverage differs')
for entry in manifest['cases']:
    case = entry['case_id'].removeprefix(HERE.name + '__')
    proof_path = HERE / entry['physical_preparation']['receipt']
    physical = json.loads(proof_path.read_text())
    require(sha(proof_path) == entry['physical_preparation']['sha256'] and
            physical['original_native_observed'] is False and
            physical['physical_acceptance_claimed'] is False and
            {item['kind'] for item in physical['fixtures']} ==
            {'complete_motion', 'incomplete_motion', 'missing_evidence'},
            'Synthetic physical proof changed')
    old = ROOT / f'.runtime-work/update068-c177225-{case}-compatibility'
    new = (ROOT / '.runtime-work/c177225-update071/reference/primary/compatibility'
           if case == 'reference' else
           ROOT / '.runtime-work/c177225-update071b/contrast/primary/compatibility')
    for name in ('config.json', 'officer_signal_definition.json', 'bus_native_rows.jsonl',
                 'officer_signal_rows.jsonl', 'video_frames.jsonl'):
        require(sha(old / name) == sha(new / name), 'Physical source differs from current: ' + name)
comparison = HERE / manifest['comparison_diagnostic']['receipt']
require(sha(comparison) == manifest['comparison_diagnostic']['sha256'] and
        json.loads(comparison.read_text())['passed'] is True,
        'Current comparison differs')
proof = {'format': 'c177225-final-current-cpu-audit-v1',
         'manifest_sha256': sha(MANIFEST), 'candidate_chains_passed': len(rows),
         'rows': rows, 'physical_fixture_source_equivalent': True,
         'diagnostic_only': True, 'original_native_accepted': False}
path = HERE / 'update073-final-selected-audit.json'
path.write_text(json.dumps(proof, indent=2) + '\n')
print(json.dumps({'candidate_chains_passed': len(rows), 'audit_sha256': sha(path)}))

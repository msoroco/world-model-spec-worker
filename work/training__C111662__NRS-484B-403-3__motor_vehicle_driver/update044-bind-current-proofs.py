"""Bind migrated-input candidate diagnostics and audit selected saved pairs."""
import hashlib
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / 'native'))
from audit_saved_pair import CASES as PAIRS, audit as audit_pair  # noqa: E402

CASES = ('reference', 'contrast', 'divided_reference', 'divided_opening')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')
EARLY = {
    ('reference', 'primary'): ('update043c-current-input-reference-primary-offline.log',
                               'update043e-current-input-reference-primary-compat.log',
                               'update043e-current-input-reference-primary-process-saved.log',
                               '.runtime-work/c111662-update043e-current-input-reference-primary-compat'),
    ('reference', 'fallback1'): ('update043f-current-reference-fallback1-offline.log',
                                 'update043f-current-reference-fallback1-compat.log',
                                 'update043f-current-reference-fallback1-process-saved.log',
                                 '.runtime-work/c111662-update043f-current-reference-fallback1-compat'),
    ('reference', 'fallback2'): ('update044-reference-fallback2-offline.log',
                                 'update044-reference-fallback2-compat.log',
                                 'update044-reference-fallback2-saved.log',
                                 '.runtime-work/update044-c111662/reference/fallback2/compat'),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def require(value, message):
    if not value:
        raise ValueError(message)


def bind(case, candidate):
    proof = HERE / 'update044-current-proof' / case / candidate
    proof.mkdir(parents=True, exist_ok=True)
    if (case, candidate) in EARLY:
        offline, compat, saved, attempt = EARLY[case, candidate]
        for source, target in ((HERE / offline, proof / 'offline.log'),
                               (HERE / compat, proof / 'compatibility.json'),
                               (HERE / saved, proof / 'processing.json'),
                               (ROOT / attempt / 'negative-analysis.log', proof / 'negative-analysis.log')):
            require(source.is_file(), 'Missing early proof: ' + str(source))
            shutil.copyfile(source, target)
    else:
        attempt = ROOT / '.runtime-work/update044-c111662' / case / candidate / 'compat'
        shutil.copyfile(attempt / 'negative-analysis.log', proof / 'negative-analysis.log')
    shutil.copyfile(ROOT / attempt / 'compatibility-analysis.log', proof / 'analysis.log')
    manifest = (HERE / 'execution-manifest.json' if (case, candidate) == ('reference', 'primary')
                else HERE / f'update043-current-manifest-{case}-{candidate}.json')
    if (case, candidate) == ('reference', 'primary'):
        snapshot = proof / 'manifest.json'
        shutil.copyfile(manifest, snapshot)
        manifest = snapshot
    data = read(manifest)
    cid = HERE.name + '__' + case
    entry = next(x for x in data['cases'] if x['case_id'] == cid)
    selected = entry if candidate == 'primary' else next(x for x in entry['candidates'] if x['id'] == candidate)
    construction = HERE / selected['construction']
    recipe = ROOT / entry['fixture_recipe']
    compatibility = read(proof / 'compatibility.json')
    processing = read(proof / 'processing.json')
    offline = read(proof / 'offline.log')
    require(offline['offline_passed'] and compatibility['passed'] and processing['passed'],
            'One CPU stage failed')
    require(compatibility['case_id'] == cid and processing['case_id'] == cid and
            compatibility['candidate_id'] == candidate and processing['candidate_id'] == candidate,
            'CPU proof identity differs')
    require(compatibility['construction_sha256'] == selected['construction_sha256'] == sha(construction)
            and processing['native_revision']['construction_sha256'] == sha(construction),
            'CPU proof construction differs')
    require(compatibility['fixture_recipe_sha256'] == sha(recipe), 'Fixture recipe differs')
    require(compatibility['negative_log_sha256'] == sha(proof / 'negative-analysis.log') and
            'Missing required source: raw.json' in (proof / 'negative-analysis.log').read_text(),
            'Missing-source rejection differs')
    require(processing['originals_preserved'] and processing['final_video_checks']['passed'],
            'Saved originals or final video failed')
    result = {'format': 'c111662-current-input-selected-proof-v1', 'case_id': cid,
              'candidate_id': candidate, 'assignment_sha256': sha(ROOT / 'inputs' / HERE.name / 'assignment.json'),
              'manifest': str(manifest.relative_to(HERE)), 'manifest_sha256': sha(manifest),
              'construction': selected['construction'], 'construction_sha256': sha(construction),
              'recipe': entry['fixture_recipe'], 'recipe_sha256': sha(recipe),
              'offline_log_sha256': sha(proof / 'offline.log'),
              'compatibility_sha256': sha(proof / 'compatibility.json'),
              'negative_log_sha256': sha(proof / 'negative-analysis.log'),
              'processing_sha256': sha(proof / 'processing.json'),
              'passed': True, 'scope': 'synthetic CPU diagnostic; no original or legal acceptance'}
    write(proof / 'proof.json', result)
    return {'case': case, 'candidate': candidate,
            'proof': str((proof / 'proof.json').relative_to(HERE)),
            'sha256': sha(proof / 'proof.json')}


def main():
    rows = [bind(case, candidate) for case in CASES for candidate in CANDIDATES]
    matrix = {'format': 'c111662-current-input-proof-matrix-v1', 'assignment_id': HERE.name,
              'candidate_count': len(rows), 'passed': len(rows) == 16, 'entries': rows}
    write(HERE / 'update044-current-proof-matrix.json', matrix)
    pairs = []
    for branch, (left, right) in PAIRS.items():
        for candidate in CANDIDATES:
            l = HERE / 'update044-current-proof' / left / candidate / 'processing.json'
            r = HERE / 'update044-current-proof' / right / candidate / 'processing.json'
            result = audit_pair(l, r, branch, candidate)
            require(result['receipt_sha256'] == [sha(l), sha(r)], 'Pair proof binding differs')
            pairs.append(result)
    pair_matrix = {'format': 'c111662-current-input-pair-audit-v1', 'assignment_id': HERE.name,
                   'pair_count': len(pairs), 'passed': len(pairs) == 8, 'pairs': pairs,
                   'scope': 'synthetic saved pairs only; independent original audit remains'}
    write(HERE / 'update044-current-pair-audit.json', pair_matrix)
    print(json.dumps({'candidate_count': len(rows), 'pair_count': len(pairs),
                      'matrix_sha256': sha(HERE / 'update044-current-proof-matrix.json'),
                      'pair_sha256': sha(HERE / 'update044-current-pair-audit.json')}))


if __name__ == '__main__':
    main()

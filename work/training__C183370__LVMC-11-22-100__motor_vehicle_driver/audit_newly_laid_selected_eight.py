"""Cross-check all eight current-manifest CPU chains and their pair diagnostic."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = ('newly_laid_crossing', 'newly_laid_avoidance')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest_sha = sha(manifest_path)
    manifest = read(manifest_path)
    if len(manifest['cases']) != 12:
        raise ValueError('Twelve selected cases required')
    rows = []
    for short in CASES:
        case_id = HERE.name + '__' + short
        entry = next(row for row in manifest['cases'] if row['case_id'] == case_id)
        for candidate in CANDIDATES:
            selected = entry if candidate == 'primary' else next(
                row for row in entry['candidates'] if row['id'] == candidate)
            path = HERE / f'update142-{short}-{candidate}-proof.json'
            proof = read(path)
            if not (proof['case_id'] == case_id and
                    proof['candidate_id'] == candidate and
                    proof['manifest_sha256'] == manifest_sha and
                    proof['construction_sha256'] == selected['construction_sha256'] and
                    proof['diagnostic_delivery_accepted'] is False and
                    proof['original_native_verified'] is False and
                    proof['synthetic_fixture'] is True):
                raise ValueError('Selected CPU proof differs: ' + short + '/' + candidate)
            for name, digest in proof['logs'].items():
                if sha(HERE / f'update142-{short}-{candidate}-{name}.log') != digest:
                    raise ValueError('Selected chain log changed: ' + short + '/' + candidate)
            rows.append({'case_id': case_id, 'candidate_id': candidate,
                         'proof': path.name, 'proof_sha256': sha(path),
                         'construction_sha256': selected['construction_sha256']})
    pair_path = HERE / 'update142-newly-laid-selected-pair-diagnostic.json'
    pair = read(pair_path)
    if not (pair['manifest_sha256'] == manifest_sha and
            pair['case_ids'] == [HERE.name + '__' + short for short in CASES] and
            pair['observed_contact'] == [True, False] and
            pair['accepted'] is False and pair['diagnostic_only'] is True and
            pair['full_original_context_verified'] is False):
        raise ValueError('Current-hash pair diagnostic differs')
    result = {'format': 'c183370-selected-newly-laid-eight-diagnostic-matrix-v1',
              'manifest_sha256': manifest_sha, 'candidates': rows,
              'passed': len(rows), 'comparison_audit': pair_path.name,
              'comparison_audit_sha256': sha(pair_path),
              'original_native_observed': False,
              'physical_or_legal_acceptance_claimed': False,
              'accepted': False}
    path = HERE / 'update142-newly-laid-selected-eight-matrix.json'
    if path.exists():
        raise ValueError('Preserve prior current-hash matrix')
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'passed': len(rows), 'manifest_sha256': manifest_sha,
                      'matrix_sha256': sha(path), 'accepted': False}, sort_keys=True))


if __name__ == '__main__':
    main()

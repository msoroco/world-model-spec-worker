"""Independently verify exact candidate and source binding of saved-only diagnostics."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    manifest_path = HERE / 'draft-execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    seen = set()
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.rsplit('__', 1)[-1]
        recipe_sha = sha(ROOT / entry['fixture_recipe'])
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            path = HERE / f'current-saved-{suffix}-{candidate}-receipt.json'
            proof = json.loads(path.read_text())
            saved = proof['saved_receipt']
            ref = entry if candidate == 'primary' else next(
                c for c in entry['candidates'] if c['id'] == candidate)
            if (case, candidate) in seen:
                raise ValueError('Duplicate case/candidate')
            seen.add((case, candidate))
            if proof['case_id'] != case or proof['candidate_id'] != candidate or \
               proof['fixture_recipe_sha256'] != recipe_sha or \
               saved['case_id'] != case or saved['candidate_id'] != candidate or \
               saved['native_revision']['construction_sha256'] != ref['construction_sha256']:
                raise ValueError('Saved candidate identity or recipe differs')
            if not saved['passed'] or not saved['recorded_only'] or not saved['originals_preserved'] or \
               saved['missing_evidence'] or saved['physical_acceptance_claimed'] or saved['legal_acceptance_claimed']:
                raise ValueError('Saved proof status or claim invalid')
            if saved['events'] != ['saved_processing_started', 'selected_analysis_executed', 'originals_verified']:
                raise ValueError('Saved event order differs')
            if sha(Path(saved['result'])) != saved['result_sha256']:
                raise ValueError('Saved result changed')
            result = json.loads(Path(saved['result']).read_text())
            if result['case_id'] != case or result.get('accepted') or result.get('legal_verdict_claimed'):
                raise ValueError('Saved result asserts acceptance or wrong identity')
            attempt = ROOT / '.runtime-work' / f'c110812-current-saved-{suffix}-{candidate}' / 'attempt'
            if not attempt.is_dir() or len(saved['original_source_hashes']) < 500:
                raise ValueError('Original source bundle absent')
            for name, digest in saved['original_source_hashes'].items():
                source = attempt / name
                if not source.is_file() or sha(source) != digest:
                    raise ValueError('Original source changed: ' + name)
    if len(seen) != 8:
        raise ValueError('Eight exact saved candidates required')
    print(json.dumps({'passed': True, 'saved_only_candidates': len(seen),
                      'scope': 'synthetic diagnostics; no physical or legal acceptance'}))


if __name__ == '__main__':
    audit()

"""Bind corrected-inventory primary and fallback CPU receipts to exact cases."""
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASES = ('reference', 'contrast', 'divided_reference', 'divided_opening')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def run():
    manifest_path = HERE / 'update046-execution-manifest.json'
    manifest = read(manifest_path)
    entries = []
    for case in CASES:
        entry = next(e for e in manifest['cases'] if e['case_id'].endswith('__' + case))
        for candidate in CANDIDATES:
            proof = HERE / 'update046b-proof' / case / candidate
            mini = read(HERE / f'update046b-manifest-{case}-{candidate}.json')
            mini_entry = next(e for e in mini['cases'] if e['case_id'] == entry['case_id'])
            if candidate == 'primary':
                entry['fixture_recipe'] = mini_entry['fixture_recipe']
            selected = entry if candidate == 'primary' else next(e for e in entry['candidates'] if e['id'] == candidate)
            offline = read(proof / 'offline.log')
            compat = read(proof / 'compatibility.json')
            saved = read(proof / 'processing.json')
            if (offline.get('offline_passed') is not True or compat.get('passed') is not True or
                    saved.get('passed') is not True or compat.get('candidate_id') != candidate or
                    saved.get('candidate_id') != candidate or
                    compat.get('construction_sha256') != selected['construction_sha256'] or
                    saved['native_revision']['construction_sha256'] != selected['construction_sha256'] or
                    compat.get('fixture_recipe_sha256') != sha(ROOT / mini_entry['fixture_recipe']) or
                    compat.get('negative_log_sha256') != sha(proof / 'negative-analysis.log') or
                    compat.get('log_sha256') != sha(proof / 'analysis.log')):
                raise ValueError('Corrected candidate proof differs: ' + case + '/' + candidate)
            selected['offline'] = {
                'command': f'.venv-cpu/bin/python runtime.py offline --manifest work/{HERE.name}/update046b-manifest-{case}-{candidate}.json '
                           f'--case {entry["case_id"]} --candidate {candidate} '
                           f'--output .runtime-work/update045-c111662/{case}/{candidate}/offline '
                           f'--python {ROOT / ".venv-cpu/bin/python"}',
                'exit_code': 0, 'construction_sha256': selected['construction_sha256'],
                'log': str((proof / 'offline.log').relative_to(HERE)),
                'log_sha256': sha(proof / 'offline.log')}
            selected['compatibility'] = {
                'receipt': str((proof / 'compatibility.json').relative_to(HERE)),
                'sha256': sha(proof / 'compatibility.json'),
                'log': str((proof / 'analysis.log').relative_to(HERE)),
                'negative_log': str((proof / 'negative-analysis.log').relative_to(HERE))}
            if candidate == 'primary':
                entry['negative'] = {'log': selected['compatibility']['negative_log']}
            entries.append({'case': case, 'candidate': candidate,
                            'construction_sha256': selected['construction_sha256'],
                            'compatibility_sha256': selected['compatibility']['sha256'],
                            'processing_sha256': sha(proof / 'processing.json')})
    manifest['status'] = 'candidate_proofs_passed_physical_and_semantic_pending'
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    matrix = {'format': 'c111662-inventory-v2-proof-matrix-v1', 'assignment_id': HERE.name,
              'candidate_count': len(entries), 'passed': len(entries) == 16,
              'entries': entries, 'scope': 'synthetic CPU proofs; no original Native or legal verdict'}
    matrix_path = HERE / 'update046b-proof-matrix.json'
    matrix_path.write_text(json.dumps(matrix, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'candidate_count': len(entries), 'matrix_sha256': sha(matrix_path),
                      'manifest_sha256': sha(manifest_path)}))


if __name__ == '__main__':
    run()

"""Bind current-input eight-candidate CPU receipts to exact roundabout cases."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASES = ('reference', 'contrast')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def main():
    path = HERE / 'update048-execution-manifest.json'
    manifest = read(path)
    rows = []
    for case in CASES:
        entry = next(e for e in manifest['cases'] if e['case_id'].endswith('__' + case))
        for candidate in CANDIDATES:
            proof = HERE / 'update048-proof' / case / candidate
            mini = read(HERE / f'update048-manifest-{case}-{candidate}.json')
            mini_entry = next(e for e in mini['cases'] if e['case_id'] == entry['case_id'])
            selected = entry if candidate == 'primary' else next(x for x in entry['candidates'] if x['id'] == candidate)
            off, compat, saved = (read(proof / name) for name in ('offline.log', 'compatibility.json', 'processing.json'))
            if (off.get('offline_passed') is not True or compat.get('passed') is not True or
                    saved.get('passed') is not True or saved.get('missing_evidence') is not False or
                    saved.get('originals_preserved') is not True or
                    compat.get('construction_sha256') != selected['construction_sha256'] or
                    saved['native_revision']['construction_sha256'] != selected['construction_sha256'] or
                    compat.get('fixture_recipe_sha256') != sha(ROOT / mini_entry['fixture_recipe']) or
                    compat.get('negative_log_sha256') != sha(proof / 'negative-analysis.log') or
                    compat.get('log_sha256') != sha(proof / 'analysis.log')):
                raise ValueError('Candidate CPU proof differs: ' + case + '/' + candidate)
            selected['offline'] = {'command': f'.venv-cpu/bin/python runtime.py offline --manifest work/{HERE.name}/update048-manifest-{case}-{candidate}.json --case {entry["case_id"]} --candidate {candidate} --output .runtime-work/update048-c132497/{case}/{candidate}/offline --python {ROOT / ".venv-cpu/bin/python"}',
                                   'exit_code': 0, 'construction_sha256': selected['construction_sha256'],
                                   'log': str((proof / 'offline.log').relative_to(HERE)),
                                   'log_sha256': sha(proof / 'offline.log')}
            selected['compatibility'] = {'receipt': str((proof / 'compatibility.json').relative_to(HERE)),
                                         'sha256': sha(proof / 'compatibility.json'),
                                         'log': str((proof / 'analysis.log').relative_to(HERE)),
                                         'negative_log': str((proof / 'negative-analysis.log').relative_to(HERE))}
            if candidate == 'primary':
                entry['negative'] = {'log': selected['compatibility']['negative_log']}
            rows.append({'case': case, 'candidate': candidate,
                         'construction_sha256': selected['construction_sha256'],
                         'compatibility_sha256': selected['compatibility']['sha256'],
                         'processing_sha256': sha(proof / 'processing.json')})
    manifest['status'] = 'current_input_candidate_and_physical_cpu_proofs_bound'
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    matrix = {'format': 'c132497-current-input-candidate-matrix-v1', 'assignment_id': HERE.name,
              'candidate_count': len(rows), 'passed': len(rows) == 8, 'rows': rows,
              'scope': 'synthetic CPU diagnostics, no original Native or legal acceptance'}
    output = HERE / 'update048-proof-matrix.json'
    output.write_text(json.dumps(matrix, indent=2) + '\n')
    print(json.dumps({'candidate_count': len(rows), 'matrix_sha256': sha(output),
                      'manifest_sha256': sha(path)}))


if __name__ == '__main__':
    main()

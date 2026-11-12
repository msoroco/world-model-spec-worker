"""Run current offline and positive/negative compatibility for eight Walk bundles."""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(tag):
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    validator = ROOT / '.runtime-work/decoder-update015-c10316/.lake/build/bin/adapterCheck'
    if not validator.is_file():
        raise ValueError('Pinned Lean adapter validator absent')
    rows = []
    for case in manifest['cases']:
        suffix = case['case_id'].removeprefix(HERE.name + '__')
        for candidate in (case, *case['candidates']):
            name = candidate.get('id', 'primary')
            construction = HERE / candidate['construction']
            if sha(construction) != candidate['construction_sha256']:
                raise ValueError('Construction hash differs')
            base = ROOT / '.runtime-work' / f'c111256-{tag}-selected-proof' / suffix / name
            if base.exists():
                raise ValueError('Retain prior attempt; choose a fresh proof tag')
            base.parent.mkdir(parents=True, exist_ok=True)
            offline = [sys.executable, str(ROOT / 'runtime.py'), 'offline',
                       '--manifest', str(manifest_path), '--case', case['case_id'],
                       '--candidate', name, '--output', str(base / 'offline'),
                       '--python', sys.executable]
            compatibility = [sys.executable, str(ROOT / 'runtime.py'), 'compatibility',
                             '--manifest', str(manifest_path), '--case', case['case_id'],
                             '--candidate', name, '--output', str(base / 'compatibility'),
                             '--library', str(ROOT / 'runtime/pipeline/library'),
                             '--validator', str(validator)]
            for kind, command in (('offline', offline), ('compatibility', compatibility)):
                run = subprocess.run(command, cwd=ROOT, text=True,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     timeout=600)
                log = HERE / f'{tag}-{suffix}-{name}-{kind}.log'
                log.write_text(run.stdout)
                print(suffix, name, kind, run.returncode, flush=True)
                if run.returncode:
                    raise ValueError(kind + ' failed: ' + run.stdout[-1600:])
                if kind == 'offline':
                    candidate['offline'] = {'command': ' '.join(command),
                        'exit_code': 0, 'construction_sha256': candidate['construction_sha256'],
                        'log': log.name, 'log_sha256': sha(log)}
            destination = HERE / f'{tag}-selected-proofs' / suffix / name
            destination.mkdir(parents=True, exist_ok=True)
            for source, target in (('compatibility.json', 'compatibility.json'),
                                   ('compatibility-analysis.log', 'analysis.log'),
                                   ('negative-analysis.log', 'negative.log')):
                (destination / target).write_bytes((base / 'compatibility' / source).read_bytes())
            receipt = json.loads((destination / 'compatibility.json').read_text())
            if (receipt['passed'] is not True or
                    receipt['construction_sha256'] != candidate['construction_sha256'] or
                    receipt['case_id'] != case['case_id'] or receipt['candidate_id'] != name):
                raise ValueError('Compatibility receipt differs')
            candidate['compatibility'] = {
                'receipt': str((destination / 'compatibility.json').relative_to(HERE)),
                'sha256': sha(destination / 'compatibility.json'),
                'log': str((destination / 'analysis.log').relative_to(HERE)),
                'negative_log': str((destination / 'negative.log').relative_to(HERE))}
            if name == 'primary':
                case['negative'] = {'log': candidate['compatibility']['negative_log']}
            rows.append({'case_id': case['case_id'], 'candidate_id': name,
                         'construction_sha256': candidate['construction_sha256'],
                         'offline_log_sha256': candidate['offline']['log_sha256'],
                         'compatibility_sha256': candidate['compatibility']['sha256']})
            manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    matrix = HERE / f'{tag}-selected-construction-proof-matrix.json'
    matrix.write_text(json.dumps({'format': 'c111256-selected-refreshed-proof-v1',
                                  'rows': rows, 'diagnostic_only': True}, indent=2) + '\n')
    print(json.dumps({'candidates_proven': len(rows), 'matrix_sha256': sha(matrix),
                      'manifest_sha256': sha(manifest_path)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag', required=True)
    main(parser.parse_args().tag)

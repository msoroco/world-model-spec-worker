"""Run exact public positive/missing-source-negative compatibility proofs."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
VARIANTS = ('space_clear', 'space_short', 'grade_clear', 'grade_deficit',
            'trailing_exact', 'trailing_just_short')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(candidate):
    if candidate not in ('primary', 'fallback1'):
        raise ValueError('Exact candidate required')
    manifest = HERE / 'execution-manifest.json'
    root = ROOT / '.runtime-work' / ('c202465-public-' + sha(manifest)[:12])
    root.mkdir(parents=True, exist_ok=True)
    validator = ROOT / '.runtime-work/c179480/decoder/.lake/build/bin/adapterCheck'
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(ROOT / '.runtime-work'),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(ROOT / '.runtime-work/c202465'))
    outcomes = []
    for suffix in VARIANTS:
        case = HERE.name + '__' + suffix
        dest = root / (suffix + '-' + candidate)
        if dest.exists():
            if not (dest / 'compatibility.json').is_file():
                raise ValueError('Retain incomplete public attempt: ' + str(dest))
        else:
            command = [sys.executable, '-B', str(ROOT / 'runtime.py'), 'compatibility',
                       '--manifest', str(manifest), '--case', case, '--output', str(dest),
                       '--library', str(ROOT / 'runtime/library'), '--validator', str(validator),
                       '--candidate', candidate]
            process = subprocess.run(command, cwd=ROOT, env=env,
                                     text=True, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT)
            if process.returncode:
                raise RuntimeError('Public compatibility failed for ' + suffix + '/' + candidate +
                                   ': ' + process.stdout[-1500:])
        proof = HERE / 'proofs' / suffix / ('public-' + candidate)
        proof.mkdir(parents=True, exist_ok=True)
        for name in ('compatibility.json', 'compatibility-analysis.log', 'negative-analysis.log'):
            source = dest / name
            target = proof / ('receipt.json' if name == 'compatibility.json' else name)
            shutil.copyfile(source, target)
            if target.stat().st_size > 2 * 1024 * 1024:
                raise ValueError('Returned proof exceeds 2 MiB: ' + str(target))
            content = target.read_bytes()
            if (content.endswith(b'\n\n') or
                    any(line.rstrip(b' \t\r') != line for line in content.splitlines())):
                raise ValueError('Proof has blank EOF or trailing whitespace')
        receipt = json.loads((proof / 'receipt.json').read_text())
        entry = next(entry for entry in json.loads(manifest.read_text())['cases']
                     if entry['case_id'] == case)
        expected = (entry['construction_sha256'] if candidate == 'primary' else
                    entry['candidates'][0]['construction_sha256'])
        if (receipt.get('passed') is not True or
                receipt.get('candidate_id') != candidate or
                receipt.get('construction_sha256') != expected):
            raise ValueError('Public proof binds another construction')
        outcomes.append({'case_id': case, 'candidate': candidate,
                         'receipt': str((proof / 'receipt.json').relative_to(HERE)),
                         'sha256': sha(proof / 'receipt.json')})
        print(json.dumps(outcomes[-1]), flush=True)
    report = HERE / ('public-' + candidate + '-proof-summary.json')
    report.write_text(json.dumps({'format': 'c202465-public-compatibility-summary',
                                  'manifest_sha256': sha(manifest),
                                  'outcomes': outcomes}, indent=2) + '\n')
    return {'passed': len(outcomes) == len(VARIANTS), 'count': len(outcomes),
            'summary_sha256': sha(report)}


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('usage: public_all.py primary|fallback1')
    print(json.dumps(run(sys.argv[1])))

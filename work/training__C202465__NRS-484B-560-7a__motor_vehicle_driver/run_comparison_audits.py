"""Run paired diagnostic rail comparison audits and source-removal negatives."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AUDIT = HERE / 'comparison_audit.py'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(suffix):
    receipt = json.loads((HERE / 'proofs' / suffix / 'saved-processing.json').read_text())
    stage = Path(receipt['version'])
    return stage.parent.parent / (suffix + '-attempt'), stage / 'processing.json'


def main():
    path = HERE / 'case-plan.json'
    plan = json.loads(path.read_text())
    output = HERE / 'proofs/comparisons'
    output.mkdir(parents=True, exist_ok=True)
    for comparison in plan['comparisons']:
        cid = comparison['comparison_id']
        suffixes = [case.rsplit('__', 1)[1] for case in comparison['case_ids']]
        (a, pa), (b, pb) = (source(suffix) for suffix in suffixes)
        name = cid.rsplit('__', 1)[1]
        result = output / (name + '.json')
        cmd = [sys.executable, '-B', str(AUDIT), '--attempt-a', str(a),
               '--attempt-b', str(b), '--processing-a', str(pa),
               '--processing-b', str(pb), '--output', str(result), '--diagnostic']
        run = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True,
                             env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        positive = output / (name + '-positive.log')
        positive.write_text((run.stdout + run.stderr).rstrip() + '\n')
        if run.returncode:
            raise RuntimeError(f'{name} positive: {run.stderr[-1000:]}')
        bad = REPO / '.runtime-work' / 'c202465-comparison-negative' / name
        if bad.exists():
            shutil.rmtree(bad)
        shutil.copytree(b, bad, copy_function=os.link)
        (bad / 'rail-review/rail-geometry.json').unlink()
        bad_result = REPO / '.runtime-work' / 'c202465-comparison-negative' / (name + '.json')
        bad_cmd = cmd.copy()
        bad_cmd[bad_cmd.index('--attempt-b') + 1] = str(bad)
        bad_cmd[bad_cmd.index('--output') + 1] = str(bad_result)
        failed = subprocess.run(bad_cmd, cwd=REPO, text=True, capture_output=True,
                                env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        negative = output / (name + '-negative.log')
        negative.write_text((failed.stdout + failed.stderr).rstrip() + '\n')
        if failed.returncode == 0 or 'reference rail geometry' not in negative.read_text():
            raise RuntimeError(f'{name} negative did not reject missing rail geometry')
        comparison.update(status='cpu_source_comparison_passed_original_pending',
                          audit=str(positive.relative_to(HERE)),
                          negative_audit=str(negative.relative_to(HERE)),
                          result=str(result.relative_to(HERE)), result_sha256=sha(result))
        print(name, sha(result))
    path.write_text(json.dumps(plan, indent=2) + '\n')
    print('plan', sha(path))


if __name__ == '__main__':
    main()

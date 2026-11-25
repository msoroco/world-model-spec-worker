"""Run exact-case delivery audit positives and synthetic-source negatives."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import delivery_audit


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    out = ROOT / 'native' / 'delivery-cpu'
    out.mkdir(exist_ok=True)
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    selected = [row['case_id'] for row in plan['cases']
                if row['case_id'].startswith(ROOT.name + '__')
                and not row['case_id'].endswith(('exception_2_1', 'exception_2_2'))]
    rows = []
    temp_root = Path(os.environ['TMPDIR'])
    for case in selected:
        suffix = case.split('__')[-1]
        good_log = out / (suffix + '-positive.log')
        good_cmd = [sys.executable, str(ROOT / 'delivery_audit.py'), '--case', case,
                    '--selftest']
        good = subprocess.run(good_cmd, cwd=ROOT, text=True, capture_output=True)
        assert good.returncode == 0 and good.stdout.startswith('PASS ')
        good_log.write_text(good.stdout.rstrip() + '\n')
        with tempfile.TemporaryDirectory(prefix='c146314-delivery-', dir=temp_root) as tmp:
            tmp = Path(tmp)
            attempt, saved = tmp / 'attempt', tmp / 'saved'
            attempt.mkdir()
            saved.mkdir()
            (attempt / 'capture-seal.json').write_text('{"diagnostic_fixture":true}\n')
            (attempt / 'acquisition-provenance.json').write_text('{"provenance_kind":"synthetic_fixture","diagnostic_fixture":true}\n')
            try:
                delivery_audit.validate(case, attempt, saved, tmp / 'pixel-review.json')
                raise AssertionError('Synthetic attempt passed independent audit')
            except ValueError as error:
                assert str(error) == 'Synthetic fixture cannot establish original Native delivery'
        bad_log = out / (suffix + '-negative.log')
        bad_cmd = [sys.executable, str(ROOT / 'delivery_audit.py'), '--case', case,
                   '--negative-selftest']
        bad = subprocess.run(bad_cmd, cwd=ROOT, text=True, capture_output=True)
        assert bad.returncode == 3
        assert bad.stdout.strip() == 'Synthetic fixture cannot establish original Native delivery'
        bad_log.write_text(bad.stdout.rstrip() + '\n')
        rows.append({'case_id': case,
                     'script': 'delivery_audit.py',
                     'script_sha256': sha(ROOT / 'delivery_audit.py'),
                     'positive_command': ' '.join(good_cmd),
                     'positive_exit_code': good.returncode,
                     'positive_log': str(good_log.relative_to(ROOT)),
                     'positive_log_sha256': sha(good_log),
                     'negative_command': ' '.join(bad_cmd),
                     'negative_exit_code': bad.returncode,
                     'negative_log': str(bad_log.relative_to(ROOT)),
                     'negative_log_sha256': sha(bad_log),
                     'physical_delivery_accepted': False})
    result = {'format': 'c146314-delivery-cpu-v1',
              'assignment_id': ROOT.name, 'selected_case_count': len(rows),
              'cases': rows, 'original_native_accepted': False}
    (out / 'checkpoint.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS', len(rows), 'selected exact-case audit identity tests and synthetic rejection')


if __name__ == '__main__':
    main()

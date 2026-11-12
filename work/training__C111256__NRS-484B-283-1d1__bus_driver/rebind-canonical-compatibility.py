"""Recheck all selected candidates after replacing draft cases with canonical cases."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    validator = ROOT / '.runtime-work/decoder-update015-c10316/.lake/build/bin/adapterCheck'
    if not validator.is_file():
        raise ValueError('Pinned validator missing')
    rows = []
    for entry in manifest['cases']:
        suffix = entry['case_id'].removeprefix(HERE.name + '__')
        for candidate_id in ('primary', *(item['id'] for item in entry['candidates'])):
            candidate = entry if candidate_id == 'primary' else next(
                item for item in entry['candidates'] if item['id'] == candidate_id)
            output = ROOT / '.runtime-work/c111256-update018-canonical-compat' / suffix / candidate_id
            command = [sys.executable, str(ROOT / 'runtime.py'), 'compatibility',
                       '--manifest', str(manifest_path), '--case', entry['case_id'],
                       '--candidate', candidate_id, '--output', str(output),
                       '--library', str(ROOT / 'runtime/pipeline/library'),
                       '--validator', str(validator)]
            if not (output / 'compatibility.json').is_file():
                if output.exists():
                    raise ValueError('Partial canonical compatibility attempt exists: ' + str(output))
                run = subprocess.run(command, cwd=ROOT, text=True,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=600)
                command_log = HERE / f'update018-canonical-{suffix}-{candidate_id}-command.log'
                command_log.write_text(run.stdout)
                print(suffix, candidate_id, run.returncode, flush=True)
                if run.returncode:
                    raise ValueError('Canonical compatibility failed: ' + run.stdout[-1500:])
            else:
                print(suffix, candidate_id, 'prior_pass', flush=True)
            destination = HERE / 'update018-selected-proofs' / suffix / candidate_id
            destination.mkdir(parents=True, exist_ok=True)
            for name, target in (('compatibility.json', 'compatibility.json'),
                                 ('compatibility-analysis.log', 'analysis.log'),
                                 ('negative-analysis.log', 'negative.log')):
                (destination / target).write_bytes((output / name).read_bytes())
            candidate['compatibility'] = {
                'receipt': str((destination / 'compatibility.json').relative_to(HERE)),
                'sha256': sha(destination / 'compatibility.json'),
                'log': str((destination / 'analysis.log').relative_to(HERE)),
                'negative_log': str((destination / 'negative.log').relative_to(HERE))}
            if candidate_id == 'primary':
                entry['negative'] = {'log': candidate['compatibility']['negative_log']}
            receipt = json.loads((destination / 'compatibility.json').read_text())
            if (receipt['case_id'] != entry['case_id'] or
                    receipt['candidate_id'] != candidate_id or
                    receipt['construction_sha256'] != candidate['construction_sha256'] or
                    receipt['passed'] is not True):
                raise ValueError('Canonical compatibility identity differs')
            rows.append({'case_id': entry['case_id'], 'candidate_id': candidate_id,
                         'receipt_sha256': candidate['compatibility']['sha256'],
                         'analysis_log_sha256': sha(destination / 'analysis.log'),
                         'negative_log_sha256': sha(destination / 'negative.log')})
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    (HERE / 'update018-canonical-compatibility-matrix.json').write_text(json.dumps({
        'format': 'c111256-canonical-selected-compatibility-v1',
        'manifest_sha256': sha(manifest_path), 'rows': rows,
        'all_diagnostic_only': True}, indent=2) + '\n')
    print(json.dumps({'canonical_compatibility_passed': len(rows),
                      'manifest_sha256': sha(manifest_path),
                      'original_physical_acceptance_claimed': False}))


if __name__ == '__main__':
    main()

"""Bind C110741 canonical selected cases to verified current CPU receipts."""
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUN = ROOT / '.runtime-work/c110741-cutover'
PROOF = HERE / 'current-cutover-proof'
MANIFEST = HERE / 'execution-manifest.json'
STAGED = HERE / 'current-cutover-staging.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def retain(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    if target.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Oversized return: ' + str(target))
    return str(target.relative_to(HERE))


def main():
    manifest = json.loads(STAGED.read_text())
    expected_runtime = sha(ROOT / 'runtime/pipeline/SOURCE-MANIFEST.json')
    if manifest['runtime_manifest_sha256'] != expected_runtime:
        raise ValueError('Staged manifest binds another runtime')
    evidence = {}
    for entry in manifest['cases']:
        case = entry['case_id'].split('__')[-1]
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            selected = entry if candidate == 'primary' else next(
                row for row in entry['candidates'] if row['id'] == candidate)
            target = PROOF / case / candidate
            output = RUN / case / candidate
            if case == 'condition_a' and candidate == 'primary':
                sources = {
                    'offline.log': HERE / 'current-cutover-condition_a-primary-offline.log',
                    'compatibility.log': HERE / 'current-cutover-condition_a-primary-compatibility.log',
                    'saved.log': HERE / 'current-cutover-condition_a-primary-saved.log',
                    'compatibility.json': output / 'compatibility/compatibility.json',
                    'analysis.log': output / 'compatibility/compatibility-analysis.log',
                    'negative-analysis.log': output / 'compatibility/negative-analysis.log',
                    'saved-receipt.json': output / 'saved/v0001/processing.json',
                }
                for name, source in sources.items():
                    retain(source, target / name)
            receipt = json.loads((target / 'compatibility.json').read_text())
            saved = json.loads((target / 'saved-receipt.json').read_text())
            if not (receipt['passed'] is True and receipt['case_id'] == entry['case_id']
                    and receipt['candidate_id'] == candidate
                    and receipt['construction_sha256'] == selected['construction_sha256']
                    and receipt['runtime_manifest_sha256'] == expected_runtime
                    and receipt['log_sha256'] == sha(target / 'analysis.log')
                    and receipt['negative_log_sha256'] == sha(target / 'negative-analysis.log')
                    and saved['passed'] is True and saved['recorded_only'] is True):
                raise ValueError('CPU proof binding failed: ' + case + '/' + candidate)
            selected['offline'] = {
                'command': '.venv-cpu/bin/python runtime.py offline --manifest '
                           + str(STAGED.relative_to(ROOT)) + ' --case '
                           + entry['case_id'] + ' --candidate ' + candidate,
                'exit_code': 0,
                'construction_sha256': selected['construction_sha256'],
                'log': str((target / 'offline.log').relative_to(HERE)),
                'log_sha256': sha(target / 'offline.log'),
            }
            selected['compatibility'] = {
                'receipt': str((target / 'compatibility.json').relative_to(HERE)),
                'sha256': sha(target / 'compatibility.json'),
                'log': str((target / 'analysis.log').relative_to(HERE)),
                'negative_log': str((target / 'negative-analysis.log').relative_to(HERE)),
            }
            if candidate == 'primary':
                entry['negative'] = {'log': selected['compatibility']['negative_log']}
                entry['post_capture']['test_log'] = str((target / 'saved.log').relative_to(HERE))
                entry['post_capture']['test_log_sha256'] = sha(target / 'saved.log')
                entry['post_capture']['test_exit_code'] = 0
            evidence[case + '/' + candidate] = {
                'construction_sha256': selected['construction_sha256'],
                'compatibility_sha256': selected['compatibility']['sha256'],
                'saved_sha256': sha(target / 'saved-receipt.json'),
            }
    manifest['status'] = 'selected_cpu_current_runtime_proven'
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    index = {'format': 'c110741-current-selected-cpu-bind-v1',
             'runtime_manifest_sha256': expected_runtime,
             'execution_manifest_sha256': sha(MANIFEST), 'candidates': evidence,
             'scope': 'synthetic CPU diagnostic only; no Native observation'}
    (PROOF / 'binding-index.json').write_text(json.dumps(index, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'bound': len(evidence), 'manifest_sha256': sha(MANIFEST)}))


if __name__ == '__main__':
    main()

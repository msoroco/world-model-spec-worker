"""Retain exact selected CPU chain receipts for the two newly laid cases."""
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    if len(manifest['cases']) != 12:
        raise ValueError('Expected twelve selected cases')
    for entry in manifest['cases'][-2:]:
        short = entry['case_id'].removeprefix(HERE.name + '__')
        if not short.startswith('newly_laid_'):
            raise ValueError('Selected pair changed')
        entry['acquisition']['pavement_footprint_contact']['entrypoint'] = (
            'native/newly_laid_finalize.py')
        entry['candidate_offline_status'] = 'diagnostic_passed_final_manifest_recheck_pending'
        for candidate in CANDIDATES:
            selected = entry if candidate == 'primary' else next(
                row for row in entry['candidates'] if row['id'] == candidate)
            source = REPO / '.runtime-work' / (
                f'c183370-update141-{short}-{candidate}-compat')
            proof = HERE / f'update141-{short}-{candidate}-proof.json'
            if not proof.is_file():
                raise ValueError('Selected chain missing: ' + str(proof))
            chain = json.loads(proof.read_text())
            if (chain['case_id'] != entry['case_id'] or
                    chain['candidate_id'] != candidate or
                    chain['construction_sha256'] != selected['construction_sha256'] or
                    chain['diagnostic_delivery_accepted'] is not False):
                raise ValueError('Selected chain mismatch: ' + short + '/' + candidate)
            directory = HERE / 'selected-proof-receipts' / short / candidate
            directory.mkdir(parents=True, exist_ok=True)
            for name, retained in (('compatibility.json', 'compatibility.json'),
                                   ('compatibility-analysis.log', 'analysis.log'),
                                   ('negative-analysis.log', 'negative.log')):
                shutil.copy2(source / name, directory / retained)
            receipt = json.loads((directory / 'compatibility.json').read_text())
            if (receipt.get('passed') is not True or
                    receipt['construction_sha256'] != selected['construction_sha256'] or
                    sha(directory / 'analysis.log') != receipt['log_sha256'] or
                    sha(directory / 'negative.log') != receipt['negative_log_sha256']):
                raise ValueError('Compatibility binding mismatch')
            relative = lambda path: str(path.relative_to(HERE))
            spec = {'receipt': relative(directory / 'compatibility.json'),
                    'sha256': sha(directory / 'compatibility.json'),
                    'log': relative(directory / 'analysis.log'),
                    'negative_log': relative(directory / 'negative.log')}
            selected['compatibility'] = spec
            offline = HERE / f'update141-{short}-{candidate}-offline.log'
            saved = HERE / f'update141-{short}-{candidate}-saved.log'
            if not offline.is_file() or not saved.is_file():
                raise ValueError('Offline or saved log missing')
            selected['offline'] = {
                'command': (f'.venv-cpu/bin/python runtime.py offline --manifest '
                            f'work/{HERE.name}/execution-manifest.json --case '
                            f'{entry["case_id"]} --candidate {candidate} '
                            '--output ${OFFLINE_DIR} --python "$PWD/.venv-cpu/bin/python"'),
                'construction_sha256': selected['construction_sha256'],
                'exit_code': 0, 'log': offline.name, 'log_sha256': sha(offline)}
            if candidate == 'primary':
                entry['negative'] = {'log': spec['negative_log'],
                                     'log_sha256': sha(directory / 'negative.log')}
                entry['post_capture']['test_exit_code'] = 0
                entry['post_capture']['test_log'] = saved.name
                entry['post_capture']['test_log_sha256'] = sha(saved)
            print(json.dumps({'case': short, 'candidate': candidate,
                              'source_manifest_sha256': chain['manifest_sha256'],
                              'retained_compatibility_sha256': spec['sha256']}))
    manifest['status'] = 'selected_twelve_cpu_diagnostics_bound_final_hash_recheck_pending'
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'manifest_sha256': sha(MANIFEST),
                      'selected_cases': len(manifest['cases']),
                      'ready': False}))


if __name__ == '__main__':
    main()

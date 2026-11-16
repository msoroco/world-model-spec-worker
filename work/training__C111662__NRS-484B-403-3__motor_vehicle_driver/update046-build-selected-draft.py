"""Normalize each selected bundle's nested draft path without duplicating drafts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = ('reference', 'contrast', 'divided_reference', 'divided_opening')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')
OLD_FINALIZER = "bundle = native_root/('divided-opening' if config['case_suffix'].startswith('divided_') else '')/'drafts'/config['case_suffix']/config['candidate_id']"
NEW_FINALIZER = "bundle = native_root/'selected-draft'/config['case_suffix']"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')


def build():
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    source = HERE / 'native/package-selected-current-input'
    target = HERE / 'native/package-selected-draft-v3'
    for case in CASES:
        entry = next(e for e in manifest['cases'] if e['case_id'].endswith('__' + case))
        for candidate in CANDIDATES:
            bundle = json.loads((source / case / candidate / 'construction.json').read_text())
            old_test = (f"native/'divided-opening'/'drafts'/'{case}'/'{candidate}'" if case.startswith('divided_')
                        else f"native/'drafts'/'{case}'/'{candidate}'")
            new_test = f"native/'selected-draft'/'{case}'"
            count = {'nested': 0, 'finalizer': 0, 'test': 0}
            for item in bundle['files']:
                path = item['path']
                if f'/drafts/{case}/{candidate}/' in path:
                    item['path'] = f'work/{HERE.name}/native/selected-draft/{case}/' + path.rsplit('/', 1)[-1]
                    count['nested'] += 1
                if path == 'finalize_current.py':
                    if OLD_FINALIZER not in item['content']:
                        raise ValueError('Current finalizer nested path changed')
                    item['content'] = item['content'].replace(OLD_FINALIZER, NEW_FINALIZER)
                    count['finalizer'] += 1
                if path.endswith('/native/prove_original_processing.py'):
                    item['content'] = (HERE / 'native/prove_original_processing.py').read_text()
                if path.startswith('tests/') and old_test in item['content']:
                    item['content'] = item['content'].replace(old_test, new_test)
                    count['test'] += 1
            if count['nested'] < 4 or count['finalizer'] != 1 or count['test'] != 1:
                raise ValueError(f'Incomplete selected draft rewrite: {case}/{candidate} {count}')
            output = target / case / candidate / 'construction.json'
            write(output, bundle)
            if output.stat().st_size > 2 * 1024 * 1024:
                raise ValueError('Selected bundle exceeds return cap: ' + str(output))
            ref = entry if candidate == 'primary' else next(e for e in entry['candidates'] if e['id'] == candidate)
            ref['construction'] = str(output.relative_to(HERE))
            ref['construction_sha256'] = sha(output)
            for key in ('offline', 'compatibility'):
                ref.pop(key, None)
        for key in ('offline', 'compatibility', 'negative', 'physical_preparation'):
            entry.pop(key, None)
    manifest['status'] = 'selected_draft_v3_requires_current_runtime_reproof'
    path = HERE / 'update046-execution-manifest.json'
    write(path, manifest)
    print(json.dumps({'candidate_count': 16, 'manifest_sha256': sha(path)}))


if __name__ == '__main__':
    build()

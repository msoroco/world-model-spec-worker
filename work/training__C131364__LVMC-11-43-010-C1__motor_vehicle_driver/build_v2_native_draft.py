"""Bind the current source-checked routes to a Native capture entrypoint draft.

The earlier diagnostic manifest and its passing receipts remain immutable.
This draft requires separate offline/compatibility proof before selection.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DIAGNOSTIC = HERE / 'v2-offline-manifest.json'
OUT = HERE / 'v2-native-draft'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source = json.loads(DIAGNOSTIC.read_text())
    capture_code = (HERE / 'native/v2_native_capture.py').read_text()
    finalizer_code = (HERE / 'native/v2_native_finalize.py').read_text()
    diagnostic_finalizer = (HERE / 'native/v2_finalize.py').read_text()
    OUT.mkdir(exist_ok=True)
    entries = []
    for diagnostic in source['cases']:
        witness = diagnostic['case_id'].rsplit('__', 1)[-1]
        construction = json.loads((HERE / diagnostic['construction']).read_text())
        construction['entrypoint'] = 'runner.py'
        construction['files'] = [item for item in construction['files']
            if item['path'] not in ('runner.py', 'finalize.py', 'v2_finalize.py')]
        construction['files'].append({'path': 'runner.py', 'content': capture_code})
        construction['files'].append({'path': 'finalize.py', 'content': finalizer_code})
        construction['files'].append({'path': 'v2_finalize.py', 'content': diagnostic_finalizer})
        construction['status'] = 'native_execution_draft_unselected'
        path = OUT / (witness + '-construction.json')
        path.write_text(json.dumps(construction, indent=2) + '\n')
        entry = dict(diagnostic)
        entry['kind'] = 'native_execution_draft_unselected'
        entry['construction'] = str(path.relative_to(HERE))
        entry['construction_sha256'] = sha(path)
        entries.append(entry)
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': HERE.name,
        'runtime_manifest_sha256': source['runtime_manifest_sha256'],
        'status': 'native_execution_draft_unselected', 'cases': entries}
    path = HERE / 'v2-native-draft-manifest.json'
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'manifest_sha256': sha(path),
        'construction_sha256': [item['construction_sha256'] for item in entries]}))


if __name__ == '__main__':
    main()

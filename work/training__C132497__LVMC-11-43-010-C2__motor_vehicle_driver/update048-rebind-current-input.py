"""Rebind selected roundabout bundles to the canonical migrated assignment."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASES = ('reference', 'contrast')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')


def main():
    assignment = ROOT / 'inputs' / HERE.name / 'assignment.json'
    plan = HERE / 'case-plan.json'
    source = json.loads(assignment.read_text())
    if source['law']['id'] != source['law_id']:
        raise ValueError('Migrated law identity differs')
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    for case in CASES:
        entry = next(e for e in manifest['cases'] if e['case_id'].endswith('__' + case))
        for candidate in CANDIDATES:
            old = HERE / 'native/package-current' / case / candidate / 'construction.json'
            bundle = json.loads(old.read_text())
            files = {item['path']: item for item in bundle['files']}
            if set(('config.json', 'assignment-source.json', 'case-plan.json', 'check.py')) - set(files):
                raise ValueError('Selected source files missing')
            files['assignment-source.json']['content'] = assignment.read_text()
            files['case-plan.json']['content'] = plan.read_text()
            files['check.py']['content'] = (HERE / 'check.py').read_text()
            config = json.loads(files['config.json']['content'])
            config['assignment_sha256'] = sha(assignment)
            config['case_plan_sha256'] = sha(plan)
            files['config.json']['content'] = json.dumps(config, indent=2) + '\n'
            output = HERE / 'native/package-current-input-v2' / case / candidate / 'construction.json'
            write(output, bundle)
            ref = entry if candidate == 'primary' else next(x for x in entry['candidates'] if x['id'] == candidate)
            ref['construction'] = str(output.relative_to(HERE))
            ref['construction_sha256'] = sha(output)
            ref.pop('offline', None)
            ref.pop('compatibility', None)
        for key in ('offline', 'compatibility', 'negative', 'physical_preparation'):
            entry.pop(key, None)
    manifest['status'] = 'current_input_reproof_in_progress'
    path = HERE / 'update048-execution-manifest.json'
    write(path, manifest)
    print(json.dumps({'assignment_sha256': sha(assignment), 'candidate_count': 8,
                      'manifest_sha256': sha(path)}))


if __name__ == '__main__':
    main()

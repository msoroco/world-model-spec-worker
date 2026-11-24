"""Bind all twelve exact proposal cases to their reviewed CPU delivery entries."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    path = HERE / 'execution-manifest.json'
    manifest = read(path)
    originals = manifest['cases'][:2]
    if any(not x['case_id'].endswith(('probe_1', 'probe_2')) for x in originals):
        raise ValueError('Expected exact original conditional pair')
    others = []
    for name in ('crossref-survey/delivery-entry-draft.json',
                 'crossref-287c-native/delivery-entry-draft.json'):
        draft = read(HERE / name)
        if draft.get('selected') is not False or draft['assignment_id'] != HERE.name:
            raise ValueError('Draft identity or selection changed: ' + name)
        others.extend(draft['cases'])
    cases = originals + others
    expected = {x['case_id'] for x in read(HERE / 'proposals/cases.json')['cases']
                if x['target_type'] != 'baseline'}
    if len(cases) != 12 or {x['case_id'] for x in cases} != expected:
        raise ValueError('Twelve exact proposal cases required')
    manifest['cases'] = cases
    write(path, manifest)
    config_path = HERE / 'config.json'
    config = read(config_path)
    config['supported_case_ids'] = [x['case_id'] for x in cases]
    write(config_path, config)
    construction_path = HERE / 'construction.json'
    construction = read(construction_path)
    files = [x for x in construction['files'] if x['path'] == 'config.json']
    if len(files) != 1:
        raise ValueError('One inline config required')
    files[0]['content'] = config_path.read_text()
    write(construction_path, construction)
    print(json.dumps({'selected_cases': len(cases),
                      'manifest_sha256': sha(path), 'config_sha256': sha(config_path),
                      'root_construction_sha256': sha(construction_path)}))


if __name__ == '__main__':
    main()

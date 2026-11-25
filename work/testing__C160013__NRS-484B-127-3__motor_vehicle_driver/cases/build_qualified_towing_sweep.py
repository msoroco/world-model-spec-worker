"""Build assignment-qualified delivery candidates from proved sweep diagnostics."""
import copy
import hashlib
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
OLD = 'caravan_spacing_towed_physical-'
NEW = PACKAGE.name + '__' + OLD
SOURCE_NAMES = ('caravan_towing_sweep_native.py',
                'caravan_towing_sweep_saved.py',
                'caravan_towing_sweep_finalizer.py')
RENAMED = {name: name.replace('sweep_', 'selected_sweep_') for name in SOURCE_NAMES}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def transform(value):
    if isinstance(value, str):
        return value.replace(OLD, NEW)
    if isinstance(value, list):
        return [transform(item) for item in value]
    if isinstance(value, dict):
        return {key: transform(item) for key, item in value.items()}
    return value


def main():
    for original, selected in RENAMED.items():
        source = PACKAGE / original
        target = PACKAGE / selected
        content = source.read_text().replace(OLD, NEW)
        for old_module, new_module in RENAMED.items():
            content = content.replace(old_module.removesuffix('.py'),
                                      new_module.removesuffix('.py'))
        target.write_text(content)
    source_manifest = json.loads((PACKAGE / 'towing-sweep-diagnostic-manifest.json').read_text())
    selected_manifest = copy.deepcopy(source_manifest)
    selected_manifest['cases'] = []
    selected_manifest['comparisons'] = []
    for old_entry in source_manifest['cases']:
        entry = copy.deepcopy(old_entry)
        entry['case_id'] = entry['case_id'].replace(OLD, NEW)
        entry['kind'] = 'delivery'
        for candidate_id, node in [('primary', entry), ('fallback1', entry['candidates'][0])]:
            source = PACKAGE / node['construction']
            bundle = transform(json.loads(source.read_text()))
            for item in bundle['files']:
                filename = Path(item['path']).name
                if item['path'] == 'tests/test_offline.py':
                    for old_module, new_module in RENAMED.items():
                        item['content'] = item['content'].replace(
                            old_module.removesuffix('.py'),
                            new_module.removesuffix('.py'))
                if filename in RENAMED:
                    renamed = RENAMED[filename]
                    item['path'] = renamed
                    item['source'] = 'work/' + PACKAGE.name + '/' + renamed
                    item['content'] = (PACKAGE / renamed).read_text()
                elif item.get('source'):
                    old_name = Path(item['source']).name
                    if old_name in RENAMED:
                        renamed = RENAMED[old_name]
                        item['source'] = 'work/' + PACKAGE.name + '/' + renamed
                        item['content'] = (PACKAGE / renamed).read_text()
            target = PACKAGE / 'cases' / (entry['case_id'] +
                        ('-fallback1' if candidate_id == 'fallback1' else '') +
                        '-construction.json')
            target.write_text(json.dumps(bundle, indent=2) + '\n')
            node['construction'] = 'cases/' + target.name
            node['construction_sha256'] = sha(target)
            node.pop('offline', None)
            node.pop('compatibility', None)
        entry.pop('saved_processing', None)
        entry.pop('physical_preparation', None)
        selected_manifest['cases'].append(entry)
    target = PACKAGE / 'qualified-towing-sweep-manifest.json'
    target.write_text(json.dumps(selected_manifest, indent=2) + '\n')
    print(json.dumps({'case_ids': [item['case_id'] for item in selected_manifest['cases']],
                      'manifest_sha256': sha(target)}))


if __name__ == '__main__':
    main()

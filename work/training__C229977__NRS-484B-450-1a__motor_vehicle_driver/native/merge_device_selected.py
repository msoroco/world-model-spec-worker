"""Integrate proved officer pair into the canonical current-runtime package."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
SUFFIXES = ('official_device_absent', 'official_device_present')


def merge(target_name, source_name):
    target_path = HERE / target_name
    target = json.loads(target_path.read_text())
    source = json.loads((HERE / source_name).read_text())
    old_ids = {case['case_id'] for case in target['cases']}
    added = {HERE.name + '__' + name for name in SUFFIXES}
    if old_ids & added:
        raise ValueError('Device pair already merged')
    if {case['case_id'] for case in source['cases']} != added:
        raise ValueError('Device source does not contain exact pair')
    if target['runtime_manifest_sha256'] != source['runtime_manifest_sha256']:
        raise ValueError('Device pair binds another runtime')
    target['cases'].extend(source['cases'])
    target_path.write_text(json.dumps(target, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    merge('selected-construction-manifest.json', 'device-construction-manifest.json')
    merge('execution-manifest.json', 'device-execution-manifest.json')

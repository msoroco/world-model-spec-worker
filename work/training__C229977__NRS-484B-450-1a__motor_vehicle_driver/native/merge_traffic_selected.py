"""Add four proved traffic variants without regenerating old stop cases."""
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent.parent


def merge(target_name, source_name):
    target_path = FOLDER / target_name
    target = json.loads(target_path.read_text())
    source = json.loads((FOLDER / source_name).read_text())
    old_ids = {case['case_id'] for case in target['cases']}
    if old_ids != {FOLDER.name + '__probe_1', FOLDER.name + '__probe_2'}:
        raise ValueError('Canonical stop cases changed before traffic merge')
    add_ids = {case['case_id'] for case in source['cases']}
    if add_ids != {FOLDER.name + '__traffic_conflict_absent',
                   FOLDER.name + '__traffic_conflict_present'}:
        raise ValueError('Traffic source does not contain exact pair')
    if target['runtime_manifest_sha256'] != source['runtime_manifest_sha256']:
        raise ValueError('Traffic proof bound another runtime')
    target['cases'].extend(source['cases'])
    target_path.write_text(json.dumps(target, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    merge('selected-construction-manifest.json',
          'traffic-construction-manifest.json')
    merge('execution-manifest.json', 'traffic-execution-manifest.json')

"""Bind the linked mounted-obey case to the tested 600-frame runner."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def main():
    turn = json.loads((HERE / 'draft-thirty-second-mounted-turn-primary-construction.json').read_text())
    obey = copy.deepcopy(turn)
    case_id = HERE.name + '__controlled_1'
    obey['case_id'] = case_id
    for part in obey['files']:
        if part['path'] == 'config.json':
            config = json.loads(part['content'])
            config['case_id'] = case_id
            config['selected_case_id'] = case_id
            config['supported_case_ids'] = [HERE.name + '__controlled_' + str(i)
                                            for i in (1, 2, 3)]
            config['case'] = {'case_id': case_id}
            config['case_suffix'] = 'mounted_obey'
            part['content'] = json.dumps(config, indent=2) + '\n'
    target = HERE / 'draft-thirty-second-mounted-obey-primary-construction.json'
    write(target, obey)
    manifest_path = HERE / 'draft-thirty-second-execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    entry = next(case for case in manifest['cases'] if case['case_id'] == case_id)
    entry['construction'] = target.name
    entry['construction_sha256'] = sha(target)
    turn_entry = next(case for case in manifest['cases'] if case['case_id'].endswith('__controlled_2'))
    turn_entry['construction_sha256'] = sha(HERE / 'draft-thirty-second-mounted-turn-primary-construction.json')
    write(manifest_path, manifest)
    print(json.dumps({'case_id': case_id, 'construction_sha256': sha(target),
                      'manifest_sha256': sha(manifest_path)}))


if __name__ == '__main__':
    main()

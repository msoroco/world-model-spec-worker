"""Copy historical draft bundles into current-input selected constructions."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    prior = HERE / 'update042-pre-rebind-manifest.json'
    if prior.exists():
        raise ValueError('Historical selected manifest already retained')
    prior.write_bytes(manifest_path.read_bytes())
    input_path = ROOT / 'inputs' / HERE.name / 'assignment.json'
    current = sha(input_path)
    changed = []
    for entry in manifest['cases']:
        suffix = entry['case_id'].removeprefix(HERE.name + '__')
        for candidate in (entry, *entry['candidates']):
            ident = candidate.get('id', 'primary')
            old_path = HERE / candidate['construction']
            old = json.loads(old_path.read_text())
            config_entry = next(item for item in old['files'] if item['path'] == 'config.json')
            config = json.loads(config_entry['content'])
            rows = [item for item in config['frozen_source_hashes']
                    if item['path'] == 'inputs/' + HERE.name + '/assignment.json']
            if len(rows) != 1:
                raise ValueError('One current frozen assignment source required')
            previous = rows[0]['sha256']
            if previous == current:
                raise ValueError('Expected an old input-bound construction to rebind')
            rows[0]['sha256'] = current
            config_entry['content'] = json.dumps(config, indent=2, ensure_ascii=False) + '\n'
            new_path = HERE / 'selected-candidates' / suffix / ident / 'construction.json'
            new_path.parent.mkdir(parents=True, exist_ok=True)
            if new_path.exists():
                raise ValueError('Selected construction already exists: ' + str(new_path))
            new_path.write_text(json.dumps(old, indent=2, ensure_ascii=False) + '\n')
            candidate['construction'] = new_path.relative_to(HERE).as_posix()
            candidate['construction_sha256'] = sha(new_path)
            candidate.pop('offline', None)
            candidate.pop('compatibility', None)
            changed.append({'case_id': entry['case_id'], 'candidate_id': ident,
                            'prior_input_sha256': previous, 'current_input_sha256': current,
                            'construction_sha256': candidate['construction_sha256']})
        for key in ('offline', 'compatibility', 'negative', 'physical_preparation',
                    'delivery_acceptance', 'post_capture'):
            entry.pop(key, None)
    manifest['status'] = 'selected_current_input_reproof_pending'
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    output = HERE / 'update042-current-input-rebind.json'
    output.write_text(json.dumps({'format': 'c111294-current-input-rebind-v1',
                                  'source_assignment_sha256': current,
                                  'historical_manifest': prior.name,
                                  'historical_manifest_sha256': sha(prior),
                                  'selected_constructions': changed,
                                  'current_manifest_sha256': sha(manifest_path),
                                  'original_recordings_accepted': 0}, indent=2) + '\n')
    print(json.dumps({'constructions_rebound': len(changed),
                      'current_input_sha256': current,
                      'manifest_sha256': sha(manifest_path),
                      'receipt_sha256': sha(output)}))


if __name__ == '__main__':
    main()

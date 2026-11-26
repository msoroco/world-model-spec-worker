"""Expose the selected bicycle statutory alternative as canonical root files."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    source = ROOT / 'draft-bicycle/bicycle_pass_wide/primary/construction.json'
    construction = json.loads(source.read_text())
    config_file = next(item for item in construction['files'] if item['path'] == 'config.json')
    config = json.loads(config_file['content'])
    config['supported_case_ids'] = [ROOT.name + '__' + suffix for suffix in
        ('bicycle_pass_wide', 'electric_bicycle_pass_wide', 'electric_bicycle_pass_narrow')]
    config_file['content'] = json.dumps(config, indent=2) + '\n'
    (ROOT / 'construction.json').write_text(json.dumps(construction, indent=2) + '\n')
    for item in construction['files']:
        path = ROOT / item['path']
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(item['content'])
    print(json.dumps({'root_case_id': construction['case_id'],
                      'materialized_files': len(construction['files'])}))


if __name__ == '__main__':
    main()

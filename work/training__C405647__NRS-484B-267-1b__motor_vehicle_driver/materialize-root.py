"""Materialize a canonical root implementation from the selected primary bundle."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    source = HERE / 'current-bundles/reference/primary/construction.json'
    construction = json.loads(source.read_text())
    cases = [HERE.name + '__reference', HERE.name + '__contrast']
    for item in construction['files']:
        if item['path'] == 'config.json':
            config = json.loads(item['content'])
            config['supported_case_ids'] = cases
            item['content'] = json.dumps(config, indent=2) + '\n'
        target = HERE / item['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(item['content'])
    (HERE / 'construction.json').write_text(json.dumps(construction, indent=2) + '\n')
    print(json.dumps({'materialized_files': len(construction['files']),
                      'root_case': construction['case_id'],
                      'supported_cases': cases}))


if __name__ == '__main__':
    main()

"""Materialize a canonical root implementation from the selected primary bundle."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    source = HERE / 'current-witness-bundles/witness_1/primary/construction.json'
    construction = json.loads(source.read_text())
    cases = [HERE.name + '__' + s for s in ('witness_1', 'witness_2', 'exception_1_1', 'exception_1_2', 'official_1', 'official_2')]
    for item in construction['files']:
        if item['path'] == 'config.json':
            config = json.loads(item['content'])
            config['supported_case_ids'] = cases
            for camera in config['cameras']:
                camera['fov_deg'] = {'overview': 80, 'approach': 70, 'reference_corner': 90, 'driver_reference': 105}[camera['name']]
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

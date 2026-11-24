"""Return the first selected case as a root executable and the paired case separately."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def main():
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    selected = [x['case_id'] for x in manifest['cases']]
    assert len(selected) == 2
    for suffix in ('probe_a', 'probe_b'):
        bundle = json.loads((HERE / f'current-v2-{suffix}-primary-construction.json').read_text())
        target = HERE if suffix == 'probe_a' else HERE / 'cases/probe_b'
        if suffix == 'probe_a':
            for item in bundle['files']:
                if item['path'] == 'config.json':
                    config = json.loads(item['content'])
                    config['supported_case_ids'] = selected
                    for camera in config['cameras']:
                        camera['pose_strategy'] = 'fixed_world_intersection_view_from_cameras_py'
                        camera['fov_deg'] = 90
                    item['content'] = json.dumps(config, indent=2) + '\n'
        for item in bundle['files']:
            write(target / item['path'], item['content'])
        write(target / 'construction.json', json.dumps(bundle, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'root_case': selected[0], 'paired_case': selected[1]}))


if __name__ == '__main__':
    main()

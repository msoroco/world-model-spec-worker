"""Build unselected 30-second witness primaries from existing exact drafts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    original = json.loads((HERE / 'draft-execution-manifest.json').read_text())
    manifest = {**original, 'format': 'worker-unselected-30s-primary-manifest-v1',
                'status': 'draft_not_selected', 'cases': []}
    for entry in original['cases']:
        case = entry['case_id']
        suffix = case.rsplit('__', 1)[-1]
        source = HERE / entry['construction']
        construction = json.loads(source.read_text())
        for item in construction['files']:
            if item['path'] == 'config.json':
                config = json.loads(item['content'])
                config['duration_s'] = 30
                config['engineering_knobs']['duration_s'] = 30.0
                for channel in config['recording_description']['channels']:
                    channel['time_window'] = 'original 30 s / 600 frame attempt'
                item['content'] = json.dumps(config, indent=2) + '\n'
            elif item['path'] in ('runner.py', 'finalize.py', 'measure_park.py'):
                item['content'] = (HERE / 'native' / item['path']).read_text()
            elif item['path'] == 'tests/test_bundle_finalize.py':
                text = (HERE / 'native/test_bundle_finalize.py').read_text()
                text = text.replace('range(480)', 'range(600)').replace('i>=400', 'i>=500')
                item['content'] = text.replace('measure_case_sources(root)', 'measure_case_sources(root, 600)')
        for channel in construction['recording_description']['channels']:
            channel['time_window'] = 'original 30 s / 600 frame attempt'
        construction['static_checks'] = [s.replace('480-frame', '600-frame') for s in construction['static_checks']]
        construction['termination_rules'] = [s.replace('480 original frames', '600 original frames')
                                             for s in construction['termination_rules']]
        output = HERE / 'draft-30s-primaries' / suffix / 'construction.json'
        write(output, construction)
        manifest['cases'].append({**entry, 'construction': str(output.relative_to(HERE)),
                                  'construction_sha256': digest(output), 'candidates': []})
    manifest_path = HERE / 'draft-30s-primary-manifest.json'
    write(manifest_path, manifest)
    print(json.dumps({'cases': len(manifest['cases']), 'manifest_sha256': digest(manifest_path)}))


if __name__ == '__main__':
    main()

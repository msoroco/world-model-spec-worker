"""Select the source-bound 30-second pair without changing its authored motion."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'current-30s-compatibility-manifest.json'
OUT = HERE / 'selected-30s'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n', encoding='utf-8')


def main():
    manifest = json.loads(SOURCE.read_text())
    selected = []
    for case in manifest['cases']:
        copied = dict(case)
        for candidate in [copied, *copied['candidates']]:
            source = HERE / candidate['construction']
            assert sha(source) == candidate['construction_sha256']
            bundle = json.loads(source.read_text())
            config_file = next(item for item in bundle['files'] if item['path'] == 'config.json')
            config = json.loads(config_file['content'])
            assert config['case_id'] == case['case_id']
            config['selected_case_id'] = case['case_id']
            config['case'] = {'case_id': case['case_id']}
            config['required_atoms'] = []
            config['source_packets'] = []
            config['cameras'] = [
                {'name': name, 'width': 1920 if name == 'overview' else 1280,
                 'height': 1080 if name == 'overview' else 720,
                 'pose_strategy': 'source-bound runner.py',
                 'fov_deg': config['policy']['camera_fov_deg']}
                for name in ('overview', 'approach', 'reference_corner', 'driver_reference')]
            config_file['content'] = json.dumps(config, sort_keys=True, indent=2) + '\n'
            bundle['status'] = 'selected_delivery_construction'
            target = OUT / case['case_id'].rsplit('__', 1)[-1] / candidate['id'] / 'construction.json'
            write(target, bundle)
            candidate['construction'] = target.relative_to(HERE).as_posix()
            candidate['construction_sha256'] = sha(target)
        copied['kind'] = 'delivery'
        selected.append(copied)
    result = {'format': 'worker-execution-manifest',
              'assignment_id': manifest['assignment_id'],
              'status': 'selected_cpu_proofs_pending',
              'runtime_manifest_sha256': manifest['runtime_manifest_sha256'],
              'cases': selected, 'delivery_ready': False,
              'original_native_observed': False}
    write(HERE / 'selected-30s-draft-execution-manifest.json', result)
    print(json.dumps({'cases': len(selected), 'selected_constructions': 6,
                      'manifest_sha256': sha(HERE / 'selected-30s-draft-execution-manifest.json')}))


if __name__ == '__main__':
    main()

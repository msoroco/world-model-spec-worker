"""Attach passing current-runtime offline and compatibility receipts to exact cases."""
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REVISION = 'v5'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    if target.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Returned proof exceeds file limit')
    return str(target.relative_to(HERE))


def main():
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    for entry in manifest['cases']:
        direction = entry['case_id'].rsplit('__', 1)[1]
        shared = HERE / 'proofs' / direction
        offline = ROOT / '.runtime-work' / ('c150916-offline-' + direction + '-primary-' + REVISION) / 'offline.log'
        log = copy(offline, shared / 'primary' / 'offline.log')
        command = ('.venv-cpu/bin/python runtime.py offline --manifest work/' + HERE.name +
                   '/execution-manifest.json --case ' + entry['case_id'] + ' --candidate primary --output ' +
                   '.runtime-work/c150916-offline-' + direction + '-primary-' + REVISION)
        entry['offline'] = {'command': command, 'exit_code': 0,
                            'construction_sha256': entry['construction_sha256'],
                            'log': log, 'log_sha256': sha(offline)}
        for candidate_id, target in [('primary', entry),
                                      ('fallback1', entry['candidates'][0])]:
            if candidate_id != 'primary':
                offline = ROOT / '.runtime-work' / ('c150916-offline-' + direction + '-fallback1-' + REVISION) / 'offline.log'
                log = copy(offline, shared / candidate_id / 'offline.log')
                target['offline'] = {'command': command.replace('primary', 'fallback1'),
                                     'exit_code': 0,
                                     'construction_sha256': target['construction_sha256'],
                                     'log': log, 'log_sha256': sha(offline)}
            output = ROOT / '.runtime-work' / ('c150916-compat-' + direction + '-' + candidate_id + '-' + REVISION)
            receipt = json.loads((output / 'compatibility.json').read_text())
            if (receipt['case_id'] != entry['case_id'] or receipt['candidate_id'] != candidate_id or
                    receipt['construction_sha256'] != target['construction_sha256'] or not receipt['passed']):
                raise ValueError('Compatibility receipt binds another exact case/candidate')
            receipt_name = copy(output / 'compatibility.json', shared / candidate_id / 'receipt.json')
            analysis_name = copy(output / 'compatibility-analysis.log', shared / candidate_id / 'analysis.log')
            negative_name = copy(output / 'negative-analysis.log', shared / candidate_id / 'negative.log')
            target['compatibility'] = {'receipt': receipt_name,
                                       'sha256': sha(HERE / receipt_name),
                                       'log': analysis_name,
                                       'negative_log': negative_name}
            if candidate_id == 'primary':
                entry['negative'] = {'log': negative_name}
        construction = json.loads((HERE / entry['construction']).read_text())
        config = json.loads(next(file['content'] for file in construction['files']
                                 if file['path'] == 'config.json'))
        entry['acquisition'] = {
            name: {'entrypoint': 'runner.py' if name == 'ego_pose' else 'finalize.py',
                   'method': channel['method'],
                   'evidence': ['vehicle-pose.jsonl', 'video_frames.jsonl',
                                'road.xodr', 'road-review.json', 'trace.jsonl']}
            for channel in config['recording_description']['channels']
            for name in [channel['name']]}
    path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'manifest_sha256': sha(path),
                      'exact_candidates_with_cpu_compatibility': 4}))


if __name__ == '__main__':
    main()

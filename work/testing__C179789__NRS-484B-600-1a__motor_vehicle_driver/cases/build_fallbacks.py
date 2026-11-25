"""Build and offline-check one lead-spawn fallback for each exact case."""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    path = ROOT / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].split('__')[-1]
        source = json.loads((ROOT / entry['construction']).read_text())
        road = next(item for item in source['files'] if item['path'] == 'road_packet.json')
        packet = json.loads(road['content'])
        packet['lead_spawn']['x'] += 2
        road['content'] = json.dumps(packet, indent=2) + '\n'
        source['candidate_rationale'] = ('If original Native lead spawn fails or overlaps traffic, '
                                         'move the lead two metres forward on the same reviewed lane.')
        target = ROOT / 'cases' / (suffix + '-fallback1-construction.json')
        target.write_text(json.dumps(source, indent=2) + '\n')
        folder = REPO / '.runtime-work' / ('c179789-fallback-' + suffix)
        folder.mkdir(parents=True, exist_ok=True)
        local = folder / 'manifest.json'
        local.write_text(json.dumps({'cases': [{'case_id': entry['case_id'],
                                               'construction': 'construction.json',
                                               'construction_sha256': sha(target)}]}, indent=2) + '\n')
        (folder / 'construction.json').write_bytes(target.read_bytes())
        output = folder / ('offline-' + sha(target)[:12])
        command = ['.venv-cpu/bin/python', 'runtime.py', 'offline', '--manifest',
                   local.relative_to(REPO).as_posix(), '--case', entry['case_id'],
                   '--output', output.relative_to(REPO).as_posix()]
        log = ROOT / 'cases' / (suffix + '-fallback1-offline.log')
        with log.open('w') as stream:
            result = subprocess.run(command, cwd=REPO, stdout=stream,
                                    stderr=subprocess.STDOUT, check=False)
        print(suffix, result.returncode, flush=True)
        if result.returncode:
            raise ValueError('Fallback offline failed: ' + suffix)
        entry['candidate_risk'] = {
            'status': 'physical',
            'reason': 'Original Native lead spawn or body gap can fail on the reviewed lane.'}
        entry['candidates'] = [{
            'id': 'fallback1', 'construction': target.relative_to(ROOT).as_posix(),
            'construction_sha256': sha(target),
            'trigger': {'source': 'original Native spawn status and joined body-gap history',
                        'metric': 'lead spawn success and positive body gap',
                        'failure_condition': 'Lead fails to spawn or overlaps ego at initial frame'},
            'changed_knobs': ['road_packet.lead_spawn.x'],
            'offline': {'command': ' '.join(command), 'exit_code': 0,
                        'construction_sha256': sha(target),
                        'log': log.relative_to(ROOT).as_posix(), 'log_sha256': sha(log)}}]
    path.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    build()

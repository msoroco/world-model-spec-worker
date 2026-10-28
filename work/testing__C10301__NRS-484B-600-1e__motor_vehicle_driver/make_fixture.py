"""Adapt pinned retained three-frame acquisition for software compatibility only."""
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
BASE = REPO / 'work/_shared/fixtures/base-v3'
DEST = ROOT / 'fixture-diagnostic'


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main():
    shutil.copytree(BASE, DEST)
    trace = rows(DEST / 'trace.jsonl')
    evidence = rows(DEST / 'capture/evidence.jsonl')
    channels = DEST / 'channels'
    channels.mkdir()
    for name in ('kin.speed', 'kin.velocity', 'kin.position', 'ru.subject'):
        with (channels / (name + '.jsonl')).open('x') as stream:
            for state, packet in zip(trace, evidence):
                original_subject = next(a for a in packet['original_observations']['participants']
                                        if a['actor_id'] == packet['actor_id'])
                values = {'kin.speed': state['speed_mps'],
                          'kin.velocity': state['velocity_mps'],
                          'kin.position': state['position_m'],
                          'ru.subject': {'actor_id': packet['actor_id'],
                                         'blueprint': original_subject['blueprint'],
                                         'role_name': 'subject'}}
                stream.write(json.dumps({'time_s': state['time_s'],
                                         'value': values[name]}) + '\n')
    provenance = json.loads((DEST / 'fixture-provenance.json').read_text())
    provenance['diagnostic_adaptations'] = [
        'Four channels are copied from original trace/evidence values before bundled analysis.',
        'The three-frame retained straight-road source is not the authored C10301 corridor.',
        'No 80 mph speed, full route, highway status, camera visibility, or physical cause is established.']
    (DEST / 'fixture-provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
    print(json.dumps({'fixture': str(DEST.relative_to(REPO)), 'frames': len(trace),
                      'scope': 'software compatibility only'}))


if __name__ == '__main__':
    main()

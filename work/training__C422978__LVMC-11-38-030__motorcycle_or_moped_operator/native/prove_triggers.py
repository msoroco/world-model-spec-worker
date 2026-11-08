"""Retain synthetic trigger/non-trigger saved packets for all fallbacks."""
import copy
import json
from pathlib import Path

from triggers import evaluate, sha

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / 'trigger-fixtures'


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + '\n')


def saved(case):
    path = HERE / 'drafts' / case / 'primary' / 'requested-tracks.jsonl'
    source = [json.loads(line) for line in path.read_text().splitlines()]
    result = []
    for row in source:
        x, y = row['requested_center_xy_m']
        result.append({'frame': row['frame'], 'time_s': row['time_s'],
                       'source_kind': 'synthetic_cpu', 'motorcycle_blueprint': row['motorcycle_blueprint'],
                       'center_xy_m': [x, y], 'speed_mps': row['requested_speed_mps'],
                       'body_xy_m': [[x + dx, y + dy] for dx, dy in
                                     ((-1.1, -.4), (-1.1, .4), (1.1, -.4), (1.1, .4))]})
    return result


def set_y(row, y):
    delta = y - row['center_xy_m'][1]
    row['center_xy_m'][1] = y
    for vertex in row['body_xy_m']:
        vertex[1] = round(vertex[1] + delta, 4)


def prove():
    receipts = []
    for case in ('witness_1', 'witness_2'):
        original = saved(case)
        for candidate in ('fallback1', 'fallback2', 'fallback3'):
            for name in ('trigger', 'nontrigger'):
                packet = copy.deepcopy(original)
                if candidate == 'fallback1':
                    if case == 'witness_1' and name == 'trigger':
                        for row in packet[100:111]: set_y(row, -4.5)
                    if case == 'witness_2' and name == 'trigger':
                        for row in packet[:121]: set_y(row, -1.75)
                if candidate == 'fallback2':
                    if case == 'witness_1' and name == 'trigger':
                        for row in packet[100:111]: set_y(row, -2.8)
                    if case == 'witness_2' and name == 'trigger':
                        for row in packet[:161]: set_y(row, -1.75)
                folder = FIXTURES / case / candidate / name
                folder.mkdir(parents=True, exist_ok=True)
                saved_path = folder / 'actor-frames.jsonl'
                saved_path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in packet))
                visibility = None
                if candidate == 'fallback3':
                    video = folder / 'synthetic-camera.txt'
                    video.write_text('synthetic diagnostic camera source for '+case+' '+name+'\n')
                    visibility = folder / 'visibility.json'
                    write(visibility, {'case_suffix': case, 'source_kind': 'synthetic_cpu',
                                       'video_path': video.name,
                                       'video_sha256': sha(video),
                                       'visible_fraction': .6 if name == 'trigger' else .9})
                result = evaluate(case, candidate, packet, visibility)
                if result['triggered'] != (name == 'trigger'):
                    raise ValueError('Synthetic trigger split differs: '+case+' '+candidate+' '+name)
                receipt = {'case_suffix': case, 'candidate_id': candidate,
                           'fixture': name, 'saved_sha256': sha(saved_path),
                           'visibility_sha256': sha(visibility) if visibility else None,
                           'result': result}
                receipts.append(receipt)
                write(folder / 'result.json', receipt)
    bad = FIXTURES / 'witness_2/fallback3/trigger/visibility.json'
    packet = json.loads(bad.read_text())
    packet['video_sha256'] = '0' * 64
    write(FIXTURES / 'negative-visibility.json', packet)
    try:
        evaluate('witness_2', 'fallback3', saved('witness_2'),
                 FIXTURES / 'negative-visibility.json')
    except ValueError as error:
        if str(error) != 'Camera source hash differs': raise
    else:
        raise ValueError('Changed camera source hash accepted')
    changed_body = saved('witness_2')
    changed_body[80]['body_xy_m'][0][1] -= 3
    try:
        evaluate('witness_2', 'fallback1', changed_body)
    except ValueError as error:
        if str(error) != 'Saved motorcycle body/center differs': raise
    else:
        raise ValueError('Changed motorcycle body accepted')
    output = {'format': 'c422978-synthetic-trigger-proof-v1',
              'manifest_sha256': sha(HERE / 'drafts/manifest.json'),
              'trigger_code_sha256': sha(HERE / 'triggers.py'),
              'rows': receipts, 'changed_camera_source_negative': 'Camera source hash differs',
              'changed_motorcycle_body_negative': 'Saved motorcycle body/center differs',
              'original_native_or_legal_outcome_claimed': False}
    write(HERE / 'trigger-proof.json', output)
    return output


if __name__ == '__main__':
    print(json.dumps({'rows': len(prove()['rows'])}))

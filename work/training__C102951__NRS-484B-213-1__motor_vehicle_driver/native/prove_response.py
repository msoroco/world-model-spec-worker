"""Retained synthetic passing response positives and source-corruption negatives."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from measure_response import measure_response

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row, sort_keys=True)+'\n' for row in rows))


def reaction_fixture():
    source = HERE/'saved-fixtures'/'170'
    folder = HERE/'response-fixtures'/'reaction-170'
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source/'road-readback.json', folder/'road-readback.json')
    rows = load_rows(source/'native-observed.jsonl')
    for actor, initial_speed, reduction, direction in (
            ('oncoming', 12.0, 4.0, -1), ('overtaken', 8.0, 4.0, 1)):
        speed_key, x_key = actor+'_speed_mps', actor+'_x_m'
        for i in range(len(rows)):
            progress = max(0, min(1, (i-55)/20))
            rows[i][speed_key] = round(initial_speed-reduction*progress, 4)
            if i:
                rows[i][x_key] = round(rows[i-1][x_key]+direction*rows[i][speed_key]/20, 4)
    write_rows(folder/'native-observed.jsonl', rows)
    return folder


def rejected(folder, alter, wrong_hash=False):
    with tempfile.TemporaryDirectory(dir=HERE) as temporary:
        copy = Path(temporary)/'saved'
        shutil.copytree(folder, copy)
        alter(copy)
        try:
            if wrong_hash:
                measure_response(copy, {'native-observed.jsonl': '0'*64,
                                        'road-readback.json': sha(copy/'road-readback.json')})
            else:
                measure_response(copy)
        except (ValueError, TypeError):
            return True
        raise AssertionError('Changed saved response accepted')


def prove():
    fixtures = []
    for distance in (70, 120, 170):
        folder = HERE/'saved-fixtures'/str(distance)
        result = measure_response(folder)
        if any(result['response'][actor]['maximum_left_phase_speed_drop_mps'] != 0 or
               result['response'][actor]['five_frame_hard_deceleration_count'] != 0
               for actor in ('oncoming', 'overtaken')):
            raise AssertionError('Constant-speed synthetic baseline differs')
        fixtures.append({'distance_m': distance, 'variant': 'constant_speed',
                         'source_hashes': result['source_hashes'],
                         'measurement': result})
    folder = reaction_fixture()
    result = measure_response(folder)
    if (result['response']['oncoming']['maximum_left_phase_speed_drop_mps'] != 4 or
            result['response']['overtaken']['maximum_left_phase_speed_drop_mps'] != 4 or
            any(result['response'][actor]['five_frame_hard_deceleration_count'] == 0
                for actor in ('oncoming', 'overtaken'))):
        raise AssertionError('Synthetic two-vehicle reaction not measured')
    fixtures.append({'distance_m': 170, 'variant': 'two_vehicle_slowdown',
                     'source_hashes': result['source_hashes'],
                     'measurement': result})
    def mutate_rows(copy, change):
        path = copy/'native-observed.jsonl'
        rows = load_rows(path)
        change(rows)
        write_rows(path, rows)
    negatives = [
        {'mutation': 'changed_saved_source_hash',
         'rejected': rejected(folder, lambda copy: None, wrong_hash=True)},
        {'mutation': 'negative_oncoming_speed',
         'rejected': rejected(folder, lambda copy: mutate_rows(
             copy, lambda rows: rows[60].update(oncoming_speed_mps=-1)))},
        {'mutation': 'missing_frame',
         'rejected': rejected(folder, lambda copy: mutate_rows(
             copy, lambda rows: rows.pop()))},
        {'mutation': 'altered_frame_time',
         'rejected': rejected(folder, lambda copy: mutate_rows(
             copy, lambda rows: rows[60].update(time_s=99)))},
    ]
    proof = {'format': 'c102951-saved-response-proof-v1',
             'assignment_id': HERE.parent.name,
             'processor_sha256': sha(HERE/'measure_response.py'),
             'pass_processor_sha256': sha(HERE/'measure_pass.py'),
             'fixtures': fixtures, 'negative_controls': negatives,
             'original_native_observed': False,
             'caused_by_passing_judgment': None,
             'interference_judgment': None,
             'legal_verdict': None, 'delivery_ready': False}
    (HERE/'response-proof.json').write_text(json.dumps(proof, indent=2)+'\n')
    return proof


if __name__ == '__main__':
    result = prove()
    print(json.dumps({'positives': len(result['fixtures']),
                      'negatives': len(result['negative_controls'])}))

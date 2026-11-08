"""Retain a saved synthetic comparison with altered-source negative controls."""
import json
from pathlib import Path
import shutil
import tempfile

from compare_saved import compare, sha

HERE = Path(__file__).resolve().parent


def load(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def write(path, rows):
    path.write_text(''.join(json.dumps(row, sort_keys=True)+'\n' for row in rows))


def prove():
    first, second = (HERE/'saved-fixtures'/case for case in ('designated', 'opposite'))
    positive = compare(first, second)
    if (positive['source_kind'] != 'synthetic_cpu' or positive['paired_frames'] != 240 or
            positive['designated_measurement']['signed_ego_displacement_m'] != 95.6 or
            positive['opposite_measurement']['signed_ego_displacement_m'] != -95.6):
        raise AssertionError('Saved synthetic comparison differs')
    negatives = []
    for mutation in ('road_bytes', 'designation_bytes', 'speed', 'time', 'lane', 'mirror'):
        with tempfile.TemporaryDirectory(dir=HERE) as temporary:
            altered = Path(temporary)/'opposite'
            shutil.copytree(second, altered)
            if mutation in ('road_bytes', 'designation_bytes'):
                name = 'road-readback.json' if mutation == 'road_bytes' else 'designation-record.json'
                path = altered/name
                path.write_bytes(path.read_bytes()+b' ')
            else:
                path = altered/'native-observed.jsonl'
                data = load(path)
                key, value = {'speed': ('ego_speed_mps', 9),
                              'time': ('time_s', 9),
                              'lane': ('lane_id', -2),
                              'mirror': ('ego_x_m', 99)}[mutation]
                data[60][key] = value
                write(path, data)
            try:
                compare(first, altered)
            except (ValueError, TypeError, KeyError):
                negatives.append({'mutation': mutation, 'rejected': True})
            else:
                raise AssertionError('Altered saved comparison accepted: '+mutation)
    proof = {'format': 'c150916-saved-comparison-proof-v1',
             'assignment_id': HERE.parent.name,
             'processor_sha256': sha(HERE/'compare_saved.py'),
             'positive': positive, 'negative_controls': negatives,
             'original_native_observed': False, 'accepted_comparison': False,
             'delivery_ready': False}
    (HERE/'saved-comparison-proof.json').write_text(json.dumps(proof, indent=2)+'\n')
    return proof


if __name__ == '__main__':
    result = prove()
    print(json.dumps({'paired_frames': result['positive']['paired_frames'],
                      'negatives': len(result['negative_controls'])}))

"""Independent saved-pair audit with replayed comparison negatives."""
import json
from pathlib import Path
import shutil
import tempfile

from compare_saved import compare, sha
from prove_saved_comparison import load, write

HERE = Path(__file__).resolve().parent


def audit():
    path = HERE/'saved-comparison-proof.json'
    proof = json.loads(path.read_text())
    expected = ['road_bytes', 'designation_bytes', 'speed', 'time', 'lane', 'mirror']
    if (proof['format'] != 'c150916-saved-comparison-proof-v1' or
            proof['assignment_id'] != HERE.parent.name or
            proof['processor_sha256'] != sha(HERE/'compare_saved.py') or
            [row['mutation'] for row in proof['negative_controls']] != expected or
            not all(row['rejected'] is True for row in proof['negative_controls']) or
            proof['original_native_observed'] or proof['accepted_comparison'] or
            proof['delivery_ready']):
        raise ValueError('Saved comparison proof provenance differs')
    first, second = (HERE/'saved-fixtures'/case for case in ('designated', 'opposite'))
    forward, reverse = (load(folder/'native-observed.jsonl') for folder in (first, second))
    if (len(forward) != 240 or len(reverse) != 240 or
            (first/'road-readback.json').read_bytes() != (second/'road-readback.json').read_bytes() or
            (first/'designation-record.json').read_bytes() != (second/'designation-record.json').read_bytes()):
        raise ValueError('Independent saved fixed source differs')
    for i, (a, b) in enumerate(zip(forward, reverse)):
        t = (i+1)/20
        if (a['frame'] != i or b['frame'] != i or
                abs(a['time_s']-t) > 1e-6 or b['time_s'] != a['time_s'] or
                a['native_frame'] != b['native_frame'] or
                a['ego_speed_mps'] != b['ego_speed_mps'] or
                a['ego_y_m'] != b['ego_y_m'] or a['lane_id'] != b['lane_id'] or
                a['ego_heading_deg'] != 0 or b['ego_heading_deg'] != 180 or
                abs(a['ego_x_m']+b['ego_x_m']-200) > 1e-4 or
                abs(a['ego_velocity_x_mps']+b['ego_velocity_x_mps']) > 1e-4):
            raise ValueError('Independent saved pair row differs')
    measured = compare(first, second, proof['positive']['source_hashes'])
    if measured != proof['positive']:
        raise ValueError('Saved comparison metric differs')
    replayed = []
    for mutation in expected:
        with tempfile.TemporaryDirectory(dir=HERE) as temporary:
            folder = Path(temporary)/'opposite'
            shutil.copytree(second, folder)
            if mutation in ('road_bytes', 'designation_bytes'):
                name = 'road-readback.json' if mutation == 'road_bytes' else 'designation-record.json'
                target = folder/name
                target.write_bytes(target.read_bytes()+b' ')
            else:
                target = folder/'native-observed.jsonl'
                data = load(target)
                key, value = {'speed': ('ego_speed_mps', 9),
                              'time': ('time_s', 9),
                              'lane': ('lane_id', -2),
                              'mirror': ('ego_x_m', 99)}[mutation]
                data[60][key] = value
                write(target, data)
            try:
                compare(first, folder)
            except (ValueError, TypeError, KeyError):
                replayed.append(mutation)
            else:
                raise ValueError('Independent saved comparison negative accepted')
    receipt = {'format': 'c150916-independent-saved-comparison-audit-v1',
               'proof_sha256': sha(path), 'paired_rows_checked': 480,
               'negative_controls_replayed': replayed,
               'original_native_observed': False, 'accepted_comparison': False,
               'delivery_ready': False}
    (HERE/'saved-comparison-audit.json').write_text(json.dumps(receipt, indent=2)+'\n')
    return receipt


if __name__ == '__main__':
    print(json.dumps(audit()))

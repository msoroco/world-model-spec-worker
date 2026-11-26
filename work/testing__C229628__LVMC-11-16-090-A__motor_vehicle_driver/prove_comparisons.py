"""Exercise every fixed aid/contest comparison with marked synthetic records."""
import hashlib
import json
from pathlib import Path

from comparison_audit import DIFFERENCES, audit
from contest_aid import CASES, SOURCE_FIELDS
from package_spec import AID

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c229628-comparisons-v1'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def scene(case):
    value = {'cell_id': 'C229628', 'actor': 'motor_vehicle_driver',
             'municipal_jurisdiction': True, 'highway': case.highway,
             'candidate_contest': case.candidate_contest, 'cue': case.cue,
             'ego_person_id': 'fixture-ego-person',
             'other_person_id': 'fixture-other-person',
             'ego_vehicle_id': 'fixture-ego-vehicle',
             'other_vehicle_id': 'fixture-other-vehicle',
             'ego_route_xy': [[0., 0.], [100., 0.]],
             'other_route_xy': [[0., 3.], [100., 3.]],
             'lane_marking_xy': [[0., 1.5], [100., 1.5]],
             'cue_frame': 100, 'other_start_frame': 120}
    value.update({name + '_source_sha256': hashlib.sha256(name.encode()).hexdigest()
                  for name in SOURCE_FIELDS})
    return value


def make(case):
    folder = SCRATCH / case.name
    if folder.exists():
        raise ValueError('retain prior comparison fixture')
    folder.mkdir(parents=True)
    s = scene(case)
    rows = []
    for i in range(900):
        row = {'original_frame': i, 'native_frame': 5000 + i,
               'time_s': i / 20, 'native_time_s': i / 20,
               'ego_xy': [i / 10, 0.], 'other_xy': [i / 10, 3.],
               'ego_speed_mps': 2.0,
               'other_speed_mps': 0.0 if i < 120 else 2.0,
               'ego_accel_mps2': 0., 'other_accel_mps2': 0.,
               'cue_observed': bool(case.cue and i == 100),
               'highway': case.highway,
               'candidate_contest': case.candidate_contest}
        row.update({name: s[name] for name in
                    ('ego_person_id', 'other_person_id', 'ego_vehicle_id', 'other_vehicle_id')})
        row.update({name: s[name] for name in s if name.endswith('_source_sha256')})
        rows.append(row)
    packet = {'assignment_id': AID, 'case_id': AID + '__' + case.name,
              'scene': s, 'frames': rows}
    packet_path = folder / 'contest-packet.json'
    packet_path.write_text(json.dumps(packet, separators=(',', ':')) + '\n')
    (folder / 'original-source-receipt.json').write_text(json.dumps({
        'source_kind': 'synthetic_diagnostic_fixture',
        'diagnostic_fixture': True, 'case_id': packet['case_id'],
        'packet_sha256': sha(packet_path)}, separators=(',', ':')) + '\n')
    return folder


def run():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    folders = {case.name: make(case) for case in CASES}
    for name, (left, right, _) in DIFFERENCES.items():
        result = audit(name, folders[left], folders[right], diagnostic=True)
        (HERE / ('proof-comparison-' + name + '.log')).write_text(
            json.dumps(result, indent=2) + '\n')
        changed = json.loads((folders[right] / 'contest-packet.json').read_text())
        changed['scene']['ego_person_id'] = 'changed-person'
        target = SCRATCH / (name + '-changed')
        target.mkdir()
        packet = target / 'contest-packet.json'
        packet.write_text(json.dumps(changed, separators=(',', ':')) + '\n')
        receipt = json.loads((folders[right] / 'original-source-receipt.json').read_text())
        receipt['packet_sha256'] = sha(packet)
        (target / 'original-source-receipt.json').write_text(json.dumps(receipt) + '\n')
        try:
            audit(name, folders[left], target, diagnostic=True)
        except ValueError as exc:
            if 'fixed comparison condition changed' not in str(exc):
                raise
        else:
            raise ValueError('independent comparison accepted changed person')
        (HERE / ('proof-comparison-negative-' + name + '.log')).write_text(
            'rejected changed fixed person in comparison ' + name + '\n')
    return len(DIFFERENCES)


if __name__ == '__main__':
    print('independent comparison CPU proofs:', run())

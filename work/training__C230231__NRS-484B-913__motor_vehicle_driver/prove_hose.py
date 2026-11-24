"""Source-shaped four-case CPU proof and missing-source rejections."""
import hashlib
import json
from pathlib import Path
import tempfile

from measure_hose import CAMERAS, FRAMES, measure, sha

CASE = Path(__file__).resolve().parent
ROOT = CASE.parents[1]


def fixture(folder, suffix):
    folder.mkdir(parents=True)
    case_id = CASE.name + '__' + suffix
    consent = None
    if suffix == 'exception_1_2':
        consent = {'type': 'recorded_radio', 'official_in_command_id': 'command-1',
                   'vehicle_case_id': case_id, 'permission': 'drive_over_hose'}
    hose = {'case_id': case_id, 'way_kind': 'highway', 'purpose': 'practice_run',
            'department_hose_source': 'asset_inventory',
            'cover_inventory_source': 'asset_inventory',
            'cover_or_ramp_present': False,
            'hose_centerline_xy_m': [[0, -4], [0, 4]], 'hose_radius_m': .1,
            'official_in_command_id': 'command-1', 'consent_record': consent}
    (folder / 'hose-source.json').write_text(json.dumps(hose) + '\n')
    with (folder / 'actor-sources.jsonl').open('x') as actors, \
         (folder / 'camera-frames.jsonl').open('x') as cameras:
        for frame in range(FRAMES):
            x = -5 + min(frame, 250) * .04
            y = 7 if suffix == 'witness_1' else 0
            body = [[x-.8, y-.8], [x+.8, y-.8], [x+.8, y+.8], [x-.8, y+.8]]
            actors.write(json.dumps({'case_id': case_id, 'frame': frame,
                'time_s': frame / 20, 'ego_speed_mps': .8 if frame <= 250 else 0,
                'ego_footprint_xy_m': body}, sort_keys=True) + '\n')
            for name in CAMERAS:
                digest = hashlib.sha256(f'{case_id}:{frame}:{name}'.encode()).hexdigest()
                cameras.write(json.dumps({'frame': frame, 'camera': name,
                    'rgb_sha256': digest}, sort_keys=True) + '\n')
    return case_id


def prove():
    scratch = ROOT / '.runtime-work' / 'c230231-913'
    scratch.mkdir(parents=True, exist_ok=True)
    entries = []
    with tempfile.TemporaryDirectory(dir=scratch) as tmp:
        for suffix in ('witness_1', 'witness_2', 'exception_1_1', 'exception_1_2'):
            folder = Path(tmp) / suffix
            case_id = fixture(folder, suffix)
            result = measure(folder, case_id)
            assert (result['driven_hose_overlap_frames'] > 0) == (suffix != 'witness_1')
            assert result['consent_documented_from_command_official'] == (True if suffix == 'exception_1_2' else None)
            assert result['hose_unprotected_per_source']
            assert result['legal_verdict'] is None and not result['original_native_observed']
            rejected = []
            for name in ('actor-sources.jsonl', 'camera-frames.jsonl'):
                path = folder / name
                original = path.read_text()
                path.write_text('\n'.join(original.splitlines()[:-1]) + '\n')
                try:
                    measure(folder, case_id)
                except ValueError as error:
                    rejected.append(str(error))
                path.write_text(original)
            assert len(rejected) == 2
            entries.append({'case_id': case_id, 'measurement': result,
                            'negative_rejections': rejected})
    receipt = {'format': 'c230231-hose-cpu-proof-v1',
               'assignment_sha256': sha(ROOT / 'inputs' / CASE.name / 'assignment.json'),
               'case_plan_sha256': sha(CASE / 'case-plan.json'),
               'measurement_module_sha256': sha(CASE / 'measure_hose.py'),
               'entries': entries, 'passed': True,
               'original_native_observed': False, 'delivery_ready': False}
    path = CASE / 'offline' / 'hose-source-proof.json'
    path.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'passed': True, 'cases': len(entries), 'negative_rejections': 8}))


if __name__ == '__main__':
    prove()

"""Source-shaped physical and lifecycle CPU fixtures; never original Native proof."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def assess(rows, inventory, expected_inside):
    if len(rows) != 600 or [r.get('video_frame') for r in rows] != list(range(600)):
        return 'unverified'
    if any(not isinstance(r.get('vehicle_xyz_m'), list) or
           len(r['vehicle_xyz_m']) < 2 or
           not isinstance(r.get('bbox_half_length_m'), (int, float)) or
           not isinstance(r.get('bbox_half_width_m'), (int, float)) or
           not isinstance(r.get('time_s'), (int, float))
           for r in rows):
        return 'unverified'
    region = inventory['trail_right_of_way_m']
    overlap = []
    for row in rows:
        x, y = row['vehicle_xyz_m'][:2]
        hx, hy = row['bbox_half_length_m'], row['bbox_half_width_m']
        overlap.append(x + hx >= region['min_x'] and x - hx <= region['max_x']
                       and y + hy >= region['min_y'] and y - hy <= region['max_y'])
    progress = rows[-1]['vehicle_xyz_m'][0] - rows[0]['vehicle_xyz_m'][0]
    return 'met' if progress > 10 and any(overlap) == expected_inside else 'not_met'


def one(suffix, kind, output):
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entry = next(e for e in manifest['cases'] if e['case_id'].endswith('__' + suffix))
    source = HERE / 'diagnostic-source' / suffix
    pose_path = source / 'vehicle-poses.jsonl'
    rows = [json.loads(line) for line in pose_path.read_text().splitlines()]
    inventory_path = source / 'trail-inventory.json'
    inventory = json.loads(inventory_path.read_text())
    base = {'case_id': entry['case_id'],
            'construction_sha256': entry['construction_sha256'],
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
            'original_native_observed': False, 'physical_acceptance_claimed': False,
            'legal_verdict_claimed': False}
    if kind == 'lifecycle':
        base.update(events=EVENTS, exit_code=0,
                    premature_saved_processing_rejected=True,
                    note='CPU ordering fixture; operator release remains unverified for Native capture')
    else:
        if kind == 'incomplete_motion':
            first = rows[0]['vehicle_xyz_m'][0]
            for row in rows:
                row['vehicle_xyz_m'][0] = first
        if kind == 'missing_evidence':
            rows.pop()
        status = assess(rows, inventory, suffix != 'outside')
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if status != expected:
            raise ValueError('Physical fixture differs: ' + suffix + '/' + kind + '/' + status)
        base.update(physical_checks={'maneuver': {
            'status': status,
            'method': '600 source-shaped original-frame body footprints, trail corridor and route progress; engineering criterion only',
            'sources': {'vehicle-poses.jsonl': sha(pose_path),
                        'trail-inventory.json': sha(inventory_path)}}},
            maneuver_completed=status == 'met',
            realized_observables={'route_progress_m':
                                  rows[-1]['vehicle_xyz_m'][0] - rows[0]['vehicle_xyz_m'][0]}
            if status == 'met' else {})
    write(output, base)
    print(json.dumps({'case_id': entry['case_id'], 'kind': kind,
                      'status': base.get('physical_checks', {}).get('maneuver', {}).get('status')}))


def build():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        folder = HERE / 'physical-proof' / suffix
        folder.mkdir(parents=True, exist_ok=True)
        refs = []
        for kind in (*KINDS, 'lifecycle'):
            output = folder / (kind + '.json')
            log = folder / (kind + '.log')
            command = [sys.executable, '-B', str(Path(__file__).resolve()),
                       '--case', suffix, '--kind', kind, '--output', str(output)]
            completed = subprocess.run(command, cwd=HERE.parents[1],
                                       capture_output=True, text=True, timeout=30)
            log.write_text((completed.stdout + completed.stderr).rstrip() + '\n')
            if completed.returncode:
                raise ValueError('Physical fixture failed: ' + str(log))
            refs.append({'kind': kind, 'command': ' '.join(command),
                         'exit_code': 0, 'log': str(log.relative_to(HERE)),
                         'log_sha256': sha(log), 'result': str(output.relative_to(HERE)),
                         'result_sha256': sha(output)})
        life = json.loads((folder / 'lifecycle.json').read_text())
        proof = {'format': 'c143691-trail-physical-cpu-v1',
                 'case_id': entry['case_id'],
                 'construction_sha256': entry['construction_sha256'],
                 'fixtures': refs[:3],
                 'lifecycle': {**life, 'log': refs[3]['log'],
                               'log_sha256': refs[3]['log_sha256']},
                 'diagnostic_only': True, 'original_native_observed': False}
        write(folder / 'proof.json', proof)
        entry['physical_preparation'] = {
            'receipt': str((folder / 'proof.json').relative_to(HERE)),
            'sha256': sha(folder / 'proof.json')}
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'physical_fixture_cases': len(manifest['cases'])}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--case')
    parser.add_argument('--kind', choices=(*KINDS, 'lifecycle'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.build:
        build()
    elif args.case and args.kind and args.output:
        one(args.case, args.kind, args.output)
    else:
        parser.error('Choose --build or one fixture')

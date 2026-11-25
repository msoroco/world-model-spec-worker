"""Source-shaped CPU proof of the parking completion decision and lifecycle order.

These outcomes are synthetic diagnostics, never original Native acceptance.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from prove_alley import sample

HERE = Path(__file__).resolve().parent
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def classify(rows, evidence_present):
    if not evidence_present or not rows or len(rows) != 600:
        return 'unverified', {}, 'source-shaped pose or frame evidence missing'
    if any(row['native_frame'] != 100 + i or abs(row['time_s'] - i / 20) > 1e-6
           for i, row in enumerate(rows)):
        return 'unverified', {}, 'source-shaped frame/time join invalid'
    if any(abs((rows[i]['subject']['xy_m'][0] - rows[i - 1]['subject']['xy_m'][0])
               - rows[i]['subject']['speed_mps'] / 20) > .02
           for i in range(1, len(rows))):
        return 'unverified', {}, 'source-shaped speed/position motion differs'
    stationary = [i for i, row in enumerate(rows)
                  if row['subject']['speed_mps'] <= .1]
    runs = []
    for i in stationary:
        if not runs or i != runs[-1][-1] + 1:
            runs.append([i])
        else:
            runs[-1].append(i)
    longest = max(runs, key=len, default=[])
    movement_before = bool(longest) and any(
        row['subject']['speed_mps'] >= 1 for row in rows[:longest[0]])
    observed = {'stationary_frames': len(longest),
                'stationary_duration_s': len(longest) / 20,
                'movement_before_stationary': movement_before,
                'first_stationary_frame': longest[0] if longest else None}
    status = 'met' if movement_before and len(longest) >= 40 else 'not_met'
    return status, observed, 'source-shaped 20 Hz pose speed and approach sequence'


def lifecycle(events):
    if events != EVENTS:
        raise ValueError('Saved processing began before Native ownership closed')
    return {'events': events, 'exit_code': 0}


def main():
    root = HERE / 'physical-proof'
    root.mkdir(exist_ok=True)
    manifest = json.loads((HERE / 'draft-alley-manifest.json').read_text())
    for entry in manifest['cases']:
        case_id = entry['case_id']
        suffix = case_id.rsplit('__', 1)[-1]
        width = {'controlled_1': 7.5, 'controlled_at_10': 6.648,
                 'controlled_2': 6.0}[suffix]
        case_dir = root / suffix
        case_dir.mkdir(exist_ok=True)
        fixtures = []
        for kind in KINDS:
            packet, inventory = sample(width)
            rows = packet['frames']
            evidence_present = kind != 'missing_evidence'
            if kind == 'incomplete_motion':
                for i in range(220, 500):
                    rows[i]['subject']['speed_mps'] = 2.0
            x = 0.0
            for i, row in enumerate(rows):
                if i:
                    x += row['subject']['speed_mps'] / 20
                row['subject']['xy_m'][0] = round(x, 6)
                row['other']['xy_m'][0] = 20.0
            status, observed, method = classify(rows, evidence_present)
            expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                        'missing_evidence': 'unverified'}[kind]
            if status != expected:
                raise ValueError(f'{kind} classified {status}, expected {expected}')
            source_hashes = {'synthetic_pose_packet': digest(packet),
                             'synthetic_alley_inventory': digest(inventory)}
            result = {'case_id': case_id, 'provenance_kind': 'synthetic_fixture',
                      'diagnostic_fixture': True, 'accepted': False,
                      'legal_verdict_claimed': False,
                      'maneuver_completed': status == 'met',
                      'physical_checks': {'maneuver': {'status': status,
                                                       'method': method,
                                                       'sources': source_hashes}},
                      'realized_observables': observed if status == 'met' else {}}
            result_path = case_dir / f'{kind}.json'
            result_path.write_text(json.dumps(result, indent=2) + '\n')
            log_path = case_dir / f'{kind}.log'
            log_path.write_text(json.dumps({'kind': kind, 'status': status,
                                            'observed': observed,
                                            'source_hashes': source_hashes},
                                           sort_keys=True) + '\n')
            fixtures.append({'kind': kind,
                             'command': f'.venv-cpu/bin/python {HERE.relative_to(HERE.parents[1])}/prove_physical.py',
                             'exit_code': 0,
                             'log': str(log_path.relative_to(HERE)),
                             'log_sha256': hashlib.sha256(log_path.read_bytes()).hexdigest(),
                             'result': str(result_path.relative_to(HERE)),
                             'result_sha256': hashlib.sha256(result_path.read_bytes()).hexdigest()})
        try:
            lifecycle(EVENTS[:-2] + EVENTS[-1:])
        except ValueError:
            pass
        else:
            raise ValueError('Premature saved processing accepted')
        life = lifecycle(EVENTS)
        life_log = case_dir / 'lifecycle.log'
        life_log.write_text(json.dumps({'passed': True, 'events': EVENTS,
                                        'negative_premature_processing_rejected': True}) + '\n')
        life['log'] = str(life_log.relative_to(HERE))
        life['log_sha256'] = hashlib.sha256(life_log.read_bytes()).hexdigest()
        proof = {'case_id': case_id,
                 'construction_sha256': entry['construction_sha256'],
                 'scope': 'synthetic source-shaped CPU proof only',
                 'fixtures': fixtures, 'lifecycle': life}
        (case_dir / 'proof.json').write_text(json.dumps(proof, indent=2) + '\n')
        print(suffix, [(f['kind'], json.loads((HERE / f['result']).read_text())['physical_checks']['maneuver']['status']) for f in fixtures])


if __name__ == '__main__':
    main()

"""Run exact-case original-shaped CPU physical and lifecycle fixtures."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

from prove_turn_physical import write
from turn_physical_probe import assess
from worker_exchange.native_output import seal_capture

ROOT = Path(__file__).resolve().parent

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--case', required=True)
    p.add_argument('--kind', required=True,
                   choices=('complete_motion', 'incomplete_motion', 'missing_evidence', 'lifecycle'))
    p.add_argument('--output', required=True)
    a = p.parse_args()
    suffix = a.case.split('__')[-1]
    output = Path(a.output)
    if output.exists():
        raise ValueError('Retain prior exact physical fixture output')
    output.mkdir(parents=True)
    construction = ROOT / 'cases' / f'construction-{suffix}-primary.json'
    selected = json.loads(construction.read_text())
    (output / 'construction.json').write_bytes(construction.read_bytes())
    (output / 'runner.py').write_text(next(f['content'] for f in selected['files'] if f['path'] == selected['entrypoint']))
    if a.kind == 'lifecycle':
        (output / 'trace.jsonl').write_text('{"frame":0,"time_s":0}\n')
        (output / 'video_frames.jsonl').write_text('{"video_frame":0,"carla_frame":0,"time_s":0}\n')
        try:
            seal_capture(output, frames=1, restoration={'restored': False},
                         errors=[], encoder_exit_codes={'overview': 0})
        except ValueError as error:
            if 'verified restoration' not in str(error):
                raise
        else:
            raise ValueError('Premature Native seal was accepted')
        seal = seal_capture(output, frames=1, restoration={'restored': True},
                            errors=[], encoder_exit_codes={'overview': 0})
        print(json.dumps({'case_id': a.case,
                          'events': seal['events'] + ['native_exit', 'owner_released', 'saved_processing_started'],
                          'premature_seal_rejected': True,
                          'seal_sha256': sha256((output / 'capture-seal.json').read_bytes()).hexdigest(),
                          'fixture_scope': 'synthetic lifecycle protocol; no Native capture'}, indent=2))
        return
    positions = [(.5,-2),(.5,-1),(-1,0)] if a.kind == 'complete_motion' else [(.5,-2)] * 3
    write(output, a.case, positions)
    if a.kind == 'missing_evidence':
        (output / 'body_footprints.jsonl').unlink()
        check = {'status': 'unverified', 'method': 'Required original body source absent',
                 'sources': {'video_frames.jsonl': sha256((output/'video_frames.jsonl').read_bytes()).hexdigest()},
                 'intervals': [], 'missing_evidence': ['body_footprints.jsonl']}
    else:
        check = assess(output, a.case)
    expected = {'complete_motion':'met','incomplete_motion':'not_met','missing_evidence':'unverified'}[a.kind]
    if check['status'] != expected:
        raise ValueError('Source assessment status differs')
    result = {'case_id': a.case, 'physical_checks': {'maneuver': check},
        'maneuver_completed': expected == 'met',
        'realized_observables': {'original_body_displacement_m': check['details']['body_center_displacement_m']} if expected == 'met' else {},
        'provenance_kind': 'native' if expected == 'met' else 'synthetic_fixture',
        'diagnostic_fixture': True,
        'fixture_scope': 'Synthetic original-shaped CPU protocol only; no CARLA turn or physical acceptance',
        'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}
    destination = ROOT / 'physical' / f'{suffix}-{a.kind}-result.json'
    destination.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'case_id': a.case, 'kind': a.kind, 'status': expected,
                      'result': str(destination), 'fixture_scope': result['fixture_scope']}, indent=2))

if __name__ == '__main__':
    main()

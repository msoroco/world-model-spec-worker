"""Exercise diagnostic motion outcomes without making a Native or legal claim."""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def classify(trace, evidence, graphs, provenance):
    sources = ['trace.jsonl', 'capture/evidence.jsonl',
               'capture/native/graphs/base', 'acquisition-provenance.json']
    check = {'status': 'unverified',
             'method': '600 source-joined 20 Hz samples, consistent integrated pose and velocity, 30 s route and measurable forward response',
             'sources': sources}
    observed = {}
    try:
        if provenance.get('provenance_kind') != 'synthetic_fixture' or not provenance.get('diagnostic_fixture'):
            raise ValueError('Fixture identity absent')
        if len(trace) != 600 or len(evidence) != 600 or len(graphs) != 600:
            raise ValueError('Full trace/evidence/graph span absent')
        for index, (row, event, graph) in enumerate(zip(trace, evidence, graphs)):
            frame = 1000 + index
            if row['frame'] != frame or row['native_frame'] != frame or row['video_frame'] != index:
                raise ValueError('Frame identity differs')
            if abs(row['time_s'] - index / 20) > 1e-7 or event['original_frame'] != frame:
                raise ValueError('Time or evidence join differs')
            x = row['position_m'][0]
            if not math.isfinite(x) or abs(x - row['position']['x']) > 1e-5:
                raise ValueError('Position fields disagree')
            if abs(x - event['ego']['position_m'][0]) > 1e-5:
                raise ValueError('Evidence position differs')
            if abs(x - graph['nodes'][0]['attributes']['vertex'][0]) > 1e-5:
                raise ValueError('Graph position differs')
            if abs(x - event['world']['road_projection']['s_m']) > 1e-5:
                raise ValueError('Road projection differs')
            if abs(x - sum(v[0] for v in event['ego']['body_vertices_m']) / 8) > 1e-5:
                raise ValueError('Evidence body differs')
            if abs(x - sum(v[0] for v in graph['nodes'][0]['attributes']['threedbbox']) / 8) > 1e-5:
                raise ValueError('Graph body differs')
            vx = row['velocity_mps'][0]
            if not math.isfinite(vx) or abs(vx - row['speed_mps']) > 1e-5:
                raise ValueError('Velocity and speed differ')
            if abs(vx - event['ego']['speed_mps']) > 1e-5 or abs(vx / .44704 - row['speed_mph']) > 1e-4:
                raise ValueError('Evidence speed differs')
            if index and abs(x - trace[index - 1]['position_m'][0] -
                             (vx + trace[index - 1]['velocity_mps'][0]) / 40) > 0.01:
                raise ValueError('Velocity and integrated position differ')
        displacement = trace[-1]['position_m'][0] - trace[0]['position_m'][0]
        speed_increase = trace[-1]['velocity_mps'][0] - trace[0]['velocity_mps'][0]
        observed = {'forward_displacement_m': displacement,
                    'speed_increase_mps': speed_increase, 'source_frames': 600}
        check['status'] = 'met' if displacement >= 30 and speed_increase >= 1 else 'not_met'
    except (KeyError, IndexError, TypeError, ValueError):
        pass
    return {'physical_checks': {'maneuver': check},
            'maneuver_completed': check['status'] == 'met',
            'realized_observables': observed if check['status'] == 'met' else {},
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
            'accepted': False, 'legal_verdict_claimed': False,
            'original_native_motion_verified': False,
            'engineering_target_only': True}


def lifecycle(events, exit_code):
    if events != EVENTS or exit_code != 0:
        raise ValueError('Saved processing before Native closure and owner release')
    return {'events': events, 'exit_code': 0,
            'synthetic_state_machine_test': True,
            'original_native_owner_release_verified': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=['reference', 'contrast'], required=True)
    parser.add_argument('--kind', choices=['complete_motion', 'incomplete_motion',
                                         'missing_evidence', 'lifecycle'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entry = next(e for e in manifest['cases'] if e['case_id'].endswith('__' + args.case))
    if args.kind == 'lifecycle':
        result = lifecycle(EVENTS, 0)
        for bad_events, code in ((EVENTS[::-1], 0), (EVENTS, 1)):
            try:
                lifecycle(bad_events, code)
            except ValueError:
                pass
            else:
                raise AssertionError('Invalid lifecycle accepted')
    else:
        spec_path = HERE / f'selected-{args.case}-fixture.json'
        spec = json.loads(spec_path.read_text())
        files = spec['files']
        trace = [json.loads(x) for x in files['trace.jsonl'].splitlines()]
        evidence = [json.loads(x) for x in files['capture/evidence.jsonl'].splitlines()]
        graphs = spec['graphs']
        provenance = json.loads(files['acquisition-provenance.json'])
        if args.kind == 'incomplete_motion':
            for row, event, graph in zip(trace, evidence, graphs):
                row['position_m'][0] = 0.0
                row['position']['x'] = 0.0
                row['velocity_mps'][0] = 0.0
                row['acceleration_mps2'][0] = 0.0
                row['speed_mps'] = 0.0
                row['speed_mph'] = 0.0
                event['ego']['position_m'][0] = 0.0
                event['ego']['speed_mps'] = 0.0
                event['world']['road_projection']['s_m'] = 0.0
                for vertex_index, vertex in enumerate(event['ego']['body_vertices_m']):
                    vertex[0] = -2.0 if vertex_index < 4 else 2.0
                graph['nodes'][0]['attributes']['vertex'][0] = 0.0
                for vertex_index, vertex in enumerate(graph['nodes'][0]['attributes']['threedbbox']):
                    vertex[0] = -2.0 if vertex_index < 4 else 2.0
        elif args.kind == 'missing_evidence':
            trace.pop()
        result = classify(trace, evidence, graphs, provenance)
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[args.kind]
        assert result['physical_checks']['maneuver']['status'] == expected
        assert classify(trace, evidence, graphs, {})['physical_checks']['maneuver']['status'] == 'unverified'
        if args.kind == 'complete_motion':
            mismatched = copy.deepcopy(trace)
            mismatched[-1]['position']['x'] += 1.0
            assert classify(mismatched, evidence, graphs, provenance)['physical_checks']['maneuver']['status'] == 'unverified'
        result['fixture_spec_sha256'] = sha(spec_path)
        result['fixture_mutation'] = args.kind
        result['mock_input_provenance'] = 'synthetic_native_sample'
    result['construction_sha256'] = entry['construction_sha256']
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'case_id': entry['case_id'], 'kind': args.kind,
                      'status': result.get('physical_checks', {}).get('maneuver', {}).get('status'),
                      'synthetic_fixture': True}))


if __name__ == '__main__':
    main()

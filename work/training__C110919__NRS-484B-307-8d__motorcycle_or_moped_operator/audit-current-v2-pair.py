"""Independently check the controlled synthetic motorcycle contrast."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def main():
    receipts = {key: json.loads((HERE / f'current-v2-{key}-compatibility.json').read_text())
                for key in ('a', 'b')}
    source = {key: HERE / f'current-v2-condition_{key}-fixture' for key in receipts}
    samples = {key: rows(source[key] / 'native_samples.jsonl') for key in receipts}
    for key in receipts:
        result = receipts[key]
        assert result['passed'] is True and result['candidate_id'] == 'primary'
        assert len(samples[key]) == 600
        assert result['negative_removed'] == 'road_geometry.json'
        assert 'negative_case_source' in result['checks']
        assert result['measurement_examples']['two_cycle_fault_condition']['value']['physical_fault_causation_observed'] is False
        assert result['measurement_examples']['failed_detection_witness']['value']['physical_failure_cause_verified'] is False
        assert all(row['signal_state_observed'] == 'Red' for row in samples[key])
        assert all(row['motorcycle_blueprint'] == 'vehicle.kawasaki.ninja' for row in samples[key])
        assert all(row['fault_injection_command'] == 'withhold_motorcycle_detector_request'
                   for row in samples[key])
        for name in ('road.xodr', 'road_geometry.json', 'capture/manifest.json'):
            assert sha(source[key] / name) == result['fixture_manifest'][name]
    for name in ('road.xodr', 'road_geometry.json'):
        assert sha(source['a'] / name) == sha(source['b'] / name)
    for name in ('overview', 'approach', 'reference_corner', 'driver_reference'):
        assert receipts['a']['fixture_manifest'][name + '.mkv'] == receipts['b']['fixture_manifest'][name + '.mkv']
    cycles = {}
    turns = {}
    for key in receipts:
        turn = next(index for index, row in enumerate(samples[key]) if row['ego_turn_entered'])
        turns[key] = turn
        cycles[key] = max(row['complete_cross_signal_cycles'] for row in samples[key][:turn + 1])
        measured = receipts[key]['measurement_examples']['two_cycle_fault_condition']['value']
        assert measured['complete_cycles_before_turn'] == cycles[key]
        assert measured['turn_entry_frame'] == turn
        assert receipts[key]['measurement_examples']['motorcycle_stop']['value']['halt_before_right_turn_on_red']
        assert receipts[key]['measurement_examples']['pedestrian_and_traffic_yield']['value']['last_walker_conflict_frame'] < turn
        assert receipts[key]['measurement_examples']['pedestrian_and_traffic_yield']['value']['last_cross_traffic_conflict_frame'] < turn
    assert cycles == {'a': 2, 'b': 1} and turns == {'a': 301, 'b': 181}
    proof = {'format': 'c110919-current-v2-pair-audit-v1', 'passed': True,
             'compatibility_sha256': {key: sha(HERE / f'current-v2-{key}-compatibility.json')
                                      for key in receipts},
             'source_cycles_at_turn': cycles, 'turn_frames': turns,
             'ego_red_frames': {'a': 600, 'b': 600},
             'same_map_and_road_geometry': True, 'same_diagnostic_video_pixels': True,
             'original_native_observed': False, 'selected_delivery': False,
             'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    path = HERE / 'current-v2-pair-audit.json'
    path.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'passed': True, 'audit_sha256': sha(path)}))


if __name__ == '__main__':
    main()

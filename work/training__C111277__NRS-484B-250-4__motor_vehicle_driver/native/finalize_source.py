"""Finalize retained source-shaped rows for the crosswalk comparison.

This CPU diagnostic never turns synthetic signal state into a physical finding.
"""
import argparse
import hashlib
import json
from pathlib import Path

from measure import load, measure


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source(path):
    if not path.is_file():
        raise ValueError('Missing required source: ' + path.name)
    return path


def finalize(attempt, output):
    attempt = Path(attempt).resolve()
    output = Path(output).resolve()
    if output.exists() or (attempt / 'channels').exists():
        raise ValueError('Use a fresh source-only finalization attempt')
    index_name = 'native-index.json' if (attempt / 'native-index.json').is_file() else 'source-index.json'
    for name in (index_name, 'geometry.json', 'signal.json', 'native-rows.jsonl'):
        source(attempt / name)
    index, geometry, signal, rows = load(attempt)
    measured = measure(attempt)
    originals = {name: sha(attempt / name) for name in
                 (index_name, 'geometry.json', 'signal.json', 'native-rows.jsonl')}
    streams = {name: [] for name in
               ('dev.traffic_signal', 'dev.inoperative', 'st.stop_line', 'st.crosswalk',
                'drv.stopped', 'drv.entering_intersection', 'drv.arrival_order',
                'drv.in_intersection', 'drv.yields_to', 'kin.velocity')}
    first_other_stop = measured['other_first_stop_frame']
    for row in rows:
        frame = row['frame']
        values = {
            'dev.traffic_signal': {'installed': signal['installed'],
                                   'uncovered': signal['uncovered'],
                                   'controlled_lane': signal['controlled_incoming_lane']},
            'dev.inoperative': {'synthetic_observation': signal['inoperative_observed'],
                                'physical_failure_confirmed': False},
            'st.stop_line': {'present': geometry['stop_line_present']},
            'st.crosswalk': {'present': geometry['near_crosswalk_present'],
                             'near_edge_x_m': geometry['crosswalk_near_edge_x_m']},
            'drv.stopped': row['ego_speed_mps'] <= 0.05,
            'drv.entering_intersection': row['ego_front_x_m'] >= geometry['intersection_entry_x_m'],
            'drv.arrival_order': {'other_first_stop_frame': first_other_stop,
                                  'other_previously_stopped': frame >= first_other_stop},
            'drv.in_intersection': row['other_in_intersection'],
            'drv.yields_to': {'other_in_intersection': row['other_in_intersection'],
                              'ego_before_crosswalk': row['ego_front_x_m'] < geometry['crosswalk_near_edge_x_m']},
            'kin.velocity': row['ego_speed_mps'],
        }
        for name, value in values.items():
            streams[name].append({'native_frame': frame, 'time_s': row['time_s'],
                                  'value': value, 'source_sha256': originals})
    channel_dir = attempt / 'channels'
    channel_dir.mkdir()
    for name, values in streams.items():
        with (channel_dir / (name + '.jsonl')).open('x') as file:
            for value in values:
                file.write(json.dumps(value, allow_nan=False) + '\n')
    if any(sha(attempt / name) != value for name, value in originals.items()):
        raise ValueError('Finalization changed retained sources')
    report = {'format': 'nrs-484b-250-4-source-finalization-v1',
              'assignment_id': index['assignment_id'], 'condition': index['condition'],
              'source_sha256': originals, 'frames': len(rows), 'rate_hz': index['rate_hz'],
              'measurements': measured,
              'derived_channels_sha256': {name: sha(channel_dir / (name + '.jsonl'))
                                          for name in sorted(streams)},
              'physical_signal_failure_confirmed': False,
              'original_native_observed': False, 'legal_outcome_asserted': False}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps({'condition': finalize(args.attempt, args.output)['condition'],
                      'passed': True}))

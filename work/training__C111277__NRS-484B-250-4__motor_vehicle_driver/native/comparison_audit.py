"""Independent retained-source audit for the selected crosswalk contrast.

Fixture execution tests the audit logic; it never certifies a Native recording.
"""
import argparse
import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read_source(root):
    root = Path(root)
    index_path = root / 'source-index.json'
    require(index_path.is_file(), 'missing source-index.json')
    index = json.loads(index_path.read_text())
    required = ('geometry.json', 'signal.json', 'native-rows.jsonl')
    require(set(index['files']) == set(required), 'incomplete source index')
    for name in required:
        path = root / name
        require(path.is_file(), 'missing ' + name)
        require(digest(path) == index['files'][name], 'source hash mismatch: ' + name)
    geometry = json.loads((root / 'geometry.json').read_text())
    signal = json.loads((root / 'signal.json').read_text())
    rows = [json.loads(line) for line in (root / 'native-rows.jsonl').read_text().splitlines()]
    require(index['frames'] == 600 and index['rate_hz'] == 20 and len(rows) == 600,
            'incomplete 600-frame 20 Hz trace')
    for frame, row in enumerate(rows):
        require(row['frame'] == frame and abs(row['time_s'] - frame / 20) < 1e-8,
                'frame/time join failed')
    require(geometry['stop_line_present'] is False and geometry['near_crosswalk_present'] is True,
            'selected stop-reference hierarchy changed')
    require(signal['installed'] is True and signal['uncovered'] is True and
            signal['inoperative_observed'] is True and
            signal['controlled_incoming_lane'] == geometry['ego_incoming_lane'],
            'governing inoperative signal source missing')
    return index, geometry, signal, rows


def audit(halt_root, roll_root):
    halt, geometry_a, signal_a, rows_a = read_source(halt_root)
    roll, geometry_b, signal_b, rows_b = read_source(roll_root)
    require((halt['condition'], roll['condition']) == ('halt', 'roll'),
            'comparison condition identities changed')
    require(geometry_a == geometry_b and signal_a == signal_b,
            'fixed geometry or signal differs')
    edge = geometry_a['crosswalk_near_edge_x_m']
    entries = []
    stopped = []
    yielded = []
    for rows in (rows_a, rows_b):
        entry = next((i for i, row in enumerate(rows) if row['ego_front_x_m'] >= edge), None)
        require(entry is not None, 'ego never entered crosswalk')
        prior_halts = [i for i, row in enumerate(rows[:entry])
                       if row['ego_speed_mps'] <= 0.05 and row['ego_front_x_m'] < edge]
        other_stop = next((i for i, row in enumerate(rows)
                           if row['other_speed_mps'] <= 0.05), None)
        other_inside = [i for i, row in enumerate(rows) if row['other_in_intersection']]
        require(other_stop is not None and other_inside and other_stop < other_inside[0],
                'priority history missing')
        entries.append(entry)
        stopped.append(bool(prior_halts))
        yielded.append(entry > other_inside[-1])
    require(entries[0] == entries[1], 'crosswalk entry timing differs')
    require(stopped == [True, False], 'halt contrast absent')
    require(yielded == [True, True], 'yield condition changed')
    return {'format': 'nrs-484b-250-4-comparison-source-audit-v1', 'passed': True,
            'comparison_variable': 'complete_halt_before_applicable_boundary',
            'crosswalk_entry_frames': entries, 'halt_before_crosswalk': stopped,
            'yielded_until_other_clear': yielded,
            'source_index_sha256': [digest(Path(p) / 'source-index.json')
                                    for p in (halt_root, roll_root)],
            'physical_realization_confirmed': False, 'legal_outcome_asserted': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--halt', required=True)
    parser.add_argument('--roll', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = audit(args.halt, args.roll)
    Path(args.output).write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': True, 'halt_contrast': report['halt_before_crosswalk']}))

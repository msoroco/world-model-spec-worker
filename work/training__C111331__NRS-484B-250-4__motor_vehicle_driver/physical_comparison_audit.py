"""Compare original source measurements for the marked-line stop contrast.

The audit reports bounded physical measurements. Camera pixels and statutory
judgments require independent review after Native capture.
"""
import argparse
import hashlib
import json
from pathlib import Path

from native.original_measure import measure

BASE = 'training__C111331__NRS-484B-250-4__motor_vehicle_driver'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def audit(primary, contrast):
    primary, contrast = Path(primary), Path(contrast)
    measures = [measure(primary), measure(contrast)]
    paths = [primary, contrast]
    configs = [json.loads((p / 'config.json').read_text()) for p in paths]
    if [c.get('case_id') for c in configs] != [BASE + '__controlled_1', BASE + '__controlled_2']:
        raise ValueError('Original exact-case pair differs')
    for key in ('law_id', 'cell_id', 'actor', 'rate_hz', 'frames', 'cameras', 'required_atoms', 'source_packets'):
        if configs[0].get(key) != configs[1].get(key):
            raise ValueError('Fixed Native comparison configuration differs: ' + key)
    if sha(primary / 'road.xodr') != sha(contrast / 'road.xodr'):
        raise ValueError('Native comparison road differs')
    actors = [rows(p / 'native-raw-actors.jsonl') for p in paths]
    signals = [rows(p / 'native-signal-readback.jsonl') for p in paths]
    for a, b, sa, sb in zip(*actors, *signals):
        if (any(abs(x-y) > 0.5 for x,y in zip(
                    a['other']['center_native_xyz_m'],
                    b['other']['center_native_xyz_m'])) or
                abs(a['other']['speed_mps'] - b['other']['speed_mps']) > 0.2 or
                sa['governing_heads'].keys() != sb['governing_heads'].keys()):
            raise ValueError('Fixed other-vehicle or governed-head source differs')
    if not measures[0]['pre_line_low_speed_frames'] or measures[1]['pre_line_low_speed_frames']:
        raise ValueError('Measured pre-line low-speed contrast differs')
    if measures[0]['ego_entry_frame'] <= measures[1]['ego_entry_frame']:
        raise ValueError('Measured entry order contrast differs')
    return {'format': 'worker-original-comparison-audit-v1',
            'case_ids': [c['case_id'] for c in configs],
            'fixed_conditions_checked': True,
            'measurements': measures,
            'original_native_sources_joined': True,
            'actual_pixels_reviewed': False,
            'legal_verdict': None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--primary', required=True)
    parser.add_argument('--contrast', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    Path(args.output).write_text(json.dumps(audit(args.primary, args.contrast), indent=2) + '\n')

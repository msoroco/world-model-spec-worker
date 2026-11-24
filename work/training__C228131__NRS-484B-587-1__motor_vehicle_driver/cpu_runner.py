"""Offline-only requested-entry construction check; Native runner is pending."""
import argparse
import json
from pathlib import Path

from entry_cpu import CAMERAS, FPS, FRAMES, requested_pose


def check():
    config = json.loads(Path('config.json').read_text())
    suffix = config['case_id'].removeprefix(config['assignment_id'] + '__')
    if (suffix not in ('witness_1', 'witness_2')
            or config['law_id'] != 'NRS-484B-587-1' or config['cell_id'] != 'C228131'
            or config['rate_hz'] != FPS or config['duration_s'] != 30
            or FRAMES != 600 or tuple(config['camera_names']) != CAMERAS
            or config['source_kind'] != 'authored_native_request'):
        raise ValueError('exact CPU entry request differs')
    crossing = [requested_pose(suffix, i) for i in range(FRAMES)
                if requested_pose(suffix, i)['phase'] == 'enter']
    if not crossing or crossing[0]['center_xy_m'][0] != (0 if suffix == 'witness_1' else 60):
        raise ValueError('controlled entry target differs')
    return {'case_id': config['case_id'], 'frames': FRAMES,
            'camera_names': list(CAMERAS), 'requested_gate_x_m':
            crossing[0]['center_xy_m'][0], 'native_executed': False,
            'delivery_ready': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if not args.check:
        parser.error('CPU draft has no Native execution entrypoint')
    print(json.dumps(check()))

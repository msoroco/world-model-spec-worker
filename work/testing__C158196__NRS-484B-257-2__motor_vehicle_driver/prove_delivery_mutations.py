"""Reject changed original-source joins, body, provenance, and camera media."""

import json
import os
import shutil
import tempfile
from pathlib import Path

from delivery_audit import audit_delivery


PACKAGE = Path(__file__).resolve().parent
REPO = PACKAGE.parents[1]
CASE = 'testing__C158196__NRS-484B-257-2__motor_vehicle_driver__active_signal_controls'


def replace_json(path, value):
    path.unlink()
    path.write_text(json.dumps(value) + '\n')


def main():
    raw_root = os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT')
    if not raw_root:
        raise ValueError('SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work is required')
    output = Path(raw_root).resolve()
    private = (REPO / '.runtime-work').resolve()
    if output != private and private not in output.parents:
        raise ValueError('Output root outside .runtime-work')
    original = output / 'active_signal_controls'
    tests = {
        'changed-frame-join': ('video_frames.jsonl', 'Crossing body history has no original frame join'),
        'missing-other-body': ('crossing_history.jsonl', 'Missing complete original other body'),
        'changed-provenance': ('acquisition-provenance.json', 'CPU diagnostic must identify a synthetic fixture'),
        'missing-camera': ('overview.mkv', 'Missing original source camera: overview'),
    }
    for label, (name, expected) in tests.items():
        with tempfile.TemporaryDirectory(dir=output, prefix='delivery-mutation-') as temporary:
            attempt = Path(temporary) / 'attempt'
            shutil.copytree(original, attempt, copy_function=os.link)
            path = attempt / name
            if label == 'changed-frame-join':
                data = [json.loads(line) for line in path.read_text().splitlines()]
                data[100]['carla_frame'] += 1
                path.unlink()
                path.write_text(''.join(json.dumps(row) + '\n' for row in data))
            elif label == 'missing-other-body':
                data = [json.loads(line) for line in path.read_text().splitlines()]
                data[100].pop('other_body_vertices_xy_m')
                path.unlink()
                path.write_text(''.join(json.dumps(row) + '\n' for row in data))
            elif label == 'changed-provenance':
                replace_json(path, {'provenance_kind': 'native'})
            else:
                path.unlink()
            try:
                audit_delivery(attempt, PACKAGE, CASE, diagnostic_fixture=True)
            except ValueError as error:
                if expected not in str(error):
                    raise AssertionError(f'{label}: wrong rejection: {error}') from error
                print(f'{label}: rejected: {error}')
            else:
                raise AssertionError(f'{label}: changed source was accepted')


if __name__ == '__main__':
    main()

"""Lazy Native entrypoint for an exact, reviewed NRS 484B.533 case."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path

from source_packet import ASSIGNMENT, verify


HERE = Path(__file__).resolve().parent


def check():
    config = json.loads((HERE / 'config.json').read_text())
    if (config.get('assignment_id') != ASSIGNMENT or
            config.get('law_id') != 'NRS-484B-533' or
            config.get('cell_id') != 'C276300'):
        raise ValueError('grade-standing bundle scope changed')
    digest = hashlib.sha256((HERE / 'case-plan.json').read_bytes()).hexdigest()
    if config.get('plan_sha256') != digest:
        raise ValueError('grade-standing plan changed')
    case_id = config.get('selected_case_id')
    if (case_id not in config.get('supported_case_ids', []) or
            config.get('rate_hz') != 20 or config.get('duration_s') != 45):
        raise ValueError('grade-standing capture contract changed')
    return config, case_id


def _reviewed_file(path_text, expected_hash, label):
    if not path_text or not expected_hash:
        raise ValueError('source-hashed reviewed ' + label + ' required')
    path = Path(path_text).resolve()
    if (not path.is_file() or path.is_symlink() or
            hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash):
        raise ValueError('reviewed ' + label + ' bytes changed')
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    config, case_id = check()
    if args.check:
        print(case_id)
        return
    if not args.host or not args.port or not args.output_dir:
        raise ValueError('Native host, port and output directory required')
    packet_path = _reviewed_file(os.environ.get('SCENARIO_GRADE_STAND_PACKET'),
                                 os.environ.get('SCENARIO_GRADE_STAND_PACKET_SHA256'),
                                 'grade-standing packet')
    checked = verify(packet_path)
    if checked['case_id'] != case_id:
        raise ValueError('reviewed packet selects another exact case')
    operator = _reviewed_file(os.environ.get('SCENARIO_GRADE_STAND_OPERATOR'),
                              os.environ.get('SCENARIO_GRADE_STAND_OPERATOR_SHA256'),
                              'grade-standing Native operator')
    spec = importlib.util.spec_from_file_location('reviewed_grade_stand_operator', operator)
    if spec is None or spec.loader is None:
        raise ValueError('reviewed Native operator cannot load')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, 'make_adapter', None)):
        raise ValueError('reviewed Native operator factory missing')
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    adapter = module.make_adapter(client.get_world(), checked['scene'], case_id,
                                  approach_offset_m=config['approach_offset_m'])
    from native_acquisition import acquire
    receipt = acquire(adapter, packet_path, args.output_dir)
    print(json.dumps({'case_id': receipt['case_id'],
                      'original_frames': receipt['source_frame_count']}))


if __name__ == '__main__':
    main()

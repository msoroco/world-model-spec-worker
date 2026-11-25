"""Dispatch the six exact caravan constructions without starting CARLA on check."""
import argparse
import json
from pathlib import Path

from caravan_native import CASES as PLAIN
from caravan_towing_native import CASES as TOWED
from caravan_towing_selected_sweep_native import CASES as SWEEP

MODULES = {case: 'caravan_native' for case in PLAIN}
MODULES.update({case: 'caravan_towing_native' for case in TOWED})
MODULES.update({case: 'caravan_towing_selected_sweep_native' for case in SWEEP})


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--case-id')
    parser.add_argument('--output-dir')
    args, _ = parser.parse_known_args()
    if args.check:
        print(json.dumps({'assignment_id': Path(__file__).resolve().parent.name,
                          'case_ids': list(MODULES), 'cpu_check_passed': True,
                          'carla_started': False}))
        return
    if not args.case_id and args.output_dir:
        config = json.loads((Path(args.output_dir) / 'config.json').read_text())
        args.case_id = config.get('selected_case_id')
    if args.case_id not in MODULES:
        raise ValueError('Unknown selected caravan case')
    if MODULES[args.case_id] == 'caravan_native':
        from caravan_native import main as selected
    elif MODULES[args.case_id] == 'caravan_towing_native':
        from caravan_towing_native import main as selected
    else:
        from caravan_towing_selected_sweep_native import main as selected
    selected()


if __name__ == '__main__':
    main()

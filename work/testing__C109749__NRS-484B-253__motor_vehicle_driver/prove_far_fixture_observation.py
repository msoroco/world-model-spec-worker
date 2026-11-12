"""Observe the generated far diagnostic without changing its sealed tree hash."""
import argparse
import json
import shutil
import sys
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
sys.path.insert(0, str(FOLDER))
from far_approach_observation import observe


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source, output = args.fixture.resolve(), args.output.resolve()
    if output.exists():
        raise ValueError('Use a fresh observation output')
    shutil.copytree(source, output)
    shutil.copy2(FOLDER / 'cases/approaching_far/config.json', output / 'config.json')
    value = observe(output)
    if value['ego_turn_start_frame'] >= value['opposing_entry_frame']:
        raise ValueError('Far diagnostic turn does not precede opposing entry')
    print(json.dumps(value, indent=2))


if __name__ == '__main__':
    main()

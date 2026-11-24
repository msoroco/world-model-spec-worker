"""CPU-checkable C24805 exact road and motion requests; Native capture pending."""
import argparse
import json
from pathlib import Path
from sight_stop import check_config, read_and_measure


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--measure-request')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    config = json.loads((root / 'config.json').read_text())
    receipt = check_config(config, (root / 'road.xodr').read_text())
    if args.measure_request:
        receipt['request_meter'] = read_and_measure(args.measure_request,
                                                     'authored_native_request')
    if not args.check and not args.measure_request:
        raise ValueError('Native capture and source sealing not yet implemented')
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()

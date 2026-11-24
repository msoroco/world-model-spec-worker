"""CPU-checkable exact C238396 route proposal; no Native outcome is claimed."""
import argparse
import json
from pathlib import Path
from roundabout_direction import check_config, read_and_measure


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--measure-request')
    args = parser.parse_args()
    bundle = Path(__file__).resolve().parent
    config = json.loads((bundle / 'config.json').read_text())
    result = check_config(config)
    if args.measure_request:
        result['route_meter'] = read_and_measure(args.measure_request,
                                                   'authored_native_request')
    if not args.check and not args.measure_request:
        raise ValueError('Native capture integration and source sealing still required')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()

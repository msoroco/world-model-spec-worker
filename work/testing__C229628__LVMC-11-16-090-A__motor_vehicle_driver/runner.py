"""Exact source-gated Native speed-contest aid probe entrypoint."""
import argparse
import json
import os
from pathlib import Path

from native_source import AID, read_site


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--case')
    parser.add_argument('--site', type=Path)
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    config = json.loads((Path(__file__).resolve().parent / 'config.json').read_text())
    case_id = config.get('selected_case_id')
    if config.get('assignment_id') != AID or args.case not in (None, case_id):
        raise ValueError('exact bundled case changed')
    if args.check:
        print('exact contest-aid runner static check passed:', case_id)
        return
    site_path = args.site or os.environ.get('C229628_REVIEWED_SITE')
    if not site_path or not args.host or args.port is None or args.output_dir is None:
        raise ValueError('reviewed site, host, port and output directory required')
    site, scene, case = read_site(site_path, case_id)
    from contest_carla_adapter import CarlaContestAdapter
    from contest_capture import capture
    adapter = CarlaContestAdapter(args.host, args.port, site)
    capture(adapter, site, scene, case, args.output_dir)


if __name__ == '__main__':
    main()

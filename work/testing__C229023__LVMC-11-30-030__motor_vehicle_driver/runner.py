"""Launch one reviewed exact crossing construction for later physical capture."""
import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def select_case(case_id):
    config = json.loads((ROOT / 'config.json').read_text())
    raw = (ROOT / 'case-plan.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != config['plan_sha256']:
        raise ValueError('Canonical crossing plan changed')
    plan = json.loads(raw)
    if config['assignment_id'] != plan['assignment_id']:
        raise ValueError('Assignment identity changed')
    if case_id not in config['supported_case_ids']:
        raise ValueError('Unselected crossing case')
    matches = [row for row in plan['cases'] if row['case_id'] == case_id]
    if len(matches) != 1:
        raise ValueError('Exact crossing case missing')
    return matches[0]


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--site')
    parser.add_argument('--output-dir')
    parser.add_argument('--carla-host', default='127.0.0.1')
    parser.add_argument('--carla-port', type=int, default=2000)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    row = select_case(args.case)
    if args.check:
        print(json.dumps({'case_id': row['case_id'], 'checked': True}, sort_keys=True))
        return
    if not args.site or not args.output_dir:
        raise ValueError('Reviewed road intersection site and original output directory required')
    from case_construction import construct
    from native_crosswalk_session import capture_case
    proposal = construct(args.site, args.case, plan_path=ROOT / 'case-plan.json')
    import carla
    client = carla.Client(args.carla_host, args.carla_port)
    client.set_timeout(30.0)
    result = capture_case(world=client.get_world(), carla=carla,
                          proposal=proposal, output=args.output_dir)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()

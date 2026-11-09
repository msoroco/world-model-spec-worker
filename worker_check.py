"""Static package checks only; does not execute any returned implementation."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / 'runtime' / 'scenario_pipeline'))
from worker_exchange.preparation import check

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--complete', action='store_true')
    parser.add_argument('--require-delivery-ready', action='store_true')
    parser.add_argument('--assignment', help='Check one exact assignment; batch coverage remains a separate final check')
    parser.add_argument('--updates', action='store_true', help='Inspect numbered update and pause state only')
    args = parser.parse_args()
    if args.updates:
        if args.complete or args.require_delivery_ready or args.assignment:
            parser.error('--updates cannot substitute for ordinary or strict readiness checking')
        from worker_exchange.updates import state
        print(json.dumps(state(Path(__file__).resolve().parent), indent=2))
        raise SystemExit(0)
    result = check(Path(__file__).resolve().parent, complete=args.complete or args.require_delivery_ready, require_ready=args.require_delivery_ready, assignment=args.assignment)
    print(json.dumps({'batch_id': result['batch_id'], 'reported': list(result['results']),
                      'static_checks_passed': True}, indent=2))

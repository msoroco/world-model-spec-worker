"""Evidence-bound engineering motion outcome on a saved diagnostic attempt."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'runtime'/'scenario_pipeline'))
from worker_exchange.native_output import physical_result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    root = Path(args.attempt)
    result = json.loads((root/'result.json').read_text())
    if result['case_id'] != args.case:
        raise ValueError('Physical fixture selected another case')
    assessed = physical_result(root, result)
    if assessed['provenance_kind'] != 'synthetic_fixture':
        raise ValueError('CPU physical fixture cannot claim Native provenance')
    Path(args.output).write_text(json.dumps(assessed, indent=2)+'\n')
    print(json.dumps({'case_id': args.case,
                      'maneuver': assessed['physical_checks']['maneuver']['status'],
                      'synthetic_fixture': True}))


if __name__ == '__main__':
    main()

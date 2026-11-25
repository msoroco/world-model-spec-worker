"""Require the compared trip's original enroute service stop and reviewed purpose."""
import argparse
import json
from pathlib import Path

from measure_through_route import AID, measure, rows


def measure_purpose(root):
    root = Path(root)
    observation = measure(root)
    context = json.loads((root/'route_context.json').read_text())
    if observation['case_id'] != AID+'__probe_02':
        raise ValueError('Purpose comparison has wrong exact case')
    if context['enroute_purpose'] not in ('pickup', 'delivery', 'essential'):
        raise ValueError('Purpose comparison requires reviewed pickup, delivery or essential use')
    trace = rows(root/'native_route_trace.jsonl')
    longest = current = 0
    for row in trace:
        if row.get('service_stop_active') is True and row['road_id'] == context['intervening_street_id'] and row['ego_speed_mps'] <= .1:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    if longest < 100 or context.get('service_stop_complete') is not True:
        raise ValueError('Missing 100-frame original stop on intervening street')
    if not observation['complete_truck_to_truck_passage']:
        raise ValueError('Purpose comparison did not complete same three-road journey')
    observation['reviewed_service_stop_frames'] = longest
    observation['reviewed_service_premises_source'] = context['served_premises_source']
    return observation


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source_dir', type=Path)
    parser.add_argument('output_json', type=Path)
    args = parser.parse_args()
    args.output_json.write_text(json.dumps(measure_purpose(args.source_dir), indent=2)+'\n')

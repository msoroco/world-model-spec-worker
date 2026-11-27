"""Independent exact 257(2) comparison audit over saved originals."""
import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from delivery_audit import audit as audit_delivery
from stop_yield_saved_measure import measure_paths

HERE = Path(__file__).resolve().parent


def pairs(values):
    output = {}
    for value in values:
        case, separator, path = value.partition('=')
        if not separator or not case or not path or case in output:
            raise ValueError('Each case path needs unique CASE=PATH form')
        output[case] = Path(path).resolve()
    return output


def road_geometry(path):
    root = ET.fromstring(path.read_text())
    for road in root.findall('road'):
        for tag in ('objects', 'signals'):
            child = road.find(tag)
            if child is not None:
                road.remove(child)
    return ET.tostring(root, encoding='unicode')


def compare(comparison_id, attempts, processing, diagnostic=False, missing_source=None):
    plan = json.loads((HERE / 'case-plan.json').read_text())
    matches = [value for value in plan['comparisons'] if value['comparison_id'] == comparison_id]
    if len(matches) != 1:
        raise ValueError('Unknown exact statutory comparison')
    comparison = matches[0]
    members = comparison['case_ids']
    if set(attempts) != set(members) or set(processing) != set(members):
        raise ValueError('Comparison lacks exact member attempts or processing receipts')
    records = {}
    for case in members:
        attempt = attempts[case]
        audit_delivery(case, attempt, processing[case], diagnostic, missing_source)
        packet = json.loads((attempt / 'nonthrough_saved_packet.json').read_text())
        controls = json.loads((attempt / 'entrance_controls.json').read_text())
        config = json.loads((attempt / 'config.json').read_text())
        measurement = measure_paths(attempt / 'nonthrough_saved_packet.json',
                                    attempt / 'entrance_controls.json')
        if not diagnostic and (packet['source_kind'] != 'native_saved_sample' or
                               controls['source_kind'] != 'native_saved_sample'):
            raise ValueError('Original Native source required for delivery comparison')
        records[case] = {'packet': packet, 'controls': controls,
                         'config': config, 'measurement': measurement,
                         'road_geometry': road_geometry(attempt / 'road.xodr')}
    first = records[members[0]]
    for case in members[1:]:
        current = records[case]
        if current['road_geometry'] != first['road_geometry']:
            raise ValueError('Undeclared local crossing geometry difference')
        for key in ('rate_hz', 'duration_s', 'frames', 'cameras', 'actor', 'cell_id'):
            if current['config'].get(key) != first['config'].get(key):
                raise ValueError('Undeclared capture or actor difference: ' + key)
        for entrance in ('east_opposing', 'south_crossing'):
            if (current['controls']['entrance_controls'][entrance] !=
                    first['controls']['entrance_controls'][entrance]):
                raise ValueError('Undeclared entrance control difference: ' + entrance)
    axis = comparison_id.split('__')[-1]
    a = first
    values = [records[case] for case in members]
    if axis in ('stop_action', 'yield_action'):
        if any(value['controls']['subject_control'] != a['controls']['subject_control'] or
               value['controls']['counterpart_control'] != a['controls']['counterpart_control'] or
               value['controls']['stop_reference'] != a['controls']['stop_reference'] for value in values):
            raise ValueError('Action comparison changed signs or reference')
        trajectories = {tuple(row['subject_body_vertices_m'][0][0] for row in value['packet']['frames'])
                        for value in values}
        if len(trajectories) != len(values):
            raise ValueError('Action comparison lacks distinct measured subject motion')
    elif axis == 'stopping_reference':
        if len({value['controls']['stop_reference'] for value in values}) != len(values):
            raise ValueError('Stopping-reference comparison lacks distinct original references')
        if any(value['controls']['subject_control'] != a['controls']['subject_control'] for value in values):
            raise ValueError('Stopping-reference comparison changed subject sign')
    elif axis == 'counterpart_phase':
        if len({tuple(row['counterpart_body_vertices_m'][0][1] for row in value['packet']['frames'])
                for value in values}) != len(values):
            raise ValueError('Counterpart phase comparison lacks distinct measured motion')
    elif axis == 'counterpart_obligation':
        if len({value['controls']['counterpart_control'] for value in values}) != len(values):
            raise ValueError('Counterpart obligation comparison lacks distinct original signs')
    elif axis in ('police_exception', 'signal_exception'):
        if len({value['controls']['control_exception'] for value in values}) != len(values):
            raise ValueError('Control-exception comparison lacks distinct original states')
    else:
        raise ValueError('Undeclared comparison axis')
    return {'comparison_id': comparison_id, 'case_ids': members,
            'diagnostic_only': diagnostic, 'fixed_geometry_and_capture_checked': True,
            'source_bound_measurements': {
                case: {'source_sha256': value['measurement']['source_sha256'],
                       'control_inventory_sha256': value['measurement']['control_inventory_sha256'],
                       'entry_frame': value['measurement']['subject_entry_frame'],
                       'counterpart_inside_at_entry': value['measurement']['counterpart_inside_at_entry']}
                for case, value in records.items()},
            'legal_verdict': None, 'physical_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--attempt', action='append', default=[], metavar='CASE=PATH')
    parser.add_argument('--processing', action='append', default=[], metavar='CASE=PATH')
    parser.add_argument('--diagnostic', action='store_true')
    parser.add_argument('--missing-source')
    args = parser.parse_args()
    print(json.dumps(compare(args.comparison, pairs(args.attempt), pairs(args.processing),
                             args.diagnostic, args.missing_source), sort_keys=True))

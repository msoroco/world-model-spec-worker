"""Independent source and controlled-pair audit of the authored crosswalk branch."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'native'))
from crosswalk_branch import marking, measure, sha


def audit():
    summary = json.loads((HERE / 'crosswalk-branch-summary.json').read_text())
    source = json.loads((HERE / 'statutory-crossrefs.json').read_text())
    if summary['crossref_law_id'] != 'LVMC-11-30-060-A' or not any(
        row['law_id'] == summary['crossref_law_id'] for row in source['crossrefs']):
        raise ValueError('Crosswalk branch statutory source differs')
    road = HERE / summary['authored_road']
    if summary['authored_road_sha256'] != sha(road) or summary['marking'] != marking(road):
        raise ValueError('Crosswalk branch authored road differs')
    if summary['physical_crossref_cases_constructed'] or summary['legal_applicability_conclusion'] is not None:
        raise ValueError('Crosswalk branch overclaims applicability')
    if [row['label'] for row in summary['records']] != ['marked', 'outside']:
        raise ValueError('Crosswalk controlled pair missing')
    traces = []
    source_pairs = []
    for row, expected_y, expected_relation in zip(summary['records'], (0, 4),
                                                  ('inside_authored_marking', 'outside_authored_marking')):
        folder = Path(row['folder'])
        result = measure(folder)
        if (row['measurement'] != result or result['crossing_y_m'] != expected_y or
            result['marking_relation_at_entry'] != expected_relation or
            result['source_kind'] != 'synthetic_scene_request' or
            result['physical_crossing_observed']):
            raise ValueError('Crosswalk controlled source differs')
        traces.append(result['vehicle_trace_sha256'])
        samples = [json.loads(line) for line in (folder / 'curb-samples.jsonl').read_text().splitlines()]
        source_pairs.append(samples)
        ys = [v[1] for v in samples[result['roadway_entry_frame']-samples[0]['native_frame']]['pedestrian_footprint_xy_m']]
        # Recompute the decisive marking relation without the measurement helper.
        if expected_relation == 'inside_authored_marking' and not (min(ys) >= -1.5 and max(ys) <= 1.5):
            raise ValueError('Independent marked crossing geometry differs')
        if expected_relation == 'outside_authored_marking' and not min(ys) > 1.5:
            raise ValueError('Independent outside crossing geometry differs')
    if traces[0] != traces[1] or len(summary['negative_rejections']) != 3:
        raise ValueError('Crosswalk vehicle control or negative set differs')
    for marked_row, outside_row in zip(*source_pairs):
        fixed = ('native_frame', 'time_s', 'pedestrian_id', 'vehicle_id',
                 'vehicle_xy_m', 'vehicle_speed_mps', 'pedestrian_speed_mps')
        if (any(marked_row[key] != outside_row[key] for key in fixed) or
            marked_row['pedestrian_xy_m'][0] != outside_row['pedestrian_xy_m'][0] or
            abs(outside_row['pedestrian_xy_m'][1] - marked_row['pedestrian_xy_m'][1] - 4) > 1e-9 or
            any(abs(b[1] - a[1] - 4) > 1e-9 or a[0] != b[0]
                for a, b in zip(marked_row['pedestrian_footprint_xy_m'],
                                outside_row['pedestrian_footprint_xy_m']))):
            raise ValueError('Crosswalk controlled pair changes nonlocation source')
    for negative in summary['negative_rejections']:
        try:
            measure(negative['folder'])
        except ValueError as error:
            if negative['expected_error'] not in str(error):
                raise
        else:
            raise ValueError('Crosswalk damaged source accepted')
    return {'independent_audit': 'pass', 'authored_native_crosswalk_roads': 1,
            'controlled_synthetic_cases': 2, 'source_negative_rejections': 3,
            'physical_crossref_cases_constructed': 0}


if __name__ == '__main__':
    print(json.dumps(audit()))

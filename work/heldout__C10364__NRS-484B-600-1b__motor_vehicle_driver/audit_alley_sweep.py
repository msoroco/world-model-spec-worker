"""Independent source-bound audit of the three synthetic alley offset points."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

from shapely.geometry import Polygon


root = Path(__file__).resolve().parent
repo = root.parents[1]
read = lambda path: json.loads(path.read_text())
digest = lambda data: sha256(data.encode()).hexdigest()


def audit(records):
    if len(records) != 3:
        raise ValueError('Three exact finite alley points required')
    ordered = sorted(records, key=lambda item: item['offset'])
    if [round(item['offset'], 2) for item in ordered] != [1.5, 1.95, 2.4]:
        raise ValueError('Frozen authored alley offsets changed')
    first = ordered[0]
    gaps = []
    for item in ordered:
        config, sources, receipt, rows = (item[key] for key in
                                         ('config', 'sources', 'receipt', 'rows'))
        for key in ('selected_case_id', 'law_id', 'cell_id', 'actor'):
            if key not in config:
                raise ValueError('Selected alley identity missing')
        if (config['pedestrian_offset_m'] != item['offset'] or
                config['target_speed_mps'] != 5.0 or
                config['protected_interest'] != 'person' or
                config['duration_s'] != 8 or config['rate_hz'] != 20 or
                config['frames'] != 160):
            raise ValueError('Alley sweep setpoint or fixed exposure changed')
        for key in ('law_id', 'cell_id', 'actor', 'alley_direction',
                    'alley_width_m', 'alley_polygon_xy', 'alley_polygon_source'):
            if config[key] != first['config'][key]:
                raise ValueError('Alley sweep fixed context changed')
        for name in ('trace.jsonl', 'video_frames.jsonl', 'ego_motion.jsonl'):
            if sources[name] != first['sources'][name]:
                raise ValueError('Alley sweep original motion/frame source changed')
        if not rows or len(rows) != len(first['rows']):
            raise ValueError('Alley sweep original footprint count changed')
        for index, row in enumerate(rows):
            reference = first['rows'][index]
            for key in ('frame', 'time_s', 'ego_id', 'pedestrian_id',
                        'property_id', 'ego_corners', 'property_corners'):
                if row[key] != reference[key]:
                    raise ValueError('Alley sweep original fixed participant changed')
            expected_shift = item['offset'] - first['offset']
            for point, original in zip(row['pedestrian_corners'],
                                       reference['pedestrian_corners']):
                if abs(point[0]-original[0]) > 1e-9 or abs(
                        point[1]-original[1]-expected_shift) > 1e-9:
                    raise ValueError('Alley sweep original person footprint differs from authored point')
        value = receipt['measurement_examples']['alley_original_exposure']['value']
        if (value['source_sha256']['participant_footprints.jsonl'] !=
                digest(sources['participant_footprints.jsonl'])):
            raise ValueError('Alley sweep measured original footprint hash differs')
        independent = min(Polygon(row['ego_corners']).distance(
            Polygon(row['pedestrian_corners'])) for row in rows)
        if abs(independent-value['minimum_pedestrian_gap_m']) > 1e-9:
            raise ValueError('Alley sweep original measured gap differs')
        gaps.append(independent)
    if not gaps[0] < gaps[1] < gaps[2]:
        raise ValueError('Alley sweep source-measured gaps are not ordered')
    return {'authored_offsets_m': [item['offset'] for item in ordered],
            'original_measured_minimum_pedestrian_gaps_m': gaps,
            'legal_judgment': None, 'physical_acceptance_claimed': False}


def load_records():
    manifest = read(root / 'probe-compatibility-manifest.json')
    proposal = read(root / 'proposals/cases.json')
    points = {case['case_id']: case['sweep_point']['pedestrian_offset_m']
              for case in proposal['cases'] if case['target_type'] == 'judgment_sweep'}
    records = []
    for entry in manifest['cases']:
        if entry['case_id'] not in points:
            continue
        construction = read(root / entry['construction'])
        config = json.loads(next(file['content'] for file in construction['files']
                                 if file['path'] == 'config.json'))
        recipe = read(repo / entry['fixture_recipe'])
        fixture = read(repo / recipe['generator']['source'])
        if sha256((repo / recipe['generator']['source']).read_bytes()).hexdigest() != recipe['generator']['sha256']:
            raise ValueError('Alley sweep diagnostic source changed')
        sources = fixture['files']
        rows = [json.loads(line) for line in sources['participant_footprints.jsonl'].splitlines()]
        records.append({'offset': points[entry['case_id']], 'config': config,
                        'sources': sources, 'rows': rows,
                        'receipt': read(root / entry['compatibility']['receipt'])})
    return records


if __name__ == '__main__':
    records = load_records()
    print(json.dumps(audit(records), indent=2))
    negative = deepcopy(records)
    negative[0]['config']['pedestrian_offset_m'] = 1.8
    try:
        audit(negative)
    except ValueError as error:
        print('Tampered selected placement rejected: ' + str(error))
    else:
        raise ValueError('Tampered selected placement was accepted')

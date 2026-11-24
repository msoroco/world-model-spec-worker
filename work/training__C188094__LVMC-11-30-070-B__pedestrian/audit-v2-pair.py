"""Independent CPU audit of the two diagnostic current-v2 saved attempts."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(attempts, saved):
    records = []
    for number in (1, 2):
        prefix = f'v2-probe{number}'
        entry = read(HERE / f'{prefix}-manifest.json')['cases'][0]
        construction = HERE / entry['construction']
        compatibility = read(HERE / f'{prefix}-compatibility.json')
        processing = read(HERE / f'{prefix}-processing.json')
        recipe = read(HERE / f'{prefix}-fixture-recipe.json')
        attempt = attempts[number]
        saved_dir = saved[number]
        if sha(construction) != entry['construction_sha256']:
            raise ValueError(f'Probe {number} construction changed')
        if compatibility['passed'] is not True or compatibility['construction_sha256'] != sha(construction):
            raise ValueError(f'Probe {number} compatibility failed')
        if processing['passed'] is not True or processing['recorded_only'] is not True or processing['originals_preserved'] is not True:
            raise ValueError(f'Probe {number} saved processing failed')
        if processing['timestamp_joins']['frames'] != 600:
            raise ValueError(f'Probe {number} frame joins incomplete')
        for source in recipe['sources']:
            path = source['path']
            if sha(attempt / path) != source['sha256']:
                raise ValueError(f'Probe {number} source changed: {path}')
        negative = HERE / f'{prefix}-negative-analysis.log'
        if sha(negative) != compatibility['negative_log_sha256']:
            raise ValueError(f'Probe {number} source-negative log changed')
        report = read(saved_dir / 'analysis/analysis-report.json')
        result = read(saved_dir / 'analysis/result.json')
        if result['accepted'] is not False or result['legal_verdict_claimed'] is not False:
            raise ValueError(f'Probe {number} claims acceptance or legal result')
        measurement = report['measurements']['business_district_crossing_path']['value']
        if measurement['legal_compliance'] != 'unassessed' or measurement['business_district_physical_status'] != 'pending_independent_review':
            raise ValueError(f'Probe {number} unsupported district or legal finding')
        config = next(f['content'] for f in read(construction)['files'] if f['path'] == 'config.json')
        config = json.loads(config)
        records.append((config, measurement, entry, compatibility, processing))
    first, second = records
    config1, config2 = first[0].copy(), second[0].copy()
    for config in (config1, config2):
        for key in ('case_id', 'selected_case_id', 'crossing_case'):
            config.pop(key)
        config['case'].pop('case_id')
    if config1 != config2:
        raise ValueError('Linked case fixed conditions changed')
    a, b = first[1], second[1]
    if a['roadway_entry_point_m']['x'] != 0 or b['roadway_entry_point_m']['x'] != 12:
        raise ValueError('Controlled crossing position changed')
    if a['roadway_entry_point_m']['y'] != b['roadway_entry_point_m']['y'] or a['roadway_entry_frame'] != b['roadway_entry_frame']:
        raise ValueError('Crossing timing or longitudinal entry changed')
    if a['roadway_frames_outside_all_crosswalks'] != 0 or b['roadway_frames_outside_all_crosswalks'] != 121:
        raise ValueError('Diagnostic crossing difference changed')
    return {
        'format': 'c188094-independent-v2-pair-cpu-audit', 'passed': True,
        'case_ids': [first[2]['case_id'], second[2]['case_id']],
        'construction_sha256': [first[2]['construction_sha256'], second[2]['construction_sha256']],
        'compatibility_sha256': [sha(HERE / f'v2-probe{n}-compatibility.json') for n in (1, 2)],
        'processing_sha256': [sha(HERE / f'v2-probe{n}-processing.json') for n in (1, 2)],
        'source_count_each': [len(read(HERE / f'v2-probe{n}-fixture-recipe.json')['sources']) for n in (1, 2)],
        'frames_each': [first[4]['timestamp_joins']['frames'], second[4]['timestamp_joins']['frames']],
        'diagnostic_crossing_x_m': [0, 12], 'diagnostic_outside_crosswalk_frames': [0, 121],
        'native_physical_observed': False, 'business_district_confirmed': False,
        'full_body_footprint_confirmed': False, 'legal_verdict_claimed': False,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for number in (1, 2):
        parser.add_argument(f'--attempt{number}', type=Path, required=True)
        parser.add_argument(f'--saved{number}', type=Path, required=True)
    args = parser.parse_args()
    proof = audit({1: args.attempt1, 2: args.attempt2}, {1: args.saved1, 2: args.saved2})
    (HERE / 'v2-pair-independent-audit.json').write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps(proof))

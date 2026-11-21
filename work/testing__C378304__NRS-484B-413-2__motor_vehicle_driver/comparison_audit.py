"""Source-hashed CPU comparison isolation audit for the eight C378304 cases."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ROOT = REPO / '.runtime-work/c378304-final'
NAMES = ('business_distance', 'business_interruption', 'weather', 'other_area_distance')

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def require(test, message):
    if not test:
        raise ValueError(message)

def audit(index, mutate_camera=False):
    plan = json.loads((HERE / 'case-plan.json').read_text())
    members = plan['comparisons'][index]['case_ids']
    require(len(members) in (2, 3), 'Comparison member count differs')
    rows = []
    for cid in members:
        slug = cid.split('__')[-1]
        folder = ROOT / slug / 'primary/compat'
        config = json.loads((folder / 'config.json').read_text())
        report = json.loads((folder / 'analysis-report.json').read_text())
        require(config['selected_case_id'] == cid and report['case_id'] == cid,
                'Comparison source identity differs')
        for name, digest in report['source_hashes'].items():
            require(sha(folder / name) == digest, 'Comparison source hash differs: ' + name)
        source = report['source_report']
        rows.append({'case_id': cid, 'config': config, 'report': report,
                     'source_sha256': sha(folder / 'analysis-report.json'),
                     'measured_distance_m': source['turn_onset']['continuous_right_signal_distance_m'],
                     'boundary_m': source['required_distance_m'],
                     'meets_boundary': source['observed_continuous_distance_meets_boundary']})
    if mutate_camera:
        rows[-1]['config']['cameras'][0]['width'] += 1
    for key in ('map_path', 'map_sha256', 'course', 'requested_speed_mps',
                'rate_hz', 'duration_s', 'cameras', 'actor'):
        require(all(row['config'][key] == rows[0]['config'][key] for row in rows),
                'Fixed comparison condition differs: ' + key)
    distances = [row['measured_distance_m'] for row in rows]
    if index in (0, 3):
        require(all(row['config']['weather'] == rows[0]['config']['weather'] for row in rows),
                'Distance comparison weather differs')
        require(all(a < b for a, b in zip(distances, distances[1:])),
                'Measured continuous distances lack strict below/at/above order')
        require([row['meets_boundary'] for row in rows] == [False, True, True],
                'Measured boundary classifications differ')
        require(all(row['boundary_m'] == rows[0]['boundary_m'] for row in rows),
                'Distance threshold differs within fixed district')
    elif index == 1:
        require(rows[0]['config']['indicator_start_m'] == rows[1]['config']['indicator_start_m'],
                'Interruption comparison changes planned indicator onset')
        require(rows[0]['config']['weather'] == rows[1]['config']['weather'],
                'Interruption comparison changes weather')
        require(distances[0] > distances[1] and rows[0]['meets_boundary'] and
                not rows[1]['meets_boundary'], 'Interruption is not source measured')
    else:
        require(rows[0]['config']['indicator_start_m'] == rows[1]['config']['indicator_start_m'],
                'Weather comparison changes planned indicator onset')
        require(rows[0]['config']['weather'] != rows[1]['config']['weather'],
                'Weather comparison lacks changed weather')
        require(abs(distances[0] - distances[1]) < 1e-8 and
                rows[0]['meets_boundary'] == rows[1]['meets_boundary'],
                'Weather comparison changes signal distance or classification')
    return {'format': 'worker-c378304-comparison-audit', 'comparison': NAMES[index],
            'members': [{k: row[k] for k in ('case_id', 'source_sha256', 'measured_distance_m',
                         'boundary_m', 'meets_boundary')} for row in rows],
            'fixed_conditions_passed': True, 'diagnostic_fixture': True,
            'legal_conclusion': 'unresolved'}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', choices=NAMES, required=True)
    parser.add_argument('--mutate-camera', action='store_true')
    parser.add_argument('--output')
    args = parser.parse_args()
    result = audit(NAMES.index(args.comparison), args.mutate_camera)
    if args.output:
        Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, sort_keys=True))

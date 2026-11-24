"""Independently compare three same-map diagnostic crossing cases."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'native'))
from body_footprint import measure_evidence_body
from unmarked_source_gate import validate as validate_unmarked


def read(path):
    return json.loads(path.read_text())


def lines(path):
    return [json.loads(item) for item in path.read_text().splitlines() if item]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(attempts, saved):
    manifest = read(HERE / 'v2-common-intersection-manifest.json')
    if len(manifest['cases']) != 3:
        raise ValueError('Three exact comparison cases required')
    configs, roads, measurements, body_values = [], [], [], []
    proof_hashes = []
    for number, entry in enumerate(manifest['cases'], 1):
        construction = HERE / entry['construction']
        if sha(construction) != entry['construction_sha256']:
            raise ValueError(f'Case {number} exact construction differs')
        proposal = read(construction)
        config = json.loads(next(f['content'] for f in proposal['files'] if f['path'] == 'config.json'))
        configs.append(config)
        attempt = attempts[number]
        saved_dir = saved[number]
        road_hash = sha(attempt / 'road.xodr')
        roads.append(road_hash)
        suffix = f'v2-common-probe{number}'
        recipe_name = f'v2-common{number}-fixture-recipe.json' if number < 3 else 'v2-probe3-fixture-recipe.json'
        recipe = read(HERE / recipe_name)
        for source in recipe['sources']:
            if sha(attempt / source['path']) != source['sha256']:
                raise ValueError(f'Case {number} original source changed: {source["path"]}')
        compatibility = read(HERE / f'{suffix}-compatibility.json')
        processing = read(HERE / f'{suffix}-processing.json')
        negative = HERE / f'{suffix}-negative-analysis.log'
        if compatibility['passed'] is not True or compatibility['construction_sha256'] != sha(construction):
            raise ValueError(f'Case {number} public compatibility differs')
        if compatibility['negative_log_sha256'] != sha(negative):
            raise ValueError(f'Case {number} source-negative log differs')
        if processing['passed'] is not True or processing['recorded_only'] is not True or processing['originals_preserved'] is not True or processing['timestamp_joins']['frames'] != 600:
            raise ValueError(f'Case {number} recorded-only source check differs')
        context = read(attempt / 'crossing-context.json')
        validate_unmarked(context, (attempt / 'road.xodr').read_bytes(),
                          {'sidewalk-edges.json': (attempt / 'sidewalk-edges.json').read_bytes()})
        report = read(saved_dir / 'analysis/analysis-report.json')
        result = read(saved_dir / 'analysis/result.json')
        if result['accepted'] is not False or result['legal_verdict_claimed'] is not False:
            raise ValueError(f'Case {number} diagnostic claims acceptance')
        measured = report['measurements']['business_district_crossing_path']['value']
        measurements.append((measured['roadway_entry_point_m']['x'],
                             measured['entry_crosswalk_kinds'],
                             measured['roadway_frames_outside_all_crosswalks']))
        body = measure_evidence_body(lines(attempt / 'actor-poses.jsonl'),
                                     lines(attempt / 'capture/evidence.jsonl'), context)
        body_values.append(body['roadway_body_frames_not_wholly_inside_one_crosswalk'])
        proof_hashes.append({'construction': sha(construction),
                             'compatibility': sha(HERE / f'{suffix}-compatibility.json'),
                             'negative': sha(negative),
                             'processing': sha(HERE / f'{suffix}-processing.json')})
    if len(set(roads)) != 1:
        raise ValueError('Comparison Native road geometry differs')
    fixed = []
    for config in configs:
        copy = json.loads(json.dumps(config))
        for key in ('case_id', 'selected_case_id', 'crossing_case'):
            copy.pop(key)
        copy['case'].pop('case_id')
        fixed.append(copy)
    if fixed[0] != fixed[1] or fixed[1] != fixed[2]:
        raise ValueError('Comparison fixed config policy differs')
    expected = [(0, ['marked'], 0), (12, [], 121), (21, ['unmarked'], 0)]
    if measurements != expected:
        raise ValueError('Diagnostic controlled crossing distinction differs')
    return {'format': 'c188094-common-intersection-cpu-comparison-audit', 'passed': True,
            'manifest_sha256': sha(HERE / 'v2-common-intersection-manifest.json'),
            'shared_road_xodr_sha256': roads[0], 'same_config_except_case_and_crossing': True,
            'case_receipt_hashes': proof_hashes,
            'diagnostic_crossing_measurements': measurements,
            'diagnostic_body_outside_frames': body_values,
            'original_native_physical_observed': False,
            'business_district_confirmed': False, 'legal_verdict_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for number in (1, 2, 3):
        parser.add_argument(f'--attempt{number}', type=Path, required=True)
        parser.add_argument(f'--saved{number}', type=Path, required=True)
    args = parser.parse_args()
    result = audit({n: getattr(args, f'attempt{n}') for n in (1, 2, 3)},
                   {n: getattr(args, f'saved{n}') for n in (1, 2, 3)})
    (HERE / 'v2-common-intersection-independent-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))

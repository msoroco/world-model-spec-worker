"""Independently bind current-v2 probe 1 CPU proof to its exact sources."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def audit(attempt, saved):
    manifest = read(HERE / 'v2-probe1-manifest.json')
    entry = manifest['cases'][0]
    construction = HERE / entry['construction']
    contract = read(HERE / entry['measurement_contract'])
    recipe = read(HERE / 'v2-probe1-fixture-recipe.json')
    compatibility = read(HERE / 'v2-probe1-compatibility.json')
    processing = read(HERE / 'v2-probe1-processing.json')
    if sha(construction) != entry['construction_sha256']:
        raise ValueError('Exact construction hash changed')
    if contract['case_id'] != entry['case_id'] or contract['negative']['remove'] != ['crossing-context.json']:
        raise ValueError('Selected measurement contract changed')
    if compatibility['passed'] is not True or compatibility['case_id'] != entry['case_id'] or compatibility['construction_sha256'] != sha(construction):
        raise ValueError('Public compatibility identity or status differs')
    expected = {'actual_analysis', 'native_validation', 'lean_decoder', 'render', 'final_decode',
                'acquisition_unchanged', 'derived_outputs_rebuilt', 'four_camera_sources',
                'selected_measurements', 'negative_case_source'}
    if not expected <= set(compatibility['checks']):
        raise ValueError('Public compatibility check coverage incomplete')
    negative = HERE / 'v2-probe1-negative-analysis.log'
    if sha(negative) != compatibility['negative_log_sha256'] or contract['negative']['error_contains'] not in negative.read_text():
        raise ValueError('Case source negative proof changed')
    if compatibility['measurement_contract_sha256'] != sha(HERE / entry['measurement_contract']) or compatibility['fixture_recipe_sha256'] != sha(HERE / 'v2-probe1-fixture-recipe.json'):
        raise ValueError('Measurement contract or fixture recipe changed')
    if compatibility['fixture_generator_sha256'] != sha(ROOT / 'runtime/scenario_pipeline/worker_exchange/fixture_generator.py'):
        raise ValueError('Diagnostic generator binding changed')
    for source in recipe['sources']:
        if sha(Path(attempt) / source['path']) != source['sha256']:
            raise ValueError('Original acquisition source changed: ' + source['path'])
    if processing['passed'] is not True or processing['recorded_only'] is not True or processing['missing_evidence'] is not False or processing['originals_preserved'] is not True:
        raise ValueError('Recorded-only processing incomplete')
    if processing['analysis_revision']['construction_sha256'] != sha(construction) or processing['timestamp_joins']['frames'] != 600:
        raise ValueError('Saved revision or original frame count differs')
    for name in ('trace.jsonl', 'actor-poses.jsonl', 'video_frames.jsonl', 'crossing-context.json', 'road.xodr'):
        if processing['original_source_hashes'][name] != sha(Path(attempt) / name):
            raise ValueError('Saved original source hash differs: ' + name)
    result = read(Path(saved) / 'analysis/result.json')
    report = read(Path(saved) / 'analysis/analysis-report.json')
    measurement = report['measurements']['business_district_crossing_path']['value']
    if result['case_id'] != entry['case_id'] or result['accepted'] is not False or result['legal_verdict_claimed'] is not False:
        raise ValueError('Diagnostic result claims acceptance or wrong case')
    if any(check['physical_cause_confirmed'] is not False for check in result['target_checks']):
        raise ValueError('Unreviewed physical cause claimed')
    if measurement['entire_roadway_point_path_within_crosswalk'] is not True or measurement['roadway_frames_outside_all_crosswalks'] != 0:
        raise ValueError('Positive crossing path measurement differs')
    return {'format': 'c188094-independent-v2-probe1-cpu-audit', 'passed': True,
            'case_id': entry['case_id'], 'construction_sha256': sha(construction),
            'compatibility_sha256': sha(HERE / 'v2-probe1-compatibility.json'),
            'processing_sha256': sha(HERE / 'v2-probe1-processing.json'),
            'negative_log_sha256': sha(negative), 'original_frame_count': 600,
            'source_count': len(recipe['sources']), 'diagnostic_only': True,
            'native_physical_observed': False, 'legal_verdict_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--saved', type=Path, required=True)
    args = parser.parse_args()
    proof = audit(args.attempt, args.saved)
    (HERE / 'v2-probe1-independent-audit.json').write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps(proof))

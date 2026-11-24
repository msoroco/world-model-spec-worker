"""Independent source/hash audit for the diagnostic unmarked exact case."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'native'))
from unmarked_source_gate import validate as validate_unmarked
from body_footprint import measure_evidence_body


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def audit(attempt, saved):
    entry = read(HERE / 'v2-three-case-manifest.json')['cases'][2]
    construction = HERE / entry['construction']
    recipe = read(HERE / 'v2-probe3-fixture-recipe.json')
    compatibility = read(HERE / 'v2-probe3-compatibility.json')
    processing = read(HERE / 'v2-probe3-processing.json')
    negative = HERE / 'v2-probe3-negative-analysis.log'
    if sha(construction) != entry['construction_sha256']:
        raise ValueError('Exact unmarked construction changed')
    if compatibility['passed'] is not True or compatibility['case_id'] != entry['case_id'] or compatibility['construction_sha256'] != sha(construction):
        raise ValueError('Public unmarked compatibility differs')
    if compatibility['negative_log_sha256'] != sha(negative) or 'Missing required source: sidewalk-edges.json' not in negative.read_text():
        raise ValueError('Unmarked source-negative proof differs')
    if processing['passed'] is not True or processing['recorded_only'] is not True or processing['originals_preserved'] is not True:
        raise ValueError('Unmarked saved processing differs')
    if processing['analysis_revision']['construction_sha256'] != sha(construction) or processing['timestamp_joins']['frames'] != 600:
        raise ValueError('Unmarked saved construction or frames differ')
    for source in recipe['sources']:
        if sha(attempt / source['path']) != source['sha256']:
            raise ValueError('Unmarked original source changed: ' + source['path'])
    context = read(attempt / 'crossing-context.json')
    source_gate = validate_unmarked(context, (attempt / 'road.xodr').read_bytes(),
                                    {'sidewalk-edges.json': (attempt / 'sidewalk-edges.json').read_bytes()})
    body = measure_evidence_body(lines(attempt / 'actor-poses.jsonl'),
                                 lines(attempt / 'capture/evidence.jsonl'), context)
    report = read(saved / 'analysis/analysis-report.json')
    measurement = report['measurements']['business_district_crossing_path']
    if measurement['value']['entry_crosswalk_kinds'] != ['unmarked'] or measurement['value']['legal_compliance'] != 'unassessed':
        raise ValueError('Diagnostic unmarked measurement changed')
    if measurement['sources']['sidewalk-edges.json'] != sha(attempt / 'sidewalk-edges.json'):
        raise ValueError('Saved unmarked sidewalk source hash differs')
    result = read(saved / 'analysis/result.json')
    if result['accepted'] is not False or result['legal_verdict_claimed'] is not False:
        raise ValueError('Unmarked diagnostic claims acceptance')
    return {'format': 'c188094-unmarked-v2-cpu-audit', 'passed': True,
            'case_id': entry['case_id'], 'construction_sha256': sha(construction),
            'compatibility_sha256': sha(HERE / 'v2-probe3-compatibility.json'),
            'negative_log_sha256': sha(negative),
            'processing_sha256': sha(HERE / 'v2-probe3-processing.json'),
            'source_count': len(recipe['sources']), 'frame_count': 600,
            'source_gate': source_gate, 'diagnostic_body_outside_frames': body['roadway_body_frames_not_wholly_inside_one_crosswalk'],
            'diagnostic_point_outside_frames': body['roadway_point_frames_outside_crosswalk'],
            'original_native_physical_observed': False, 'business_district_confirmed': False,
            'legal_verdict_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--saved', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.attempt, args.saved)
    (HERE / 'v2-probe3-independent-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))

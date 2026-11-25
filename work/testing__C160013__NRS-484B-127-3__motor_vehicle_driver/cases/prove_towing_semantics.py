"""Validate a three-case semantic draft without changing selected delivery."""
import hashlib
import json
import os
import shutil
import sys
from copy import deepcopy
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
STAGE = REPO / '.runtime-work/c160013-towing-semantic-stage'
ROOT = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '')).resolve()
if not ROOT.is_relative_to((REPO / '.runtime-work').resolve()):
    raise RuntimeError('Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work')
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.semantic_delivery import validate


def main():
    if STAGE.exists():
        shutil.rmtree(STAGE)
    (STAGE / 'cases').mkdir(parents=True)
    shutil.copytree(PACKAGE / 'proposals', STAGE / 'proposals')
    assignment = json.loads((REPO / 'inputs' / PACKAGE.name / 'assignment.json').read_text())
    manifest = json.loads((PACKAGE / 'execution-manifest.json').read_text())
    for entry in manifest['cases']:
        source = PACKAGE / entry['construction']
        target = STAGE / entry['construction']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    towing = json.loads((PACKAGE / 'towing-diagnostic-manifest.json').read_text())['cases'][0]
    tow_entry = {'case_id': towing['case_id'],
                 'construction': towing['construction'], 'kind': 'delivery'}
    manifest['cases'].append(tow_entry)
    shutil.copyfile(PACKAGE / towing['construction'], STAGE / towing['construction'])
    cases_path = STAGE / 'proposals/cases.json'
    cases = json.loads(cases_path.read_text())
    wide = next(item for item in cases['cases'] if item['case_id'].endswith('__entrant_can_occupy_gap'))
    tow = deepcopy(wide)
    tow['case_id'] = towing['case_id']
    tow['rationale'] = 'Full drawing-and-drawn body gap and entrant occupancy; statutory danger unresolved.'
    tow['paired_probe_id'] = 'caravan_gap_occupancy'
    tow['recording_description'] = json.loads((STAGE / towing['construction']).read_text())['recording_description']
    cases['cases'].append(tow)
    cases_path.write_text(json.dumps(cases, indent=2) + '\n')
    index_path = STAGE / 'proposals/semantic-index.json'
    index = json.loads(index_path.read_text())
    index['stages']['cases']['sha256'] = hashlib.sha256(cases_path.read_bytes()).hexdigest()
    index_path.write_text(json.dumps(index, indent=2) + '\n')
    result = validate(STAGE, assignment, manifest)
    if result['selected_cases'] != 3:
        raise ValueError('Three selected cases required in staged draft')
    print(json.dumps({'format': 'worker-towing-semantic-diagnostic-proof',
                      'case_id': towing['case_id'], 'selected_cases': 3,
                      'stage_count': result['stage_count'],
                      'canonical_delivery_unchanged': True}, sort_keys=True))


if __name__ == '__main__':
    main()

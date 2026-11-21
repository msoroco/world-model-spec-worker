"""Record the distinct newly laid controlled pair before exact bundle promotion."""
import hashlib
import json
from pathlib import Path

from newly_laid_plan import ASSIGNMENT, ROUTES

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
ROOT = PACKAGE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    assignment_path = ROOT / 'inputs' / ASSIGNMENT / 'assignment.json'
    assignment = json.loads(assignment_path.read_text())
    law = assignment['law']
    if (law['id'] != 'LVMC-11-22-100' or
            'newly laid or repaired' not in law['text'] or
            assignment['cell_id'] != 'C183370' or
            assignment['actor'] != 'motor_vehicle_driver'):
        raise ValueError('Newly laid pair must remain under exact frozen law/cell/actor')
    pair = []
    for short, contact in zip(ROUTES, (True, False)):
        pair.append({
            'case_id': ASSIGNMENT + '__' + short,
            'target_law_id': law['id'],
            'target_type': 'attempt',
            'comparison_variable': 'requested_pavement_crossing',
            'requested_contact': contact,
            'condition': 'newly_laid',
            'frames': 600, 'rate_hz': 20,
            'required_original_sources': [
                'live map and surveyed laid-surface polygon',
                'fixed warning-person identity, act, content and time',
                'independent newly laid surface history and camera review',
                'operator paving-activity evidence',
                '600 joined Native actor/body/frame rows',
                'four full-duration original camera streams'],
            'original_native_observed': False,
        })
    return {
        'format': 'c183370-newly-laid-controlled-pair-draft-v1',
        'assignment_id': ASSIGNMENT, 'law_id': law['id'],
        'law_text_sha256': hashlib.sha256(law['text'].encode()).hexdigest(),
        'frozen_assignment_sha256': sha(assignment_path),
        'existing_case_plan_sha256': sha(PACKAGE / 'case-plan.json'),
        'survey_validator': 'native/newly_laid_plan.py',
        'survey_validator_sha256': sha(HERE / 'newly_laid_plan.py'),
        'cases': pair,
        'comparison': {
            'comparison_id': ASSIGNMENT + '__comparison_newly_laid',
            'case_ids': [row['case_id'] for row in pair],
            'deliberate_differences': ['requested_pavement_crossing'],
            'fixed_conditions': ['C183370 cell', 'motor vehicle actor',
                                 'surveyed newly laid polygon',
                                 'warning person and source-reviewed warning act',
                                 'surface history', 'operator exception status',
                                 'weather', 'camera/capture profile',
                                 'noncompared controller settings']},
        'selection_status': 'draft_cpu_construction_not_in_exact_manifest',
        'original_native_observed': False,
        'physical_or_legal_acceptance_claimed': False,
    }


if __name__ == '__main__':
    path = PACKAGE / 'draft-newly-laid-controlled-pair.json'
    if path.exists():
        raise ValueError('Retain prior newly laid draft')
    path.write_text(json.dumps(build(), indent=2, sort_keys=True) + '\n')
    print(json.dumps({'draft_sha256': sha(path), 'cases': len(build()['cases'])},
                     sort_keys=True))

"""Bind each selected C80909 requirement to a saved original-source output."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PLAN = json.loads((ROOT / 'case-plan.json').read_text())
KEYS = {
    0: ('site_context_sources', 'object', ['divider_context.json', 'site_source_receipt.json']),
    1: ('starts_on_right_hand_roadway', 'boolean', ['divider_context.json','movement_history.jsonl','video_frames.jsonl']),
    2: ('any_body_overlap_outside_opening', 'boolean', ['divider_context.json','barrier_receipt.json','movement_history.jsonl','video_frames.jsonl']),
    3: ('public_authority_establishment_judgment', 'text', ['site_source_receipt.json']),
    4: ('observed_turn_angle_degrees', 'number', ['movement_history.jsonl','video_frames.jsonl']),
    5: ('samples', 'array', ['movement_history.jsonl','video_frames.jsonl']),
}


def build():
    for case in PLAN['cases']:
        case_id = case['case_id']
        requirements = []
        for index, disposition in enumerate(PLAN['requirement_dispositions']):
            if case_id not in disposition['case_ids']:
                continue
            key, value_type, inputs = KEYS[index]
            requirements.append({
                'disposition_index': index, 'requirement': disposition['requirement'],
                'source': disposition['source'], 'output_key': key,
                'method': 'saved_finalizer.finalize original-source measurement',
                'value_type': value_type,
                'kind': 'sourced_context' if index in (0,3) else 'measured',
                'inputs': inputs})
        contract = {'format': 'worker-measurement-contract', 'case_id': case_id,
                    'requirements': requirements,
                    'negative': {'remove': ['movement_history.jsonl'],
                                 'error_contains': 'Missing original source: movement_history.jsonl'},
                    'statutory_judgment': 'unresolved; original source review required'}
        suffix = case_id.split('__')[-1]
        path = ROOT / 'measurement-contract.json' if suffix == 'left_through_opening' else ROOT / 'cases' / suffix / 'measurement-contract.json'
        path.write_text(json.dumps(contract, indent=2) + '\n')


if __name__ == '__main__':build()

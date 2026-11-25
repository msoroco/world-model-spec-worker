"""Bind C126120 U-turn requirements to exact saved source outputs."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PLAN = json.loads((ROOT / 'case-plan.json').read_text())
KEYS = {
    0: ('site_context_sources', 'object', ['divider_context.json', 'site_source_receipt.json']),
    1: ('starts_on_right_hand_roadway', 'boolean',
        ['divider_context.json', 'movement_history.jsonl', 'video_frames.jsonl']),
    2: ('any_body_overlap_outside_opening', 'boolean',
        ['divider_context.json', 'barrier_receipt.json', 'movement_history.jsonl', 'video_frames.jsonl']),
    3: ('observed_turn_angle_degrees', 'number', ['movement_history.jsonl', 'video_frames.jsonl']),
    4: ('multiple_movement_observed', 'boolean', ['movement_history.jsonl', 'video_frames.jsonl']),
    5: ('reverse_motion_observed', 'boolean', ['movement_history.jsonl', 'video_frames.jsonl']),
    6: ('public_authority_establishment_judgment', 'text', ['site_source_receipt.json']),
}


def build():
    for case in PLAN['cases']:
        case_id = case['case_id']
        requirements = []
        for index, disposition in enumerate(PLAN['requirement_dispositions']):
            if case_id not in disposition['case_ids']:
                continue
            output_key, value_type, inputs = KEYS[index]
            requirements.append({
                'disposition_index': index, 'requirement': disposition['requirement'],
                'source': disposition['source'], 'output_key': output_key,
                'method': 'finalize_delivery', 'value_type': value_type,
                'kind': 'sourced_context' if index in (0, 6) else 'measured',
                'inputs': inputs})
        contract = {'format': 'worker-measurement-contract', 'case_id': case_id,
                    'requirements': requirements,
                    'negative': {'remove': ['movement_history.jsonl'],
                                 'error_contains': 'Missing required source: movement_history.jsonl'},
                    'statutory_judgment': 'unresolved; original site and authority review required'}
        suffix = case_id.split('__')[-1]
        target = ROOT / ('measurement-contract.json' if suffix.startswith('source_verified_single')
                         else f'cases/{suffix}/measurement-contract.json')
        target.write_text(json.dumps(contract, indent=2) + '\n')


if __name__ == '__main__':
    build()

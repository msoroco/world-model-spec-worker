"""Bind every selected statutory source topic to saved-source measurements."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PLAN = json.loads((ROOT / 'case-plan.json').read_text())
MANIFEST = ROOT / 'execution-manifest.json'
ROWS = PLAN['requirement_dispositions']

METHODS = {
    0: ('school_zone_observation', ['school_zone_context.json', 'native_motion.jsonl',
                                    'video_frames.jsonl']),
    1: ('school_day_observation', ['school_zone_context.json']),
    2: ('half_hour_observation', ['school_zone_context.json']),
    3: ('beacon_exception_observation', ['school_zone_context.json', 'overview.mkv',
                                        'approach.mkv']),
    4: ('nonbeacon_sign_observation', ['school_zone_context.json',
                                     'reference_corner.mkv']),
    5: ('beacon_definition_observation', ['school_zone_context.json', 'overview.mkv',
                                         'approach.mkv']),
    6: ('motor_bus_scope_observation', ['school_zone_context.json',
                                       'children_context.jsonl', 'native_motion.jsonl']),
}


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        case_id = entry['case_id']
        name = case_id.rsplit('__', 1)[-1]
        requirements = []
        for index, disposition in enumerate(ROWS):
            if disposition['status'] != 'selected_required' or case_id not in disposition['case_ids']:
                continue
            method, inputs = METHODS[index]
            requirements.append({
                'disposition_index': index,
                'requirement': disposition['requirement'],
                'source': disposition['source'],
                'output_key': 'source_topic_' + str(index),
                'method': method,
                'value_type': 'object',
                'kind': 'measured' if index in (0, 6) else 'sourced_context',
                'inputs': inputs,
            })
        contract = {'format': 'worker-measurement-contract',
                    'case_id': case_id,
                    'requirements': requirements,
                    'negative': {'remove': ['school_zone_context.json'],
                                 'error_contains':
                                 'Missing required source: school_zone_context.json'}}
        path = HERE / 'selected' / name / 'measurement-contract.json'
        path.write_text(json.dumps(contract, indent=2) + '\n')
        entry['measurement_contract'] = str(path.relative_to(ROOT))
        entry['fixture_recipe'] = str((HERE / ('selected-recipe-' + name + '.json'))
                                      .relative_to(ROOT.parents[1]))
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'measurement_contracts': len(manifest['cases'])}, sort_keys=True))


if __name__ == '__main__':
    main()

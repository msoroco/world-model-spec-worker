"""Bind each selected statutory disposition to saved original-source outputs."""
import json
from pathlib import Path

from signal_scene import CASE_SUFFIXES


HERE = Path(__file__).resolve().parent
MEASUREMENTS = {
    'text-0': ('measure_signal_distance', 'signal_distance',
        ['signal-source.jsonl', 'body_history.jsonl', 'video_frames.jsonl']),
    'text-1': ('measure_weather_source', 'weather_source',
        ['capture/evidence.jsonl', 'video_frames.jsonl']),
    'reviewed-scope-0': ('measure_area_context', 'area_context',
        ['area-source.json', 'lane-source.json', 'video_frames.jsonl']),
    'reviewed-scope-1': ('measure_course_change', 'course_change',
        ['body_history.jsonl', 'signal-source.jsonl', 'video_frames.jsonl'])}


def main():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    for suffix in CASE_SUFFIXES:
        case_id = HERE.name + '__' + suffix
        rows = []
        for index, disposition in enumerate(plan['requirement_dispositions']):
            if case_id not in disposition['case_ids']:
                continue
            method, output, sources = MEASUREMENTS[disposition['requirement']]
            rows.append({'disposition_index': index,
                'requirement': disposition['requirement'],
                'source': disposition['source'], 'kind': 'measured',
                'method': method, 'output_key': output,
                'value_type': 'object', 'inputs': sources})
        contract = {'format': 'worker-measurement-contract',
            'case_id': case_id, 'status': 'selected_cpu_draft',
            'negative': {'remove': ['signal-source.jsonl'],
                'error_contains': 'Missing required source: signal-source.jsonl'},
            'requirements': rows, 'legal_compliance': 'unassessed'}
        path = HERE / ('measurement-' + suffix + '.json')
        path.write_text(json.dumps(contract, indent=2, allow_nan=False) + '\n')
    return len(CASE_SUFFIXES)


if __name__ == '__main__':
    print(main())

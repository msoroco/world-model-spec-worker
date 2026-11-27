"""Write exact saved-measurement contracts for three approach cases."""
import json
from pathlib import Path

from source_review import SOURCES

HERE = Path(__file__).resolve().parent
AID = HERE.name
INPUTS = ['approach-review.json', 'visibility-review.json',
          'native-speed.jsonl', 'video_frames.jsonl', 'trace.jsonl',
          'road.xodr', *(f'source_context/{name}.txt' for name in SOURCES),
          'overview.mkv', 'approach.mkv', 'reference_corner.mkv',
          'driver_reference.mkv']


def main():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    disposition = plan['requirement_dispositions'][0]
    for index in range(1, 4):
        case = AID + f'__probe_0{index}'
        contract = {'format': 'worker-measurement-contract', 'case_id': case,
                    'requirements': [{'disposition_index': 0,
                        'requirement': disposition['requirement'],
                        'source': disposition['source'], 'kind': 'measured',
                        'method': 'measure_approach_speed',
                        'output_key': 'approach_speed', 'value_type': 'object',
                        'inputs': INPUTS}],
                    'negative': {'remove': ['source_context/road_curb_route.txt'],
                        'error_contains': 'Missing required source: source_context/road_curb_route.txt'}}
        path = HERE / 'cases' / f'probe_0{index}' / 'measurement-contract.json'
        path.write_text(json.dumps(contract, indent=2) + '\n')
    print('Three exact approach-speed contracts written')


if __name__ == '__main__':
    main()

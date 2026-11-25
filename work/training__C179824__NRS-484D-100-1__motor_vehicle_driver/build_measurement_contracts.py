"""Build exact selected device-branch measurement contracts."""
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
SOURCES = ['vehicle-lamps.jsonl', 'video_frames.jsonl', 'road.xodr',
           'lamp-context.json', 'lamp-source-review.json',
           'highway-review.json', 'vehicle-class-review.json',
           'device-content-review.json', 'device-authority-review.json',
           'device-placement-review.json', 'device-timing-review.json']


def main():
    for suffix in ('controlled_1', 'controlled_2'):
        case = ASSIGNMENT + '__' + suffix
        contract = {'format': 'worker-measurement-contract', 'case_id': case,
                    'requirements': [{'disposition_index': 0,
                                      'requirement': 'NRS-484D-100-1',
                                      'source': 'NRS 484D.100(1)',
                                      'output_key': 'lamp_device_measurement',
                                      'method': 'reviewed_measure',
                                      'value_type': 'object', 'kind': 'measured',
                                      'inputs': SOURCES}],
                    'negative': {'remove': ['device-authority-review.json'],
                                 'error_contains':
                                 'Missing required source: device-authority-review.json'}}
        path = HERE / 'cases' / suffix / 'measurement-contract.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(contract, indent=2) + '\n')
    print(json.dumps({'passed': True, 'cases': 2, 'sources_per_case': len(SOURCES)},
                     sort_keys=True))


if __name__ == '__main__':
    main()

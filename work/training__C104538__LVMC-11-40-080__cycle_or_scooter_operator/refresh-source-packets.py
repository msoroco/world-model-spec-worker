"""Add truthful pending-designation source packets to retained CPU fixtures."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    count = 0
    for source in sorted(HERE.glob('v2-*-source')):
        native = [json.loads(line) for line in (source / 'native_samples.jsonl').read_text().splitlines()]
        if len(native) != 600:
            raise ValueError('Expected 600 original-shaped native rows: ' + source.name)
        (source / 'scenario_geometry.json').write_text(json.dumps({
            'source': 'Synthetic rider diagnostic geometry; original Native designation unverified',
            'physical_verification': {'status': 'synthetic_diagnostic_only'},
            'directed_roadways': [], 'direction_sign_objects': [],
        }, allow_nan=False) + '\n')
        (source / 'scenario_rule_evidence.jsonl').write_text(''.join(json.dumps({
            'frame': row['native_frame'], 'time_s': row['time_s'],
            'value': {'devices': []}, 'provenance_kind': 'synthetic_fixture',
        }, allow_nan=False) + '\n' for row in native))
        count += 1
    print(json.dumps({'retained_sources': count}))


if __name__ == '__main__':
    main()

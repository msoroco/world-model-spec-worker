"""Record candidate Native assets for the unselected B(3) source review.

Blueprint names establish neither device design nor use by an impaired person.
The output is an inventory only and cannot satisfy mobility_eligibility.audit.
"""
import argparse
import json
from pathlib import Path


PATTERNS = ('vehicle.*wheelchair*', 'vehicle.*mobility*',
            'walker.*wheelchair*', 'static.prop.*wheelchair*')


def collect(library):
    found = {}
    for pattern in PATTERNS:
        for blueprint in library.filter(pattern):
            found.setdefault(blueprint.id, set()).add(pattern)
    return {
        'format': 'c143691-native-mobility-asset-inventory',
        'source_kind': 'native_blueprint_library_readback',
        'query_patterns': list(PATTERNS),
        'matches': [{'blueprint_id': key, 'matched_patterns': sorted(patterns)}
                    for key, patterns in sorted(found.items())],
        'device_design_established': False,
        'impaired_person_use_established': False,
        'frozen_actor_eligibility_established': False,
        'physical_capture_established': False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    output = Path(args.output).resolve()
    if output.exists():
        raise ValueError('Fresh Native inventory output required')
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    inventory = collect(client.get_world().get_blueprint_library())
    output.write_text(json.dumps(inventory, indent=2) + '\n')
    print(json.dumps({'output': str(output), 'matches': len(inventory['matches'])}))


if __name__ == '__main__':
    main()

"""CPU-only positive and damaged-source tests for the saved bus meter."""
import argparse
import json
import tempfile
from pathlib import Path

from measure_saved import measure


def test(source):
    source = Path(source).resolve()
    positive = measure(source)
    if (positive['frames_above_25_mph_in_zone'] != list(range(
            positive['first_zone_frame'], positive['last_zone_frame'] + 1)) or
            not positive['reviewed_activation_complete']):
        raise AssertionError('Synthetic positive did not demonstrate measured above-25 active-zone branch')
    negatives = {}
    mutations = {
        'missing_children': ('children_context.jsonl', None, 'Missing saved source: children_context.jsonl'),
        'missing_child_actor': ('children_context.jsonl', 'child', 'Child actor source does not join original frame'),
        'missing_zone_designation': ('school_zone_context.json', 'zone', 'Missing reviewed school-crossing-zone fact: zone_designated'),
        'one_beacon_light': ('school_zone_context.json', 'light', 'Operational beacon lacks source-reviewed sign and two yellow lights'),
        'missing_alternation': ('school_zone_context.json', 'alternate', 'Beacon flashing claim lacks alternating yellow evidence'),
        'stale_camera_binding': ('school_zone_context.json', 'camera', 'Context not bound to source camera bytes'),
    }
    with tempfile.TemporaryDirectory(prefix='c255451-negative-', dir=Path('.runtime-work').resolve()) as base:
        base = Path(base)
        for label, (filename, mutation, error) in mutations.items():
            target = base/label
            target.mkdir()
            for item in source.iterdir():
                if item.name == filename:
                    if mutation is None:
                        continue
                    data = item.read_text()
                    if filename.endswith('.jsonl'):
                        rows = [json.loads(line) for line in data.splitlines()]
                        rows[0]['children'].pop()
                        data = ''.join(json.dumps(row, separators=(',', ':'))+'\n' for row in rows)
                    else:
                        context = json.loads(data)
                        if mutation == 'zone': context.pop('zone_designated')
                        elif mutation == 'light': context['beacon_yellow_light_count'] = 1
                        elif mutation == 'alternate': context['beacon_alternating_yellow'] = False
                        elif mutation == 'camera': context['camera_sha256']['overview.mkv'] = '0'*64
                        data = json.dumps(context, separators=(',', ':'))+'\n'
                    (target/item.name).write_text(data)
                else:
                    (target/item.name).symlink_to(item)
            try:
                measure(target)
            except ValueError as exc:
                if str(exc) != error:
                    raise
                negatives[label] = error
            else:
                raise AssertionError('Damaged saved source accepted: '+label)
    return {'format': 'c255451-saved-meter-cpu-proof',
            'case_id': positive['case_id'], 'synthetic_positive': True,
            'source_hashes': positive['sources'], 'negative_rejections': negatives,
            'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source')
    args = parser.parse_args()
    print(json.dumps(test(args.source), sort_keys=True))

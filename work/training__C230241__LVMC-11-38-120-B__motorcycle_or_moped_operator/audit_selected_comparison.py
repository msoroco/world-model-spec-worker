"""Independently compare source-bound synthetic lamp-state cases."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'selected-source'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def compare(reference, contrast):
    a, b = reference, contrast
    if len(a) != len(b) or len(a) != 600:
        raise ValueError('Comparison source frame count differs')
    for index, (left, right) in enumerate(zip(a, b)):
        if left['native_frame'] != right['native_frame'] or left['time_s'] != right['time_s']:
            raise ValueError('Comparison frame identity differs at ' + str(index))
        for key in ('utc_s', 'tail_lamp_lit', 'headlamp_white', 'tail_lamp_red',
                    'rear_visible_ft', 'discernible_500ft'):
            if left[key] != right[key]:
                raise ValueError('Comparison fixed condition differs: ' + key)
    if not (sum(1 for row in a if row['headlamp_lit']) == 598 and
            all(row['front_visible_ft'] == 300 for row in a) and
            all(not row['headlamp_lit'] and row['front_visible_ft'] == 0 for row in b)):
        raise ValueError('Requested lamp-state contrast not observed in diagnostic rows')
    return {'reference_front_visible_ft': 300, 'contrast_front_visible_ft': 0,
            'reference_headlamp_lit_frames': 598, 'contrast_headlamp_lit_frames': 0}


def main():
    ref = SOURCE / 'reference/lighting-review.jsonl'
    contrast = SOURCE / 'contrast/lighting-review.jsonl'
    left, right = rows(ref), rows(contrast)
    outcomes = compare(left, right)
    altered = json.loads(json.dumps(right))
    altered[0]['rear_visible_ft'] = 499
    try:
        compare(left, altered)
    except ValueError as error:
        if 'fixed condition differs' not in str(error):
            raise
    else:
        raise ValueError('Changed fixed rear visibility was accepted')
    try:
        compare(left, right[:-1])
    except ValueError as error:
        if 'frame count' not in str(error):
            raise
    else:
        raise ValueError('Missing frame was accepted')
    path = HERE / 'selected-comparison.json'
    path.write_text(json.dumps({
        'format': 'c230241-selected-synthetic-comparison-v1',
        'case_ids': [HERE.name + '__reference', HERE.name + '__contrast'],
        'comparison_id': HERE.name + '__comparison_main',
        'source_sha256': {'reference': sha(ref), 'contrast': sha(contrast)},
        'frames': 600, 'diagnostic_only': True,
        'physical_visibility_verified': False, 'legal_verdict_claimed': False,
        'positive': outcomes,
        'negative_changed_fixed_condition_rejected': True,
        'negative_missing_frame_rejected': True,
    }, indent=2) + '\n')
    print(json.dumps({'passed': True, 'receipt_sha256': sha(path)}))


if __name__ == '__main__':
    main()

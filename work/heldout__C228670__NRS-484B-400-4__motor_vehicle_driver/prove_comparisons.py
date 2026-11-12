"""Independent source-bound exact contrast and negative audit proof."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import tempfile
from turn_comparison_audit import audit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SLUGS = ('approach_near_depart_right', 'approach_far_depart_right', 'approach_near_depart_left')


def measured(slug):
    stem = 'c228670-candidate-' + slug + '-primary-compatibility-v'
    attempts = sorted((ROOT / '.runtime-work').glob(stem + '*'), key=lambda p: int(p.name.rsplit('-v', 1)[1]))
    if not attempts:
        raise ValueError('No retained exact compatibility source: ' + slug)
    report = attempts[-1] / 'analysis-report.json'
    return json.loads(report.read_text())['measurements']['turn_geometry']['value'], sha256(report.read_bytes()).hexdigest()


def main():
    values = {slug: measured(slug) for slug in SLUGS}
    with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work', prefix='c228670-compare-') as temp:
        paths = {}
        for slug, (value, _) in values.items():
            path = Path(temp) / (slug + '.json')
            path.write_text(json.dumps(value) + '\n')
            paths[slug] = path
        near, far, left = (paths[slug] for slug in SLUGS)
        approach = audit([near, far], 'approach_curb_position')
        departure = audit([near, left], 'departure_centerline_side')
        for key, expected in (('departure_centerline_min_signed_m', 'held departure'),
                              ('geometry_sha256', 'fixed geometry')):
            changed = deepcopy(values[SLUGS[1]][0])
            changed[key] = 'changed' if key == 'geometry_sha256' else changed[key] + .1
            far.write_text(json.dumps(changed) + '\n')
            try:
                audit([near, far], 'approach_curb_position')
            except ValueError as error:
                if expected not in str(error):
                    raise
            else:
                raise ValueError('Changed fixed condition escaped audit: ' + key)
    result = {'format': 'worker-turn-comparison-proof',
              'case_analysis_sha256': {slug: row[1] for slug, row in values.items()},
              'approach': approach, 'departure': departure,
              'negative_held_position_rejected': True, 'negative_geometry_source_rejected': True,
              'legal_acceptance_claimed': False, 'physical_acceptance_claimed': False}
    (HERE / 'contrast-comparison-proof.json').write_text(json.dumps(result, indent=2) + '\n')
    print('Two exact contrasts and two changed-fixed-condition negatives passed')


if __name__ == '__main__':
    main()

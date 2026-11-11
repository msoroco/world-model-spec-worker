"""Audit two source-bound contrast pairs and changed-held-condition rejection."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile

from turn_comparison_audit import audit

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def observed(slug):
    report = REPO / ('.runtime-work/c109705-' + slug + '-compatibility-v2/analysis-report.json')
    return json.loads(report.read_text())['measurements']['turn_geometry']['value']


def main():
    near = observed('approach_near_depart_right')
    far = observed('approach_far_depart_right')
    left = observed('approach_near_depart_left')
    with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work', prefix='c109705-comparison-') as temporary:
        root = Path(temporary)
        paths = []
        for name, item in (('near', near), ('far', far), ('left', left)):
            path = root / (name + '.json')
            path.write_text(json.dumps(item) + '\n')
            paths.append(path)
        approach = audit(paths[:2], 'approach_curb_position')
        departure = audit([paths[0], paths[2]], 'departure_centerline_side')
        changed = deepcopy(far)
        changed['departure_all_corners_right_of_centerline'] = False
        paths[1].write_text(json.dumps(changed) + '\n')
        try:
            audit(paths[:2], 'approach_curb_position')
        except ValueError as error:
            if 'held departure' not in str(error):
                raise
        else:
            raise ValueError('Changed held departure escaped comparison audit')
    (ROOT / 'contrast-comparison-proof.json').write_text(json.dumps({
        'approach': approach, 'departure': departure,
        'negative_changed_held_departure_rejected': True,
        'source_case_measurement_logs': [
            'proof-approach_near_depart_right-compatibility.log',
            'proof-approach_far_depart_right-compatibility.log',
            'proof-approach_near_depart_left-compatibility.log'],
        'legal_acceptance_claimed': False, 'physical_acceptance_claimed': False}, indent=2) + '\n')
    print('Two exact source-bound contrasts and changed-held-condition rejection passed')


if __name__ == '__main__':
    main()

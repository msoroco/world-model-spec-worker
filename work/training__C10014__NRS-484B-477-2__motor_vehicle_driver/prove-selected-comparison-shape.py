"""Exercise the exact selected alley comparison with nonoriginal CPU source shapes."""
import json
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path[:0] = [str(HERE), str(HERE / 'tests'), str(REPO / 'runtime/pipeline')]

from delivery_audit import audit_complete, sha  # noqa: E402
from comparison_audit import audit_pair  # noqa: E402
from test_delivery_positive_shape import PositiveDeliveryShapeTest  # noqa: E402


def require(value, message):
    if not value:
        raise ValueError(message)


def main():
    target = HERE / 'update038-selected-comparison-shape.json'
    require(not target.exists(), 'Retain prior selected comparison proof')
    maker = PositiveDeliveryShapeTest()
    audit_paths = {}
    with tempfile.TemporaryDirectory(prefix='c10014-comparison-', dir=REPO / '.runtime-work') as temporary:
        root = Path(temporary)
        for suffix, overlap, stop in (('reference', 0.0, -12.0),
                                      ('contrast', 5.2, 0.0)):
            case_id = HERE.name + '__' + suffix
            local = root / suffix
            local.mkdir()
            attempt, owner, saved, construction, pixel, access, primary, core = (
                maker.make_shape(local, case_id=case_id, overlap=overlap, stop_x=stop))
            report = audit_complete(attempt, saved, owner, case_id, construction,
                                    pixel, access, primary, core, local / 'decode',
                                    'unit-job', 1, 'unit-recording', test_shape=True)
            require(report['source_shaped_unit_test'] is True and
                    report['passed'] is False, 'Synthetic delivery was accepted')
            path = local / 'delivery-audit.json'
            path.write_text(json.dumps(report, indent=2) + '\n')
            audit_paths[suffix] = path
        compared = audit_pair(audit_paths['reference'], audit_paths['contrast'],
                              test_shape=True)
        require(compared['source_shaped_unit_test'] is True and
                compared['passed'] is False and
                compared['measured_overlap_m'] == [0.0, 5.2],
                'Selected comparison shape was not checked')
        contrast_path = audit_paths['contrast']
        intact = contrast_path.read_text()
        altered = json.loads(intact)
        altered['property_access_id'] = 'different-property-access'
        contrast_path.write_text(json.dumps(altered, indent=2) + '\n')
        try:
            audit_pair(audit_paths['reference'], contrast_path, test_shape=True)
        except ValueError as error:
            require('independent access review changed' in str(error),
                    'Wrong changed-property rejection')
        else:
            raise AssertionError('Different property access passed comparison')
        contrast_path.write_text(intact)
        try:
            audit_pair(audit_paths['reference'], audit_paths['contrast'])
        except ValueError as error:
            require('independent original delivery' in str(error),
                    'Wrong original-source rejection')
        else:
            raise AssertionError('Synthetic pair passed original comparison')
        comparison = {
            'format': 'c10014-selected-comparison-cpu-proof-v1',
            'comparison_id': compared['comparison_id'],
            'case_ids': compared['case_ids'],
            'diagnostic_source_shape_passed': True,
            'original_comparison_accepted': False,
            'altered_property_access_audit_rejected': True,
            'measured_overlap_m': compared['measured_overlap_m'],
            'comparison_auditor_sha256': sha(HERE / 'comparison_audit.py'),
            'delivery_auditor_sha256': sha(HERE / 'delivery_audit.py'),
            'source_shaped_unit_test': True,
        }
    target.write_text(json.dumps(comparison, indent=2) + '\n')
    print(json.dumps({'comparison_id': comparison['comparison_id'],
                      'diagnostic_source_shape_passed': True,
                      'original_comparison_accepted': False,
                      'proof_sha256': sha(target)}, sort_keys=True))


if __name__ == '__main__':
    main()

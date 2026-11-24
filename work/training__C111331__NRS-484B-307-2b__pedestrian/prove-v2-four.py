"""Exercise the independent four-case audit and two rejection paths."""
import copy
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('four_audit', HERE / 'audit-v2-four.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def main():
    result = module.audit()
    case = json.loads((HERE / 'v2-four-case-manifest.json').read_text())['cases'][0]
    wrong = copy.deepcopy(case)
    wrong['construction_sha256'] = '0' * 64
    try:
        module.audit_case(wrong)
    except ValueError as exc:
        assert 'Construction identity' in str(exc)
    else:
        raise AssertionError('Stale construction accepted')
    original = module.audit_case

    def wrong_comparison(case, root=HERE):
        config, measurement = original(case, root)
        if case['case_id'].endswith('witness_2'):
            measurement = dict(measurement, pedestrian_signal_at_entry='walk')
        return config, measurement

    with patch.object(module, 'audit_case', side_effect=wrong_comparison):
        try:
            module.audit()
        except ValueError as exc:
            assert 'contrast absent' in str(exc)
        else:
            raise AssertionError('Broken comparison accepted')
    return dict(result, negative_rejections=['stale_construction', 'missing_comparison_contrast'])


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))

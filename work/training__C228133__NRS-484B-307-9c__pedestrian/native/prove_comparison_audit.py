"""CPU proof of the independent C228133 saved comparison audit."""

import json
from pathlib import Path
import tempfile

from comparison_audit import audit, digest
from finalize_saved import finalize
from prove_saved_source_analysis import sample


HERE = Path(__file__).resolve().parent
OUT = HERE.parent / 'comparison-audit-proof.json'


def reject(reference, contrast, label, mutate, expected):
    mutate()
    try:
        audit(reference, contrast)
    except ValueError as error:
        if expected not in str(error):
            raise AssertionError(label + ': unexpected rejection ' + str(error))
    else:
        raise AssertionError(label + ': malformed comparison accepted')


def prove():
    root = HERE.parents[2] / '.runtime-work'
    root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root, prefix='c228133-comparison-') as temp:
        ref, alt = Path(temp) / 'reference', Path(temp) / 'contrast'
        sample(ref, False)
        sample(alt, True)
        finalize(ref, ref / 'analysis-report.json')
        finalize(alt, alt / 'analysis-report.json')
        result = audit(ref, alt)
        assert result['changed_footprint_frames'] == 520
        assert result['reference_entry_frames'] == []
        assert result['contrast_entry_frames'] == [80]
        def change_json(path, update):
            data = json.loads(path.read_text())
            update(data)
            path.write_text(json.dumps(data) + '\n')
        checks = []
        target = alt / 'result.json'
        original = target.read_bytes()
        reject(ref, alt, 'invented observed contrast',
               lambda: change_json(target, lambda x: x['measured_values'].__setitem__(
                   'pedestrian_enters_highway', False)),
               'entry result differs')
        checks.append('invented observed contrast')
        target.write_bytes(original)
        target = alt / 'native-signal-frames.jsonl'
        original = target.read_bytes()
        reject(ref, alt, 'changed signal source',
               lambda: target.write_bytes(original + b'{}\n'),
               'source hash differs')
        checks.append('changed signal source')
        target.write_bytes(original)
        target = alt / 'config.json'
        original = target.read_bytes()
        reject(ref, alt, 'changed capture duration',
               lambda: change_json(target, lambda x: x.__setitem__('duration_s', 29)),
               'capture contract differs')
        checks.append('changed capture duration')
        target.write_bytes(original)
        target = alt / 'reviewed-source/measurement.json'
        original = target.read_bytes()
        reject(ref, alt, 'changed measurement',
               lambda: change_json(target, lambda x: x['measurement'].__setitem__(
                   'potential_9c_entry_frames', [])),
               'result/measurement differs')
        checks.append('changed measurement')
        target.write_bytes(original)
        assert audit(ref, alt)['passed'] is True
    return {'format': 'c228133-comparison-audit-proof-v1', 'passed': True,
            'comparison_audit_sha256': digest(HERE / 'comparison_audit.py'),
            'source_fixture_sha256': digest(HERE / 'prove_saved_source_analysis.py'),
            'positive': result, 'negative_checks': checks,
            'synthetic_diagnostic': True, 'original_native_observed': False,
            'physical_acceptance_claimed': False, 'legal_verdict': None}


if __name__ == '__main__':
    proof = prove()
    OUT.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps(proof, sort_keys=True))

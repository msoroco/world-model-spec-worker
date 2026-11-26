"""Bind three independent comparison positive and missing-check negatives."""
import hashlib
import json
from pathlib import Path

from audit_comparisons import PAIRS

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    folder = PACKAGE / 'comparison-audit'
    rows = []
    script = 'work/' + PACKAGE.name + '/native/audit_comparisons.py'
    for suffix, (base, contrast, variable) in PAIRS.items():
        positive = folder / (suffix + '-positive.log')
        negative = folder / (suffix + '-negative.log')
        result = json.loads(positive.read_text())
        if (result['changed_variable'] != variable or
                not result['synthetic_diagnostic_only'] or
                'Independent predeparture check source required' not in negative.read_text()):
            raise ValueError('Independent comparison audit incomplete: ' + suffix)
        command = '.venv-cpu/bin/python ' + script + ' --comparison ' + result['comparison_id']
        rows.append({'comparison_id': result['comparison_id'],
                     'case_ids': result['selected_case_ids'],
                     'changed_variable': variable,
                     'command': command, 'exit_code': 0,
                     'log': str(positive.relative_to(PACKAGE)),
                     'log_sha256': sha(positive),
                     'negative_command': command + ' --negative',
                     'negative_exit_code': 1,
                     'negative_expected_error': 'Independent predeparture check source required',
                     'negative_log': str(negative.relative_to(PACKAGE)),
                     'negative_log_sha256': sha(negative),
                     'sources': {'base': result['base_sources'],
                                 'contrast': result['contrast_sources']}})
    output = folder / 'proof.json'
    output.write_text(json.dumps({'format': 'c245490-comparison-audit-v1',
                                  'assignment_id': PACKAGE.name,
                                  'script': script,
                                  'script_sha256': sha(HERE / 'audit_comparisons.py'),
                                  'comparisons': rows,
                                  'original_native_motion_verified': False},
                                 indent=2) + '\n')
    print(json.dumps({'comparison_count': len(rows), 'sha256': sha(output)}))


if __name__ == '__main__':
    main()

"""Run independent retained-source audit on every selected CPU diagnostic."""
import json
import shlex
from pathlib import Path

from delivery_audit import audit

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent


def main():
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    claims = json.loads((ROOT / 'result.json').read_text())['tests']
    for entry in manifest['cases']:
        case_id = entry['case_id']
        attempts = []
        for claim in claims:
            tokens = shlex.split(claim['command'])
            if ('compatibility' in tokens and '--candidate' not in tokens
                    and '--case' in tokens and tokens[tokens.index('--case') + 1] == case_id):
                attempts.append(REPO / tokens[tokens.index('--output') + 1])
        if len(attempts) != 1:
            raise ValueError('One current primary compatibility attempt required: ' + case_id)
        proof = audit(case_id, attempts[0], ROOT, diagnostic=True)
        if not proof['software_audit_passed'] or not proof['diagnostic_only']:
            raise ValueError('Incorrect diagnostic audit outcome: ' + case_id)
        print(case_id + ': four-camera source audit passed; physical acceptance false')
    print('selected_cases=' + str(len(manifest['cases'])))


if __name__ == '__main__':
    main()

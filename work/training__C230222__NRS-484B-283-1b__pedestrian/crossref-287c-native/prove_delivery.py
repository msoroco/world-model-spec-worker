"""Bind four 287(c) diagnostic delivery and original-source rejection controls."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parent
ROOT = HERE.parents[2]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    rows = []
    for label in ('marked', 'unmarked'):
        for candidate in ('primary', 'fallback1'):
            tag = 'topology' if candidate == 'primary' else 'fallback'
            folder = HERE / label / ('proofs' if candidate == 'primary' else 'fallback1/proofs')
            attempt = ROOT / '.runtime-work' / f'c230222-287c-{tag}-{label}-compat'
            saved = ROOT / '.runtime-work' / f'c230222-287c-{tag}-{label}-saved/v0001/processing.json'
            diagnostic = ROOT / '.runtime-work' / f'c230222-287c-{tag}-{label}-delivery-diagnostic.json'
            positive = folder / 'delivery-positive.log'
            negative = folder / 'delivery-negative.log'
            receipt = json.loads(diagnostic.read_text())
            case_id = ASSIGNMENT.name + '__crossref_287c_' + label
            if (receipt['case_id'] != case_id or receipt['candidate_id'] != candidate or
                    receipt['diagnostic_only'] is not True or receipt['physical_review'] is not None or
                    receipt['physical_or_legal_acceptance_claimed'] is not False or
                    receipt['processing_sha256'] != sha(saved) or
                    receipt['analysis_sha256'] != sha(attempt / 'analysis-report.json') or
                    '"passed": true' not in positive.read_text().lower() or
                    'Original Native source required' not in negative.read_text()):
                raise ValueError('287(c) diagnostic delivery or rejection differs')
            rows.append({'case_id': case_id, 'candidate_id': candidate,
                         'positive_log_sha256': sha(positive),
                         'negative_log_sha256': sha(negative),
                         'diagnostic_result_sha256': sha(diagnostic),
                         'original_native_observed': False})
    proof = {'format': 'c230222-287c-delivery-cpu-proof-v1',
             'auditor_sha256': sha(HERE / 'delivery_audit.py'),
             'cases': rows, 'selected_for_delivery': False}
    target = HERE / 'delivery-proof.json'
    target.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'controls': len(rows), 'proof_sha256': sha(target)}))


if __name__ == '__main__':
    main()

"""Source-bound exact-80 disposition; a request is never an observed speed."""
import hashlib
import json
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    review_path = HERE / 'accepted-membership-review.json'
    review = json.loads(review_path.read_text())
    at = next(item for item in review['accepted_memberships']
              if item['case_id'].endswith('-80-at'))
    requested = Decimal(at['review_description'].split(': ', 1)[1].split(' ', 1)[0])
    exact_mps = Decimal('80') * Decimal('0.44704')
    assert requested == Decimal('35.5397')
    assert exact_mps == Decimal('35.76320')
    assert not at['review_receipt_sources'] and at['reuse'] is False
    checks = {
        'below': Decimal('79.9999') > Decimal('80'),
        'at': Decimal('80') > Decimal('80'),
        'above': Decimal('80.0001') > Decimal('80'),
    }
    assert checks == {'below': False, 'at': False, 'above': True}
    output = {
        'format': 'worker-speed-boundary-disposition',
        'assignment_id': HERE.name,
        'law_id': 'NRS-484B-600-1e',
        'legal_operator': '>',
        'legal_limit_mph': '80',
        'exact_limit_mps': str(exact_mps),
        'accepted_at_recording_id': at['recording_id'],
        'accepted_at_request_mps': str(requested),
        'accepted_at_request_mph': str(requested / Decimal('0.44704')),
        'accepted_at_original_velocity_source': None,
        'source_hashed_equivalence': False,
        'reuse': False,
        'measured_at_boundary': 'unresolved',
        'synthetic_operator_unit_checks': checks,
        'rounding_rule': 'Compare original unrounded m/s magnitude to Decimal(80)*Decimal(0.44704); report mph separately.',
        'selected_cases_cover': ['below_request', 'above_request'],
        'missing_canonical_branch': 'at-80 source-bound original Native measurement',
        'review_sha256': digest(review_path),
        'physical_or_legal_acceptance_claimed': False,
    }
    path = HERE / 'boundary-disposition.json'
    path.write_text(json.dumps(output, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'boundary_disposition_sha256': digest(path),
                      'at_reuse': False, 'original_speed_unresolved': True}))


if __name__ == '__main__':
    main()

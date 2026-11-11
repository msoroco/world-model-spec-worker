"""Bind candidate-bound synthetic comparison proofs without physical claims."""
import hashlib
import json
from pathlib import Path

folder = Path(__file__).resolve().parent
repo = folder.parent.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


source_path = folder / 'fallback-candidate-source-receipt.json'
source_receipt = json.loads(source_path.read_text())
sources = source_receipt['sources']
if (len(sources) != 24 or len({(r['case_id'], r['candidate_id']) for r in sources}) != 24 or
        source_receipt['physical_fallback_motion_proven'] is not False or
        source_receipt['generator_sha256'] != sha(folder / 'fallback_candidate_sources.py') or
        any(sha(repo / row['path']) != row['sha256'] or row['frames'] != 900 for row in sources)):
    raise ValueError('Candidate-bound 900-frame source projections are incomplete')
positive_path = folder / 'full-duration-fallback-comparison.log'
positive = [json.loads(line) for line in positive_path.read_text().splitlines()]
if (len(positive) != 21 or
        any(row['frames'] != 900 or row['candidate_source_kind'] != 'candidate_bound_synthetic_projection'
            or row['physical_fallback_motion_proven'] is not False for row in positive)):
    raise ValueError('Twenty-one candidate-bound comparisons did not pass')
negative_path = folder / 'fallback-candidate-negative.log'
negative = json.loads(negative_path.read_text())
if negative != {'negative': 'changed_candidate_source', 'rejected': True,
                'source_restored': True, 'physical_acceptance_claimed': False}:
    raise ValueError('Changed candidate source was not rejected and restored')
receipt = {'format': 'worker-fallback-candidate-comparison-diagnostic',
           'source_receipt': source_path.name, 'source_receipt_sha256': sha(source_path),
           'generator_sha256': sha(folder / 'fallback_candidate_sources.py'),
           'comparison_script_sha256': sha(folder / 'full_duration_fallback_comparison_proof.py'),
           'negative_script_sha256': sha(folder / 'fallback_candidate_negative_proof.py'),
           'positive_log': positive_path.name, 'positive_log_sha256': sha(positive_path),
           'negative_log': negative_path.name, 'negative_log_sha256': sha(negative_path),
           'candidate_sources': 24, 'paired_comparisons': 21, 'frames_per_source': 900,
           'software_checks_passed': True, 'physical_fallback_motion_proven': False,
           'delivery_passed': False, 'legal_verdict_asserted': False}
(folder / 'fallback-candidate-comparison-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({'candidate_sources': 24, 'paired_comparisons': 21,
                  'software_checks_passed': True, 'physical_fallback_motion_proven': False}))

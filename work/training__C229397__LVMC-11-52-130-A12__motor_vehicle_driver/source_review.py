"""Join separately reviewed original sources without rewriting Native capture."""
import hashlib
import json
from pathlib import Path

FIELDS = (
    'jurisdiction_source_id', 'marked_crosswalk_source_id',
    'crosswalk_extent_source_id', 'responsible_person_source_id',
    'traffic_conflict_review_source_id', 'law_compliance_review_source_id',
    'directions_review_source_id',
)


def join(attempt, inventory):
    attempt = Path(attempt).resolve()
    review_path = attempt / 'crosswalk-source-review.json'
    if not review_path.is_file():
        raise ValueError('independent crosswalk source review missing')
    review = json.loads(review_path.read_text())
    if review.get('format') != 'c229397-crosswalk-source-review-v1':
        raise ValueError('crosswalk source review format differs')
    if review.get('assignment_id') != inventory.get('assignment_id'):
        raise ValueError('crosswalk source review assignment differs')
    findings = review.get('findings')
    if not isinstance(findings, dict) or set(findings) != set(FIELDS):
        raise ValueError('crosswalk source review findings incomplete')
    joined = dict(inventory)
    for field in FIELDS:
        finding = findings[field]
        if not isinstance(finding, dict) or finding.get('finding') not in ('present', 'absent', 'unresolved'):
            raise ValueError('crosswalk source review finding invalid: ' + field)
        rel = finding.get('source')
        if not isinstance(rel, str) or not rel or Path(rel).is_absolute() or '..' in Path(rel).parts:
            raise ValueError('crosswalk source review path invalid: ' + field)
        source = (attempt / rel).resolve()
        if not source.is_relative_to(attempt) or not source.is_file():
            raise ValueError('crosswalk source review file missing: ' + field)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if digest != finding.get('sha256'):
            raise ValueError('crosswalk source review hash differs: ' + field)
        if field == 'marked_crosswalk_source_id' and finding['finding'] != 'present':
            raise ValueError('marked crosswalk has not been established')
        joined[field] = rel + '#sha256=' + digest + '#finding=' + finding['finding']
    return joined, hashlib.sha256(review_path.read_bytes()).hexdigest(), {
        field: findings[field]['finding'] for field in FIELDS}

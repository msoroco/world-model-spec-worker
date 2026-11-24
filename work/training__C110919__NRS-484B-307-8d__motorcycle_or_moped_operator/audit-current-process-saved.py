"""Independently verify retained current process-saved diagnostic receipts."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
MANIFEST=HERE/'saved-diagnostic-manifest.json'
POSITIVE=HERE/'native/current-process-saved-proof.json'
NEGATIVE=HERE/'native/current-process-saved-negative-proof.json'
POSITIVE_B=HERE/'native/current-process-saved-proof-b.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_sources(proof):
    receipt=proof['processing_receipt']
    version=Path(receipt['version'])
    stage=Path(receipt['analysis_directory'])
    if not version.is_dir() or stage!=version/'analysis':
        raise ValueError('Saved analysis directory missing')
    for rel,checksum in receipt['original_source_hashes'].items():
        # Saved output stages source acquisition; changed source bytes invalidate
        # the receipt without relying on a prior command's success label.
        source=stage/rel
        if not source.is_file() or sha(source)!=checksum:
            raise ValueError('Saved source hash changed: '+rel)
    if not receipt['originals_preserved'] or receipt['timestamp_joins']['frames']!=600:
        raise ValueError('Original preservation or frame join incomplete')
    if receipt['final_video_checks']['frames']!=600 or not receipt['final_video_checks']['passed']:
        raise ValueError('Final video decode incomplete')
    return {'sources':len(receipt['original_source_hashes']),
            'version':str(version),
            'final_video_sha256':receipt['final_video_checks']['video_sha256']}


def main():
    positive=json.loads(POSITIVE.read_text())
    negative=json.loads(NEGATIVE.read_text())
    manifest=json.loads(MANIFEST.read_text())
    case=manifest['cases'][0]['case_id']
    if (not positive['passed'] or not negative['passed'] or
            positive['manifest_sha256']!=sha(MANIFEST) or
            negative['manifest_sha256']!=sha(MANIFEST) or
            negative['positive_proof_sha256']!=sha(POSITIVE) or
            positive['case_id']!=case or
            positive['source']['construction_sha256']!=manifest['cases'][0]['construction_sha256'] or
            positive['selected_delivery'] or positive['original_native_observed'] or
            negative['selected_delivery'] or negative['original_native_observed']):
        raise ValueError('Current saved diagnostic identity or status changed')
    good=verify_sources(positive)
    bad=verify_sources(negative)
    second=json.loads(POSITIVE_B.read_text())
    if (not second['passed'] or second['case_id']!=manifest['cases'][1]['case_id'] or
            second['manifest_sha256']!=sha(MANIFEST) or
            second['source']['construction_sha256']!=manifest['cases'][1]['construction_sha256'] or
            second['selected_delivery'] or second['original_native_observed'] or
            second['processing_receipt']['missing_evidence'] or
            second['processing_receipt']['case_id']!=second['case_id']):
        raise ValueError('Condition B saved diagnostic identity changed')
    second_good=verify_sources(second)
    if (positive['processing_receipt']['missing_evidence'] or
            negative['processing_receipt']['missing_evidence'] is not True or
            negative['classification']!='incomplete_or_unavailable_law_evidence' or
            'road_geometry.json' not in positive['processing_receipt']['original_source_hashes'] or
            'road_geometry.json' in negative['processing_receipt']['original_source_hashes']):
        raise ValueError('Missing-source contrast failed')
    if not (ROOT/'.runtime-work') in Path(good['version']).parents or not (ROOT/'.runtime-work') in Path(bad['version']).parents:
        raise ValueError('Generated diagnostic escaped .runtime-work')
    result={'format':'c110919-independent-current-saved-audit-v1',
            'passed':True,'manifest_sha256':sha(MANIFEST),
            'positive_proof_sha256':sha(POSITIVE),
            'negative_proof_sha256':sha(NEGATIVE),
            'positive':good,'negative':bad,
            'condition_b_positive_proof_sha256':sha(POSITIVE_B),
            'condition_b_positive':second_good,
            'missing_source':'road_geometry.json',
            'original_native_observed':False,'selected_delivery':False,
            'physical_acceptance_claimed':False,'legal_verdict_claimed':False}
    target=HERE/'native/current-process-saved-audit.json'
    target.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'passed':True,'audit_sha256':sha(target),
                      'source_counts':[good['sources'],bad['sources'],second_good['sources']]}))


if __name__=='__main__':
    main()

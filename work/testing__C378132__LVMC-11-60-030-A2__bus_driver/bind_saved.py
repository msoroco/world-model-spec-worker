"""Bind saved-only CPU rerun receipts for all ten diagnostic A2 bus attempts."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
SCRATCH=REPO/'.runtime-work/c378132-a2'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path=ROOT/'execution-manifest.json'
    manifest=json.loads(path.read_text())
    for entry in manifest['cases']:
        suffix=entry['case_id'].split('__')[-1]
        folder=ROOT/'cases'/suffix
        source=SCRATCH/('saved-'+suffix+'-v2')/'v0001'/'processing.json'
        proof=json.loads(source.read_text())
        if (proof.get('case_id')!=entry['case_id'] or proof.get('recorded_only') is not True
                or proof.get('originals_preserved') is not True or proof.get('passed') is not True
                or proof.get('missing_evidence') is not False
                or proof['analysis_revision']['construction_sha256']!=entry['construction_sha256']):
            raise ValueError('incomplete saved-only source proof: '+suffix)
        log_source=SCRATCH/('saved-'+suffix+'-v2-cli.log')
        log=folder/'saved-processing.log'
        log.write_text(log_source.read_text().rstrip()+'\n')
        receipt=folder/'saved-processing-receipt.json'
        summary={'format':'worker-saved-processing-diagnostic-summary','case_id':entry['case_id'],
                 'recorded_only':True,'passed':True,'originals_preserved':True,
                 'timestamp_joins':proof['timestamp_joins'],
                 'construction_sha256':entry['construction_sha256'],
                 'analysis_log_sha256':proof['analysis_log_sha256'],
                 'result_sha256':proof['result_sha256'],
                 'processing_receipt_sha256':sha(source),
                 'scope':'synthetic source-shaped fixture; no original physical or legal acceptance'}
        receipt.write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
        entry['post_capture'].update({'test_exit_code':0,'test_log':str(log.relative_to(ROOT)),
                                      'test_log_sha256':sha(log),
                                      'diagnostic_receipt':str(receipt.relative_to(ROOT)),
                                      'diagnostic_receipt_sha256':sha(receipt)})
    path.write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    print(f"bound {len(manifest['cases'])} A2 saved-only original-preservation and decode receipts")


if __name__=='__main__':main()

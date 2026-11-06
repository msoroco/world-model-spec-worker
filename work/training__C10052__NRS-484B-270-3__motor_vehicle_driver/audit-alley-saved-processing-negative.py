"""Audit the retained missing-channel saved-processing negative."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    summary=json.loads((HERE/'alley-saved-processing-negative-summary.json').read_text())
    root=REPO/summary['source_root'];attempt=root/'attempt'
    version=Path(summary['processing_version'])
    assert not (attempt/'source_channels').exists()
    assert (attempt/'channels').is_dir()
    seal=json.loads((attempt/'capture-seal.json').read_text())
    assert seal['diagnostic_fixture'] is True
    assert all(sha(attempt/name)==digest for name,digest in seal['sources'].items())
    receipt=json.loads((version/'processing.json').read_text())
    assert receipt['missing_evidence'] is True
    assert receipt['originals_preserved'] is True
    assert receipt['physical_acceptance_claimed'] is False
    assert receipt['legal_acceptance_claimed'] is False
    log=(version/'analysis.log').read_text()
    assert summary['expected_error'] in log
    result=json.loads((version/'analysis/result.json').read_text())
    assert result.get('accepted') is not True
    assert summary['selected'] is False and summary['accepted'] is False
    return {'passed':True,'missing_source':'source_channels',
            'missing_evidence':True,'selected':False,'accepted':False}


if __name__=='__main__':
    print(json.dumps(audit(),indent=2))

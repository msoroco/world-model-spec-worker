"""Independent exact C102372 v1 package and negative audit."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    manifest=json.loads((HERE/'draft-execution-manifest.json').read_text())
    summary=json.loads((HERE/'draft-package-summary.json').read_text())
    records={(item['case'],item['candidate']):item for item in summary['results']}
    if len(records)!=28:raise ValueError('Twenty-eight exact C102372 portable receipts required')
    checked=[]
    for entry in manifest['cases']:
        case=entry['case_id'];suffix=case.rsplit('__',1)[-1]
        fixture_hash=None
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            ref=entry if candidate=='primary' else next(
                item for item in entry['candidates'] if item['id']==candidate)
            folder=HERE/'draft-candidates'/suffix/candidate
            if sha(folder/'construction.json')!=ref['construction_sha256']:
                raise ValueError('Exact C102372 construction changed')
            package=json.loads((folder/'package-receipt.json').read_text())
            if package!=records[(case,candidate)] or package['passed'] is not True or \
                    package['accepted_recording_claimed'] is not False:
                raise ValueError('Portable summary, receipt or scope differs')
            receipt=package['receipt']
            if (receipt['format'],receipt['case_id'],receipt['candidate_id'],
                receipt['construction_sha256'],receipt['runtime_manifest_sha256'])!=(
                'worker-package-compatibility-v1',case,candidate,
                ref['construction_sha256'],manifest['runtime_manifest_sha256']):
                raise ValueError('Exact C102372 portable identity differs')
            checks={'actual_analysis','native_validation','mandatory_observations',
                'lean_decoder','render','final_decode','acquisition_unchanged'}
            if receipt['passed'] is not True or not checks<=set(receipt['checks']):
                raise ValueError('Pinned portable check set incomplete')
            if fixture_hash is None:fixture_hash=receipt['fixture_sha256']
            elif fixture_hash!=receipt['fixture_sha256']:
                raise ValueError('Controlled candidate fixture changed')
            if sha(folder/'package-analysis.log')!=receipt['log_sha256']:
                raise ValueError('Saved analysis log differs')
            if package['negative_exit_code']==0 or \
                    'Missing required source: native_samples.jsonl' not in \
                    (folder/'package-negative.log').read_text():
                raise ValueError('Removed Native truck source negative missing')
            checked.append({'case':suffix,'candidate':candidate,
                            'construction_sha256':ref['construction_sha256']})
    return {'passed':True,'exact_unselected_portable_candidates':checked,
            'physical_or_selected_claim':False}


if __name__=='__main__':print(json.dumps(audit(),sort_keys=True))

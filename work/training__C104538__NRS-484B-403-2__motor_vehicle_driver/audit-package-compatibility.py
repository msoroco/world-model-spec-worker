"""Independent exact v1 positive/negative receipt and source audit."""
import hashlib
import json
from pathlib import Path
import sys

FOLDER=Path(__file__).resolve().parent
ROOT=FOLDER.parents[1]
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
from worker_exchange.common import digest,tree


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    manifest=json.loads((FOLDER/'draft-execution-manifest.json').read_text())
    expected={(entry['case_id'],candidate):(
        entry if candidate=='primary' else next(c for c in entry['candidates'] if c['id']==candidate))
        for entry in manifest['cases'] for candidate in ('primary','fallback1','fallback2','fallback3')}
    seen=set();rows=[]
    for suffix in ('witness_1','witness_2'):
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            packet=json.loads((FOLDER/f'package-{suffix}-{candidate}.json').read_text())
            case=FOLDER.name+'__'+suffix;key=case,candidate
            if key in seen or key not in expected or packet['case']!=suffix or packet['candidate']!=candidate:
                raise AssertionError('Exact package identity missing or duplicated')
            seen.add(key)
            scratch=Path(packet['scratch'])
            if ROOT/'.runtime-work' not in scratch.parents:
                raise AssertionError('Package proof escaped ignored scratch')
            receipt=json.loads((scratch/'positive/compatibility.json').read_text())
            positive=packet['positive']
            if (positive!={k:v for k,v in receipt.items() if k!='fixture_manifest'} or
                receipt['format']!='worker-package-compatibility-v1' or receipt['passed'] is not True):
                raise AssertionError('Positive receipt differs or failed')
            source=expected[key]
            if (receipt['case_id']!=case or receipt['candidate_id']!=candidate or
                receipt['construction_sha256']!=source['construction_sha256'] or
                sha(FOLDER/source['construction'])!=source['construction_sha256']):
                raise AssertionError('Positive proof used another exact construction')
            required={'actual_analysis','native_validation','mandatory_observations',
                      'lean_decoder','render','final_decode','acquisition_unchanged'}
            if not required<=set(receipt['checks']):
                raise AssertionError('Pinned compatibility stages missing')
            if digest(tree(scratch/'source'))!=receipt['fixture_sha256']:
                raise AssertionError('Positive source fixture changed')
            if sha(scratch/'positive/compatibility-analysis.log')!=receipt['log_sha256']:
                raise AssertionError('Positive analysis log changed')
            result=json.loads((scratch/'positive/result.json').read_text())
            if result['accepted'] is not False or result['legal_verdict_claimed'] is not False:
                raise AssertionError('Diagnostic claimed acceptance or legal verdict')
            negative=(scratch/'negative-analysis.log').read_text()
            if (packet['negative']!={'removed':'native_samples.jsonl','rejected':True} or
                'Missing required source: native_samples.jsonl' not in negative):
                raise AssertionError('Missing-source negative incomplete')
            rows.append({'case':suffix,'candidate':candidate,
                         'construction_sha256':source['construction_sha256'],
                         'positive_receipt_sha256':sha(scratch/'positive/compatibility.json'),
                         'missing_native_source_rejected':True})
    if seen!=set(expected):raise AssertionError('Eight-bundle compatibility inventory incomplete')
    return {'passed':True,'format':'c104538-unselected-v1-package-audit',
            'rows':rows,'selected':False,'native_executed':False,
            'strict_v2_proved':False,'accepted_recordings':0}


if __name__=='__main__':print(json.dumps(audit(),indent=2))

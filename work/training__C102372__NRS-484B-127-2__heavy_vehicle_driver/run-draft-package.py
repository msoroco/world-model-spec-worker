"""Exact unselected synthetic v1 positives and missing-source negatives."""
import importlib.util
import argparse
import hashlib
import json
from pathlib import Path
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
spec=importlib.util.spec_from_file_location('c102372_package',HERE/'probe-package.py')
package=importlib.util.module_from_spec(spec);spec.loader.exec_module(package)


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def saved_receipt(manifest,entry,candidate):
    case=entry['case_id'];suffix=case.rsplit('__',1)[-1]
    ref=entry if candidate=='primary' else next(
        item for item in entry['candidates'] if item['id']==candidate)
    folder=HERE/'draft-candidates'/suffix/candidate
    path=folder/'package-receipt.json'
    if not path.is_file():return None
    try:
        item=json.loads(path.read_text());receipt=item['receipt']
        checks={'actual_analysis','native_validation','mandatory_observations',
                'lean_decoder','render','final_decode','acquisition_unchanged'}
        if (item['passed'] is not True or item['case']!=case or item['candidate']!=candidate
            or item['construction_sha256']!=ref['construction_sha256']
            or item['negative_exit_code']==0 or item['accepted_recording_claimed'] is not False
            or receipt['format']!='worker-package-compatibility-v1'
            or receipt['case_id']!=case or receipt['candidate_id']!=candidate
            or receipt['construction_sha256']!=ref['construction_sha256']
            or receipt['runtime_manifest_sha256']!=manifest['runtime_manifest_sha256']
            or receipt['passed'] is not True or not checks<=set(receipt['checks'])
            or sha(folder/'package-analysis.log')!=receipt['log_sha256']
            or 'Missing required source: native_samples.jsonl' not in
               (folder/'package-negative.log').read_text()):
            return None
        return item
    except (KeyError,ValueError,TypeError,OSError):return None


def main(resume=False):
    manifest=json.loads((HERE/'draft-execution-manifest.json').read_text())
    records=[]
    with tempfile.TemporaryDirectory(dir=ROOT/'.runtime-work',prefix='c102372-package-matrix-') as temporary:
        scratch=Path(temporary)
        for suffix in ('probe_1','probe_2','two_lane_exception','passing_overtake',
                       'passing_hold','conditions_steady','conditions_lead_brake'):
            entry=next(item for item in manifest['cases']
                       if item['case_id']==HERE.name+'__'+suffix)
            candidates=('primary','fallback1','fallback2','fallback3')
            cached={candidate:saved_receipt(manifest,entry,candidate) if resume else None
                    for candidate in candidates}
            if all(cached.values()):
                for candidate in candidates:
                    records.append(cached[candidate])
                    print(suffix,candidate,'exact receipt reused',flush=True)
                continue
            source_root=scratch/(suffix+'-source')
            source_root.mkdir()
            source=package.make_source(suffix,source_root)
            for candidate in candidates:
                if cached[candidate]:
                    records.append(cached[candidate])
                    print(suffix,candidate,'exact receipt reused',flush=True)
                    continue
                folder=scratch/(suffix+'-'+candidate);folder.mkdir()
                value=package.probe(suffix,candidate,source,folder)
                saved=HERE/'draft-candidates'/suffix/candidate
                (saved/'package-analysis.log').write_bytes(
                    (folder/'output/compatibility-analysis.log').read_bytes())
                (saved/'package-negative.log').write_text(value.pop('negative_log'))
                (saved/'package-receipt.json').write_text(json.dumps(value,indent=2)+'\n')
                records.append(value)
                print(suffix,candidate,'portable pass',flush=True)
    (HERE/'draft-package-summary.json').write_text(json.dumps({
        'format':'c102372-unselected-v1-package-summary','results':records},indent=2)+'\n')
    return {'passed':True,'exact_candidates':len(records),
            'accepted_recordings_claimed':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--resume',action='store_true')
    args=parser.parse_args()
    print(json.dumps(main(resume=args.resume),sort_keys=True))

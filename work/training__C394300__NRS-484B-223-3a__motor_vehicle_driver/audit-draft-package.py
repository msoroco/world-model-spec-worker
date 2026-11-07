"""Independent exact v1 diagnostic receipt audit for the unselected 3(a) pair."""
import hashlib
import json
from pathlib import Path

FOLDER=Path(__file__).resolve().parent
CASES=('controlled_1','controlled_2')
CANDIDATES=('primary','fallback1','fallback2','fallback3')
CHECKS={'actual_analysis','native_validation','mandatory_observations',
        'lean_decoder','render','final_decode','acquisition_unchanged'}


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    manifest=json.loads((FOLDER/'draft-execution-manifest.json').read_text())
    entries={entry['case_id']:entry for entry in manifest['cases']}
    assert manifest['status']=='draft_not_selected' and len(entries)==2
    rows=[]
    for case in CASES:
        case_id=FOLDER.name+'__'+case
        entry=entries[case_id]
        selected={'primary':entry,**{c['id']:c for c in entry['candidates']}}
        assert set(selected)==set(CANDIDATES)
        for candidate in CANDIDATES:
            log=FOLDER/f'probe-package-{case}-{candidate}.log'
            lines=log.read_text().splitlines()
            assert len(lines)==2 and lines[0].startswith('scratch ')
            record=json.loads(lines[1]);positive=record['positive'];negative=record['negative']
            assert record['case']==case and record['candidate']==candidate
            assert record['scope']=='unselected diagnostic exact package, not selected strict v2 delivery'
            assert positive['format']=='worker-package-compatibility-v1' and positive['passed'] is True
            assert positive['case_id']==case_id and positive['candidate_id']==candidate
            assert positive['construction_sha256']==selected[candidate]['construction_sha256']
            assert positive['runtime_manifest_sha256']==manifest['runtime_manifest_sha256']
            assert CHECKS<=set(positive['checks'])
            assert negative['exit_code']!=0 and negative['removed']=='declared_purpose.json'
            assert negative['error_contains']=='Missing required source: declared_purpose.json'
            rows.append({'case_id':case_id,'candidate_id':candidate,'log_sha256':sha(log),
                'construction_sha256':positive['construction_sha256'],
                'positive_format':positive['format'],'negative_exit':negative['exit_code']})
    return {'format':'c394300-3a-unselected-package-audit-v1','passed':True,
        'diagnostic_exact_v1_count':len(rows),'selected_or_delivery_ready_claimed':False,
        'results':rows}


if __name__=='__main__':print(json.dumps(audit(),indent=2))

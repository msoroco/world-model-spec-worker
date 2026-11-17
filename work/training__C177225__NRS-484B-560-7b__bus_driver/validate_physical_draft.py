"""Check retained source-bound negative physical diagnostics without promotion."""
import hashlib
import json
from pathlib import Path

folder=Path(__file__).resolve().parent
manifest=json.loads((folder/'execution-manifest.json').read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
for entry in manifest['cases']:
    ref=entry['physical_preparation_draft']
    path=folder/ref['receipt']
    if sha(path)!=ref['sha256']:
        raise ValueError('Changed physical draft')
    draft=json.loads(path.read_text())
    if (draft['case_id']!=entry['case_id'] or draft['construction_sha256']!=entry['construction_sha256'] or
            draft['complete_motion'] is not None or draft['lifecycle']['events_proven']):
        raise ValueError('Physical draft incorrectly claims Native completion')
    if {item['kind'] for item in draft['fixtures']}!={'incomplete_motion','missing_evidence'}:
        raise ValueError('Negative outcome fixtures incomplete')
    for item in draft['fixtures']:
        if sha(folder/item['log'])!=item['log_sha256'] or sha(folder/item['result'])!=item['result_sha256']:
            raise ValueError('Changed physical diagnostic proof')
        result=json.loads((folder/item['result']).read_text())
        expected='not_met' if item['kind']=='incomplete_motion' else 'unverified'
        if (result['case_id']!=entry['case_id'] or result['physical_checks']['maneuver']['status']!=expected or
                result['maneuver_completed'] or result['provenance_kind']!='synthetic_fixture'):
            raise ValueError('Negative outcome status or provenance differs')
    if sha(folder/draft['lifecycle']['test_log'])!=draft['lifecycle']['test_log_sha256']:
        raise ValueError('Lifecycle test log changed')
    print(entry['case_id'], 'negative physical outcomes verified; Native complete motion pending')
